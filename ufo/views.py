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
import stat
import utils

from filesystem import SyncDocument
from sharing import FriendDocument
from utils import get_user_infos
import pwd

from couchdb.mapping import ViewField


def _wrap_bypass(row):
    return row

def _reduce_sum(keys, values):
    return sum(values)

def _reduce_unique(keys, values):
    return True


class SortedByTypeSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_type(doc):
        if doc['doctype'] == "SyncDocument" and \
           doc["type"] != "application/x-directory":
            yield doc['type'].split('/'), 1

    @classmethod
    def getDocuments(cls, database, category=None, type=None):
        if type:
            assert category

            for doc in cls.by_type(database, key="%s/%s" % (category, type)):
              yield doc

        else:
            if category:
                start = [category]
            else:
                start = []

            end = start + [{}]
            dirpath = "/" + "/".join(start)
            for row in cls.sorted_by_type(database,
                                          startkey=start,
                                          endkey=end,
                                          group_level=len(start) + 1):

                yield cls(filename=row['key'][len(start)],
                          dirpath=dirpath,
                          mode=0555 | stat.S_IFDIR,
                          type="application/x-directory")


class FriendSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_login(doc):
        if doc['doctype'] == 'FriendDocument' and doc['status'] != 'BLOCKED_USER':
            yield doc['login'], 1

    @classmethod
    def getDocuments(cls, database):
        for row in cls.sorted_by_login(database, group=True):
            if row['key'] != database.name:
                # Retrieve provider infos from gss api
                infos = utils.get_user_infos(row['key'])
                #yield cls(filename=infos['fullname'],
                yield cls(filename=infos['login'],
                          dirpath=os.sep,
                          mode=0555 | stat.S_IFDIR,
                          uid=infos['uid'],
                          gid=infos['gid'],
                          type="application/x-directory")


class BuddySharesSyncDocument(SyncDocument):
    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_unique)
    def sorted_by_provider(doc):
        import pwd
        if doc['doctype'] == 'SyncDocument':
            yield pwd.getpwuid(doc['stats']['st_uid']).pw_name, 1

    @classmethod
    def getDocuments(cls, database, buddy=None, *path):
        if len(path) > 0:
            login = get_user_infos(uid=int(buddy))['login']
            for doc in cls.by_dir(database,
                                  key="/" + "/".join([login] + list(path))):
                yield doc

        elif buddy:
            uid = int(buddy)
            login = get_user_infos(uid=uid)['login']
            shared_dirs = { }
            startkey = [ uid, "/" + login ]
            endkey = [ uid + 1 ]
            for doc in cls.by_uid_and_path(database, startkey=startkey, endkey=endkey):
                if doc.type == "application/x-directory":
                    shared_dirs[doc.path] = doc
                else:
                    if doc.dirpath in shared_dirs:
                        continue
                yield doc

        else:
            for row in cls.sorted_by_provider(database, group=True):
                if row['key'] != database.name:
                    # Retrieve provider infos from gss api
                    infos = utils.get_user_infos(row['key'])
                    #yield cls(filename=infos['fullname'],
                    yield cls(filename=infos['login'],
                              dirpath=os.sep,
                              mode=0555 | stat.S_IFDIR,
                              uid=infos['uid'],
                              gid=infos['gid'],
                              type="application/x-directory")


class MySharesSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_unique)
    def sorted_by_participant(doc):
        import pwd
        from ufo.acl import ACL, ACL_XATTR, ACL_USER
        if doc['doctype'] == 'SyncDocument' and doc.get('xattrs', {}).has_key(ACL_XATTR):
            try:
                acl = ACL.from_xattr(eval(repr(doc['xattrs'][ACL_XATTR])[1:]))
                for ace in acl:
                    if ace.kind & ACL_USER:
                        yield pwd.getpwuid(ace._qualifier).pw_name, 1
            except: pass

    @classmethod
    def getDocuments(cls, database, buddy=None, *path):
        if len(path) > 0:
            login = get_user_infos(uid=int(buddy))['login']
            for doc in cls.by_dir(database,
                                  key="/" + "/".join([login] + list(path))):
                yield doc
        elif buddy:
            uid = int(buddy)
            login = get_user_infos(uid=uid)['login']
            shared_dirs = {}
            provider_id = get_user_infos(login=database.name)['uid']
            startkey = [ provider_id, uid ]
            endkey = [ provider_id, uid + 1 ]
            for doc in SyncDocument.by_provider_and_participant(database,
                                                                startkey=startkey,
                                                                endkey=endkey):
                if doc.type == "application/x-directory":
                    shared_dirs[doc.path] = doc
                else:
                    if doc.dirpath in shared_dirs:
                        continue
                yield doc

        else:
            for row in cls.sorted_by_participant(database, group=True):
                if row['key'] != database.name:
                    # Retrieve participant infos from gss api
                    infos = utils.get_user_infos(row['key'])
                    #yield cls(filename=infos['fullname'],
                    yield cls(filename=infos['login'],
                              dirpath=os.sep,
                              mode=0555 | stat.S_IFDIR,
                              uid=infos['uid'],
                              gid=infos['gid'],
                              type="application/x-directory")


class TaggedSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_tag(doc):
        if doc['doctype'] == "SyncDocument":
            for tag in doc['tags']:
                yield [ doc['stats']['st_uid'], tag ], 1

    @classmethod
    def getDocuments(cls, database, tag=None, uid=None):
        if tag:
            for doc in cls.by_tag(database, key=tag):
                yield doc

        else:
            kw = { "group" : True }
            if uid:
                kw["startkey"] = [ uid ]
                kw["endkey"] = [ uid + 1 ]
            for row in cls.sorted_by_tag(database, **kw):
                yield cls(filename=row['key'][1],
                          dirpath=os.sep,
                          mode=0555 | stat.S_IFDIR,
                          type="application/x-directory")

