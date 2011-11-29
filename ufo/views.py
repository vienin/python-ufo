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

from ufo.filesystem import SyncDocument
from ufo.sharing import FriendDocument
from ufo.utils import get_user_infos
from ufo.database import DocumentHelper


class SortedByTypeSyncDocument(SyncDocument):

    @classmethod
    def getDocuments(cls, database, category=None, type=None):
        helper = DocumentHelper(SyncDocument, database)

        if type:
            assert category

            for doc in helper.by_type(key="%s/%s" % (category, type)):
              yield doc

        else:
            if category:
                start = [category]
            else:
                start = []

            end = start + [{}]
            dirpath = "/" + "/".join(start)
            for key, doc in helper.by_type(startkey=start,
                                           endkey=end,
                                           group_level=len(start) + 1, reduce=True):

                yield cls(filename=key[len(start)],
                          dirpath=dirpath,
                          mode=0555 | stat.S_IFDIR,
                          type="application/x-directory")


class FriendSyncDocument(SyncDocument):

    @classmethod
    def getDocuments(cls, database):
        for user in DocumentHelper(FriendDocument, database).by_login():
            if user.login != database.name and user.status != 'BLOCKED_USER':
                yield cls(filename=user.login,
                          dirpath=os.sep,
                          mode=0555 | stat.S_IFDIR,
                          uid=user.uid,
                          gid=user.gid,
                          type="application/x-directory")


class BuddySharesSyncDocument(SyncDocument):

    @classmethod
    def getDocuments(cls, database, buddy=None, *path):
        helper = DocumentHelper(cls, database)

        if len(path) > 0:
            login = get_user_infos(uid=int(buddy))['login']
            for doc in helper.by_dir(key="/" + "/".join([login] + list(path))):
                yield doc

        elif buddy:
            uid = utils.get_user_infos(login=database.name)['uid']
            provider = int(buddy)
            shared_dirs = { }
            startkey = [ provider, uid ]
            endkey = [ provider + 1, uid ]
            for key, doc in helper.by_provider_and_participant(startkey=startkey,
                                                               endkey=endkey):
                if doc.type == "application/x-directory":
                    shared_dirs[doc.path] = doc
                else:
                    if doc.dirpath in shared_dirs:
                        continue
                yield doc

        else:
            uid = utils.get_user_infos(login=database.name)['uid']
            for key, doc in helper.by_provider_and_participant(group_level=1, reduce=True):
                if key[0] != uid:
                    # Retrieve provider infos from gss api
                    infos = utils.get_user_infos(uid=key[0])
                    yield cls(filename=infos['login'],
                              dirpath=os.sep,
                              mode=0555 | stat.S_IFDIR,
                              uid=infos['uid'],
                              gid=infos['gid'],
                              type="application/x-directory")


class MySharesSyncDocument(SyncDocument):

    @classmethod
    def getDocuments(cls, database, buddy=None, *path):
        helper = DocumentHelper(cls, database)

        if len(path) > 0:
            login = get_user_infos(uid=int(buddy))['login']
            for doc in helper.by_dir(key="/" + "/".join([login] + list(path))):
                yield doc

        elif buddy:
            uid = int(buddy)
            shared_dirs = {}
            provider_id = get_user_infos(login=database.name)['uid']
            startkey = [ provider_id, uid ]
            endkey = [ provider_id, uid + 1 ]
            for key, doc in helper.by_provider_and_participant(startkey=startkey,
                                                               endkey=endkey):
                if doc.type == "application/x-directory":
                    shared_dirs[doc.path] = doc
                else:
                    if doc.dirpath in shared_dirs:
                        continue
                yield doc

        else:
            uid = utils.get_user_infos(login=database.name)['uid']
            for key, doc in helper.by_provider_and_participant(startkey=[uid],
                                                               group_level=2,
                                                               reduce=True):
                if key != uid:
                    # Retrieve participant infos from gss api
                    infos = utils.get_user_infos(uid=key[1])
                    yield cls(filename=infos['login'],
                              dirpath=os.sep,
                              mode=0555 | stat.S_IFDIR,
                              uid=infos['uid'],
                              gid=infos['gid'],
                              type="application/x-directory")


class TaggedSyncDocument(SyncDocument):

    @classmethod
    def getDocuments(cls, database, tag=None, uid=None):
        helper = DocumentHelper(cls, database)

        startkey = []
        endkey = []

        if tag:
            startkey.append(tag)
            endkey.append(tag + "\u9999")
        else:
            startkey.append("_")
            endkey.append(u"\u9999")

        if uid:
            startkey.append(uid)
            endkey.append(uid + 1)

        if tag:
            for key, doc in helper.by_tag(startkey=startkey, endkey=endkey):
                yield doc

        else:
            kw = {}
            if startkey and endkey:
                kw["startkey"] = startkey
                kw["endkey"] = endkey

            for key, value in helper.by_tag(reduce=True, group_level=len(startkey), **kw):
                # This is done to spare a view, hopefully this shouldn't happen
                # very often and on a small dataset
                if uid != None and key[1] != uid:
                    continue

                yield cls(filename=key[0],
                          dirpath=os.sep,
                          mode=0555 | stat.S_IFDIR,
                          type="application/x-directory")
