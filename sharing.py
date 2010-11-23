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


from database import Document, TextField, ViewField
from constants import Notification

class FriendDocument(Document):

    doctype = TextField(default="FriendDocument")

    status = TextField()
    login  = TextField()

    @ViewField.define('friend')
    def by_login(doc):
        if doc['doctype'] == 'FriendDocument':
            yield doc['login'], doc

    @ViewField.define('friend')
    def by_login_and_status(doc):
        if doc['doctype'] == 'FriendDocument':
            yield [doc['login'], doc['status']], doc

    @ViewField.define('friend')
    def by_status(doc):
        '''
        For example to get all pending_followers use : 
        FriendShip.by_status(db, key='pending_followers', limit=10)
        '''
        if doc['doctype'] == 'FriendDocument':
            yield doc['status'], doc

    @ViewField.define('friend')
    def by_id(doc):
      if doc['doctype'] == "FriendDocument":
        yield doc['_id'], doc


class ShareDocument(Document):

    doctype = TextField(default="ShareDocument")

    provider    = TextField()
    participant = TextField()
    filepath    = TextField()
    permissions = TextField()
    flags       = TextField()

    @ViewField.define('share')
    def by_provider_and_path(doc):
        if doc['doctype'] == 'ShareDocument':
            yield [doc['provider'], doc['filepath']], doc

    @ViewField.define('share')
    def by_provider_and_participant(doc):
        if doc['doctype'] == 'ShareDocument':
            yield [doc['provider'], doc['participant']], doc

    @ViewField.define('share')
    def by_provider_and_participant_and_path(doc):
        if doc['doctype'] == 'ShareDocument':
            yield [doc['provider'], doc['participant'], doc['filepath']], doc

    @ViewField.define('share')
    def by_provider_and_participant_and_flag(doc):
        if doc['doctype'] == 'ShareDocument':
            yield [doc['provider'], doc['participant'], doc['flags']], doc

    @ViewField.define('share')
    def by_id(doc):
      if doc['doctype'] == "ShareDocument":
        yield doc['_id'], doc
