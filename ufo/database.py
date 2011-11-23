# Copyright (C) 2010  Agorabox. All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'''UFO client library.'''

import os
import socket
import new
import kerberos as k
from uuid import uuid4
from urlparse import urlsplit

import ufo.auth
from debugger import Debugger
from errors import ConflictError

from couchdb.http import ResourceNotFound, ResourceConflict, Session
from couchdb.client import Server
from couchdb.design import ViewDefinition
from couchdb.mapping import *

couchdb_servers = {}


class UTF8Document(Document):
    def __init__(self, *args, **fields):
        for field in fields:
            if isinstance(fields[field], str) and fields[field]:
                fields[field] = fields[field].decode('utf-8')

        super(UTF8Document, self).__init__(*args, **fields)

    def __getattribute__(self, attr):
      result = super(UTF8Document, self).__getattribute__(attr)

      if isinstance(result, unicode):
        return result.encode('utf-8')

      return result

    def __setattr__(self, attr, value):
      if isinstance(value, str):
        value = value.decode('utf-8')

      super(UTF8Document, self).__setattr__(attr, value)


class ChangesSequenceDocument(Document):

    doctype    = TextField(default="ChangesSequenceDocument")

    consumer   = TextField()
    seq_number = IntegerField()

    @ViewField.define('changessequence')
    def by_consumer(doc):
        if doc['doctype'] == "ChangesSequenceDocument":
            yield doc['consumer'], doc


class ChangesFiltersDocument(Document):

    filters    = DictField(Mapping.build(
                   by_type = TextField(default=""
                     "function(doc, req) {"
                     "  if(doc.doctype == req.query.type)"
                     "    { return true; }"
                     "  else"
                     "    { return false; }"
                     "}")))


class ReplicationFiltersDocument(Document):
    filters    = DictField(Mapping.build(
                   nodesigndocs = TextField(default=""
                     "function(doc, req) {"
                     " if (doc.local) return false;"
                     " if (doc._id.slice(0, 8) === '_design/') {"
                     "  return false;"
                     " }"
                     " else {"
                     "  return true;"
                     " }"
                     "}"),

                   onlymeta = TextField(default=""
                     "function(doc, req) {"
                     " if (doc.local) return false;"
                     " if (doc.doctype == 'FriendDocument') {"
                     "   return true;"
                     " }"
                     "}")))


class DocumentHelper(Debugger):

    doc_class = None
    database  = None
    server    = None

    batchmode = False

    def __init__(self, doc_class, db, server="http://localhost:5984", auth=None, batch=False):
        try:
            # Creating server object
            if not couchdb_servers.has_key(server):
                couchdb_servers[server] = (Server(server), {})

            def _get_connection(self, url):
                conn = Session._get_connection(self, url)
                auth.bind(conn, service="couchdb")
                return conn

            self.server, databases = couchdb_servers[server]

            if auth:
                # Hook the _get_connection method to used authenticated requests
                self.server.resource.session._get_connection = new.instancemethod(_get_connection,
                                                                                  self.server.resource.session)

            # Creating database if needed
            if type(db) in (str, unicode):
                if databases.has_key(db):
                    self.database = databases[db]
                else:
                    try:
                        self.database = self.server[db]
                    except:
                        raise
                        self.database = self.server.create(db)
                    finally:
                        databases[db] = self.database

                    if auth:
                        # Hook the _get_connection method again
                        self.database.resource.session._get_connection = new.instancemethod(_get_connection,
                                                                                            self.database.resource.session)

            else:
                self.database = db

        except socket.error, e:
            raise DocumentException("Unable to create database '%s' on %s (%s)"
                                    % (db, server, e.message))

        self.doc_class = doc_class

        self.batchmode = batch

    def sync(self):
        # Synchronizing all couchdb views of the document class
        for attr in self.doc_class.__dict__:
            if isinstance(getattr(self.doc_class, attr), ViewDefinition):
                getattr(self.doc_class, attr).sync(self.database)

    def commit(self):
      self.debug("%s: Syncing changes" % (self))

      self.database.commit()

    def create(self, **fields):
        doc = self.doc_class(**fields)

        if fields.has_key('_id'):
            doc._data['_id'] = fields['_id']
        else:
            doc._data['_id'] = uuid4().hex

        self.debug("%s: Creating %s:%s (batch=%s)"
                   % (self, doc.doctype, doc.id, str(self.batchmode)))

        opts = {}
        # Can't get the new generated _rev number when batch mode...
        if False and self.batchmode:
            opts['batch'] = 'ok'

        try:
            doc._data['_id'], doc._data['_rev'] = self.database.save(doc._data, **opts)

        except ResourceConflict, e:
            raise ConflictError

        return doc

    def update(self, documents):
        if not isinstance(documents, list):
            documents = [documents]

        self.debug("%s: Updating %s documents (batch=%s): %s"
                   % (self, len(documents), str(self.batchmode), str(documents)))

        # Build a document dict indexed by doc ids
        docs_by_id = {}
        for doc in documents:
            docs_by_id[doc.id] = doc

        opts = {}
        if self.batchmode:
          opts['batch'] = 'ok'

        # Update docs and fill rev fields with new ones
        for success, id, rev in self.database.update(documents, **opts):
            docs_by_id[id]['_rev'] = rev

        return documents

    def delete(self, document):
        self.debug("%s: Deleting %s:%s" % (self, document.doctype, document.id))

        self.database.delete(document)

    def changes(self, **opts):
        opts["filter"] = "changes/by_type"
        opts["type"] = self.doc_class.__name__
        return self.database.changes(**opts)

    def replicate(self, db_name, server="http://localhost:5984", auth=None, reverse=False, **opts):
        if auth:
            # The connection for the replication is created by the CouchDB server
            # but we can pass our authentication headers.
            # TODO: handle credentials expiration
            db_uri = urlsplit(server).hostname
            dest = { "url" : server + "/" + db_name,
                     "headers" : auth.get_headers("couchdb", db_uri) }
        
        else:
            dest = server + "/" + db_name

        if reverse:
            src  = dest
            dest = self.database.name
        else:
            src = self.database.name

        try:
            return self.server.replicate(src, dest, **opts)
        except ResourceNotFound, e:
            raise DocumentException("Can not replicate %s to %s (%s)" %
                                    (src, dest, e.message))

    def _pk_view(self, view, **opts):
        try:
            key = opts.pop('key')
            return getattr(self.doc_class, view)(self.database, key=key, **opts).rows[0]

        except KeyError, e:
            raise DocumentException("You must specify a key for %s.%s()" %
                                    (self.doc_class.__name__, view))

        except IndexError, e:
            raise DocumentException("Primary not found key for %s.%s(key='%s')" %
                                    (self.doc_class.__name__, view, key))

    def __getattr__(self, attr):
        # Checking within document couchdb views
        if isinstance(getattr(self.doc_class, attr), ViewDefinition):
            
            def view_wrapper(**opts):
                self.debug("%s: Calling view %s:%s(%s)"
                           % (self, self.doc_class.__name__, attr, str(opts)))

                if opts.get("pk"):
                    return self._pk_view(attr, **opts)
                return getattr(self.doc_class, attr).__call__(self.database, **opts)

            return view_wrapper

        return lambda *args, **kw: getattr(self.doc_class, attr).__call__(self.database, *args, **kw)

    def __str__(self):
        return '<DocumentHelper class: %s server: %s database: %s>' % \
               (self.doc_class.__name__, self.server, self.database.name)

    def __repr__(self):
        return str(self)


class DocumentException(Exception):
    pass
