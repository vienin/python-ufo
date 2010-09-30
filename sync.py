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

'''UFO file synchronization client library.'''

import os
import posix

from utils import MutableStat

from couchdb.client import Server
from couchdb.design import ViewDefinition
from couchdb.mapping import *

couchdb_servers = {}

class FriendDocument(Document):
    # status : "FOLLOWER" | "FOLLOWING" | "PENDING_FOLLOWER" | 
    #          "PENDING_FOLLOWING" | "BLOCKED_USER" (see constants.py)
    status       = TextField() 
    login       = TextField() # 'lambert'
    notification = TextField() # 'NOT_NOTIFY' | 'NOTIFY' (see constants.py)
    doctype      = TextField(default="Friend")

    @ViewField.define('notification')
    def by_notification(doc):
        if doc.get('doctype') and (doc['doctype'] == 'Friend'):
            yield doc['notification'], doc

    @ViewField.define('login')
    def by_login(doc):
        if doc.get('doctype') and (doc['doctype'] == 'Friend'):
            yield doc['login'], doc

    @ViewField.define('login')
    def by_login_and_status(doc):
        if doc.get('doctype') and (doc['doctype'] == 'Friend'):
            yield [doc['login'],doc['status']], doc

    @ViewField.define('status')
    def by_status(doc):
        '''
        For example to get all pending_followers use : 
        FriendShip.by_status(db, key='pending_followers', limit=10)
        '''
        if doc.get('doctype') and (doc['doctype'] == 'Friend'):
            yield doc['status'], doc

            

class SyncDocument(Document):

    doctype  = TextField(default="SyncDocument")
    filename = TextField()
    dirpath  = TextField()
    uid      = IntegerField()
    gid      = IntegerField()
    mode     = IntegerField()
    type     = TextField()
    users    = ListField(TextField)
    stats    = DictField(Mapping.build(
                   n_sequence_fields = IntegerField(),
                   n_unnamed_fields  = IntegerField(),
                   n_fields   = IntegerField(),
                   st_atime   = FloatField(),
                   st_blksize = IntegerField(),
                   st_blocks  = IntegerField(),
                   st_ctime   = FloatField(),
                   st_dev     = IntegerField(),
                   st_gid     = IntegerField(),
                   st_ino     = IntegerField(),
                   st_mode    = IntegerField(),
                   st_mtime   = FloatField(),
                   st_nlink   = IntegerField(), 
                   st_rdev    = IntegerField(),
                   st_size    = LongField(),
                   st_uid     = IntegerField()))

    def __init__(self, stats=None, **fields):
        super(SyncDocument, self).__init__(**fields)
        if stats: 
            self.set_stats(stats)
  
    def set_stats(self, stat_result):
        for field in self.stats._fields.keys():
            setattr(self.stats, field, getattr(stat_result, field))
  
    def get_stats(self):
        stat_result = MutableStat()
        for field in self.stats._fields.keys():
            if field in ['st_uid', 'st_gid', 'st_mode']:
                setattr(stat_result, field, getattr(self, field[3:]))
            else:
                setattr(stat_result, field, getattr(self.stats, field))
    
        return stat_result

    def _wrap_bypass(row):
        return row

    def _reduce_sum(keys, values):
        return sum(values)

    @ViewField.define('path')
    def by_path(doc):
        from os.path import join
        if doc['doctype'] == "SyncDocument":
            yield join(doc['dirpath'], doc['filename']), doc

    @ViewField.define('type')
    def by_type(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['type'], doc

    @ViewField.define('dir')
    def by_dir(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['dirpath'], doc

    @ViewField.define('dirprefix')
    def by_dir_prefix(doc):
        from os import sep
        from os.path import dirname
        if doc['doctype'] == "SyncDocument":
            last = ''
            current = doc['dirpath']
            while current != sep and current != last:
                yield current, doc
                last = current
                current = dirname(current)

    @ViewField.define('mimetypes', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def mimetypes(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['type'].split('/'), 1

    def __str__(self):
        return '<%s id:%s path:%s type:%s>' % \
               (self.doctype, self.id, os.path.join(self.dirpath, self.filename), self.type)

    def __repr__(self):
        return str(self)


class RevisionDocument(Document):

    doctype  = TextField(default="RevisionDocument")
    filepath = TextField()
    revision = TextField()

    @ViewField.define('revision')
    def by_path(doc):
        if doc['doctype'] == "RevisionDocument":
            yield doc['filepath'], doc


class DocumentHelper(object):

    document_class = None
    database       = None

    def __init__(self, doc_class, db_name, db_uri="localhost", db_port=5984):

        # Creating server object
        if not couchdb_servers.has_key(db_uri):
            couchdb_servers[db_uri] = Server("http://" + db_uri + ":" + str(db_port))

        # Creating database if needed
        if db_name not in couchdb_servers[db_uri]:
            self.database = couchdb_servers[db_uri].create(db_name)
        else:
            self.database = couchdb_servers[db_uri][db_name]

        # Synchronizing all document class couchdb views
        self.document_class = doc_class
        for attr in self.document_class.__dict__:

            if isinstance(getattr(self.document_class, attr), ViewDefinition):
                getattr(self.document_class, attr).sync(self.database)

    def create(self, **fields):
        return self.document_class(**fields).store(self.database)

    def update(self, documents):
        if not isinstance(documents, list):
            documents = [documents]

        # Build a document dict indexed by doc ids
        docs_by_id = {}
        for doc in documents:
            docs_by_id[doc.id] = doc

        # Update docs and fill rev fields with new ones
        for success, id, rev in self.database.update(documents):
            docs_by_id[id]['_rev'] = rev

        return documents

    def delete(self, document):
        self.database.delete(document)

    def _pk_view(self, view, **opts):
        try:
            key = opts.pop('key')
            return getattr(self.document_class, view)(self.database, key=key, **opts).rows[0]

        except KeyError, e:
            raise DocumentException("You must specify a key for %s.%s()" %
                                    (self.document_class.__name__, view))

        except IndexError, e:
            raise DocumentException("Primary not found key for %s.%s(key='%s')" %
                                    (self.document_class.__name__, view, key))

    def __getattr__(self, attr):
        # First checking DocumentHelper attributes
        if self.__dict__.has_key(attr):
            return self.__dict__[attr]

        # Then checking within document couchdb views
        if isinstance(getattr(self.document_class, attr), ViewDefinition):

            def view_wrapper(**opts):
                if opts.get("pk"):
                    return self._pk_view(attr, **opts)
                return getattr(self.document_class, attr)(self.database, **opts)

            return view_wrapper

        raise AttributeError(attr)


class DocumentException(Exception):
    pass
