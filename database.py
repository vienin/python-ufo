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
from uuid import uuid4

from debugger import Debugger

from couchdb.http import ResourceNotFound
from couchdb.client import Server
from couchdb.design import ViewDefinition
from couchdb.mapping import *

couchdb_servers = {}


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
                   by_type = TextField(default='''
                     function(doc, req) { 
                       if(doc.doctype == req.query.type)
                         { return true; }
                       else 
                         { return false; }
                     }''')))


class DocumentHelper(Debugger):

    doc_class = None
    database  = None
    server    = None

    batchmode = False

    def __init__(self, doc_class, db_name, db_uri="localhost", db_port=5984, batch=False):

        try:
            # Creating server object
            if not couchdb_servers.has_key(db_uri):
                couchdb_servers[db_uri] = Server("http://" + db_uri + ":" + str(db_port))

            self.server = couchdb_servers[db_uri]

            # Creating database if needed
            if db_name not in self.server:
                self.database = self.server.create(db_name)
            else:
                self.database = self.server[db_name]

        except socket.error, e:
            raise DocumentException("Unable to create database '%s' on %s:%s (%s)"
                                    % (db_name, db_uri, str(db_port), e.message))

        # Synchronizing all couchdb views of the document class
        self.doc_class = doc_class
        for attr in self.doc_class.__dict__:

            if isinstance(getattr(self.doc_class, attr), ViewDefinition):
                getattr(self.doc_class, attr).sync(self.database)

        # For instance, creating the 'changesfilters' design document here
        if not self.database.get("_design/changes"):
            changesfilters = ChangesFiltersDocument()
            changesfilters._data['_id'] = "_design/changes"
            changesfilters.store(self.database)
            
        self.batchmode = batch

    def commit(self):
      self.debug("%s: Syncing changes" % (self))

      self.database.commit()

    def create(self, **fields):
        # Generate _id UUID on the client side
        doc = self.doc_class(**fields)
        doc._data['_id'] = uuid4().hex

        self.debug("%s: Creating %s:%s (batch=%s)"
                   % (self, doc.doctype, doc.id, str(self.batchmode)))

        opts = {}
        if self.batchmode:
          opts['batch'] = 'ok'

        doc._data['_id'], doc._data['_rev'] = self.database.save(doc._data, **opts)
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
        self.debug("%s: Deleting %s:%s"
                   % (self, document.doctype, document.id))

        self.database.delete(document)

    def changes(self, **opts):
        opts["filter"] = "changes/by_type"
        opts["type"] = self.doc_class.__name__
        return self.database.changes(**opts)

    def replicate(self, dest, reverse=False, **opts):
        if reverse:
          src  = dest
          dest = self.database.name
        else:
          src = self.database.name

        try:
          self.server.replicate(src, dest, **opts)
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

        return lambda **args: getattr(self.doc_class, attr).__call__(self.database, **args)

    def __str__(self):
        return '<DocumentHelper class: %s server: %s database: %s>' % \
               (self.doc_class.__name__, self.server, self.database.name)

    def __repr__(self):
        return str(self)


class DocumentException(Exception):
    pass
