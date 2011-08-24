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

import utils
import config
import os
from datetime import datetime

import xmlrpclib as rpc
from ipalib.rpc import KerbTransport

from debugger import Debugger
from constants import ShareDoc

from database import *

from ufo.utils import ComponentProxy

def _(message):
  return message


class NotificationDocument(Document, Debugger):

    doctype = TextField(default="NotificationDocument")

    subtype = TextField(default="")

    title   = TextField(default="")
    body    = TextField(default="")
    summary = TextField(default="")
    actions = DictField()
    date    = DateTimeField(default=datetime.now)
    params  = DictField()

    def __init__(self):
        super(NotificationDocument, self).__init__()

    @ViewField.define('notification')
    def by_id(doc):
      if doc['doctype'] == "NotificationDocument":
        yield doc['_id'], doc


class NewFriendshipNotification(NotificationDocument):

    subtype = TextField(default="NewFriendship")

    initiator = TextField()
    target  = TextField()

    actions = DictField(Mapping.build(
                  block_invitation  = TextField(default=_("Block user")),
                  refuse_invitation = TextField(default=_("Refuse")),
                  accept_invitation = TextField(default=_("Accept"))))

    def __init__(self, **fields):
        super(NewFriendshipNotification, self).__init__()

        if fields.get('initiator') and fields.get('target'):
          self.initiator = fields['initiator']
          self.target  = fields['target']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('New friendship invitation')
          self.body    = _('You have been invited by %(fullname)s to be his/her friend.')
          self.summary = _("%(fullname)s wants to be your friend")
          self.params  = { "fullname" : fullname }

    def accept_invitation(self):
        self.debug("Accepting the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.accept_friend(self.initiator)

    def refuse_invitation(self):
        self.debug("Refusing the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.refuse_friend(self.initiator)

    def block_invitation(self):
        self.debug("Blocking the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.block_user(self.initiator)


class FollowRequestNotification(NotificationDocument):

    subtype = TextField(default="FollowRequest")

    initiator = TextField()
    target  = TextField()

    actions = DictField(Mapping.build(
                  block_invitation  = TextField(default=_("Block user")),
                  refuse_invitation = TextField(default=_("Refuse")),
                  accept_invitation = TextField(default=_("Accept"))))

    def __init__(self, **fields):
        super(FollowRequestNotification, self).__init__()

        if fields.get('initiator') and fields.get('target'):
          self.initiator = fields['initiator']
          self.target  = fields['target']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('New file sharing request')
          self.body    = _('%(fullname)s you like to be in your followers list.')
          self.summary = _("%(fullname)s wants to follow you")
          self.params  = { "fullname" : fullname }

    def accept_invitation(self):
        self.debug("Accepting the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.accept_following(self.initiator)

    def refuse_invitation(self):
        self.debug("Refusing the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.refuse_following(self.initiator)

    def block_invitation(self):
        self.debug("Blocking the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_account = ComponentProxy("ufoaccount.account.Account", config.sync_host)
        remote_account.block_user(self.initiator)


class AcceptedFriendshipNotification(NotificationDocument):

    subtype = TextField(default="AcceptedFriendship")

    initiator = TextField()
    target = TextField()

    actions = DictField(Mapping.build(
                  proceed_pending_shares = TextField(default=_("Ok"))))

    def __init__(self, **fields):
        super(AcceptedFriendshipNotification, self).__init__()

        if fields.get('initiator') and fields.get('target'):
          self.initiator = fields['initiator']
          self.target  = fields['target']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('Friendship invitation accepted')
          self.body    = _('%(fullname)s has accepted your friendship invitation, '
                           'you can now share some document with him/her.')
          self.summary = _("%(fullname)s has accepted your invitation")
          self.params  = { "fullname" : fullname }

    def proceed_pending_shares(self):
        self.debug("Proceed pending shares from '%s' to '%s'"
                   % (self.initiator, self.target))

        remote_sync = ComponentProxy("ufosync.sync.Sync", config.sync_host, ufo_in_server=False)
        remote_sync.proceed_pending_shares(self.initiator)


class CanceledFriendshipNotification(NotificationDocument):

    subtype = TextField(default="CanceledFriendship")

    initiator = TextField()

    def __init__(self, **fields):
        super(CanceledFriendshipNotification, self).__init__()

        if fields.get('initiator'):
          self.initiator = fields['initiator']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('A friendship has been canceled')
          self.body    = _('%(fullname)s has removed you from his friend list, '
                           'you can not access to his files any more.')
          self.summary = _("%(fullname)s has canceled his friendship with you")
          self.params  = { "fullname" : fullname }


class RefusedFriendshipNotification(NotificationDocument):

    subtype = TextField(default="RefusedFriendship")

    initiator = TextField()

    def __init__(self, **fields):
        super(RefusedFriendshipNotification, self).__init__()

        if fields.get('initiator'):
          self.initiator = fields['initiator']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('A friendship has refused your friend request')
          self.body    = _('%(fullname)s would rather be stranger than friends.')
          self.summary = _("%(fullname)s has refused your friend request")
          self.params  = { "fullname" : fullname }


class NewShareNotification(NotificationDocument):

    subtype = TextField(default="NewShare")

    initiator = TextField()
    filepath  = TextField()

    def __init__(self, **fields):
        super(NewShareNotification, self).__init__()

        if fields.get('initiator') and fields.get('filepath'):
          self.initiator = fields['initiator']
          self.filepath  = fields['filepath']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('A new file has been shared')
          self.body    = _('The new file \'%(file)s\' has been shared by %(fullname)s.')
          self.summary = _("%(fullname)s has shared a file with you")
          self.params = { "file" : os.path.basename(self.filepath),
                          "fullname" : fullname }


class CanceledShareNotification(NotificationDocument):

    subtype = TextField(default="CanceledShare")

    initiator = TextField()
    filepath  = TextField()

    def __init__(self, **fields):
        super(CanceledShareNotification, self).__init__()

        if fields.get('initiator') and fields.get('filepath'):
          self.initiator = fields['initiator']
          self.filepath  = fields['filepath']

          fullname = utils.get_user_infos(self.initiator)['fullname']

          self.title   = _('A share has been canceled')
          self.body    = _('%(fullname)s has canceled the share of \'%(file)s\', '
                           'so you can\'t access the file any more.')
          self.summary = _("%(fullname)s has canceled a share with you")
          self.params  = { "file" : os.path.basename(self.filepath),
                           "fullname" : fullname }
