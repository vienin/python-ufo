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
from sharing import ShareDocument

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
            for row in cls.sorted_by_type(database,
                                          startkey=start,
                                          endkey=end,
                                          group_level=len(start) + 1):

                yield cls(filename=row['key'][len(start)], mode=0555 | stat.S_IFDIR)


class BuddySharesSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_provider(doc):
        if doc['doctype'] == "ShareDocument":
            yield doc['provider'], 1

    @classmethod
    def getDocuments(cls, database, buddy=None):
        if buddy:
            for doc in cls.by_uid(database, key=int(buddy)):
              if doc.type != "application/x-directory":
                yield doc

        else:
            for row in cls.sorted_by_provider(database, group=True):
              if row['key'] != database.name:
                # Retrieve provider infos from gss api
                infos = utils.get_user_infos(row['key'])
                yield cls(filename=infos['fullname'],
                          mode=0555 | stat.S_IFDIR,
                          uid=infos['uid'],
                          gid=infos['gid'])


class MySharesSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_participant(doc):
        if doc['doctype'] == "ShareDocument":
            yield doc['participant'], 1

    @classmethod
    def getDocuments(cls, database, buddy=None):
        if buddy:
            participant = utils.get_user_infos(uid=int(buddy))['login']
            for share in ShareDocument.by_provider_and_participant(database,
                                                                   key=[database.name, participant]):
              for doc in cls.by_path(database, key=share.filepath):
                yield doc

        else:
            for row in cls.sorted_by_participant(database, group=True):
              if row['key'] != database.name:
                # Retrieve participant infos from gss api
                infos = utils.get_user_infos(row['key'])
                yield cls(filename=infos['fullname'],
                          mode=0555 | stat.S_IFDIR,
                          uid=infos['uid'],
                          gid=infos['gid'])


class TaggedSyncDocument(SyncDocument):

    @ViewField.define('viewsdocument', wrapper=_wrap_bypass, reduce_fun=_reduce_sum)
    def sorted_by_tag(doc):
        if doc['doctype'] == "SyncDocument":
            for tag in doc['tags']:
                yield tag, 1

    @classmethod
    def getDocuments(cls, database, tag=None):
        if tag:
            for doc in cls.by_tag(database, key=tag):
              yield doc

        else:
            for row in cls.sorted_by_tag(database, group=True):
                yield cls(filename=row['key'], mode=0555 | stat.S_IFDIR)

