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

    def __init__(self):
        super(NotificationDocument, self).__init__()

    @ViewField.define('notification')
    def by_id(doc):
      if doc['doctype'] == "NotificationDocument":
        yield doc['_id'], doc


class NewFriendshipNotification(NotificationDocument):

    subtype = TextField(default="NewFriendship")

    following = TextField()
    follower  = TextField()

    actions = DictField(Mapping.build(
                  block_invitation  = TextField(default=_("Block user")),
                  refuse_invitation = TextField(default=_("Refuse")),
                  accept_invitation = TextField(default=_("Accept"))))

    def __init__(self, **fields):
        super(NewFriendshipNotification, self).__init__()

        if fields.get('following') and fields.get('follower'):
          self.following = fields['following']
          self.follower  = fields['follower']

          fullname = utils.get_user_infos(self.following)['fullname']

          self.title   = _('New friendship invitation')
          self.body    = _('You have been invited by %s to be his/her friend.') % fullname
          self.summary = _("New friend invitation (%s)") % fullname

    def accept_invitation(self):
        self.debug("Accepting the friend invitation from '%s' to '%s'"
                   % (self.following, self.follower))

        meta = { "apache_env" : { "KRB5CCNAME" : os.environ["KRB5CCNAME"] } }
        remote_account = ComponentProxy("ufoaccount.account.Account", meta, config.sync_host)
        remote_account.accept_following(self.following)

    def refuse_invitation(self):
        self.debug("Refusing the friend invitation from '%s' to '%s'"
                   % (self.following, self.follower))

        meta = { "apache_env" : { "KRB5CCNAME" : os.environ["KRB5CCNAME"] } }
        remote_account = ComponentProxy("ufoaccount.account.Account", meta, config.sync_host)
        remote_account.refuse_following(self.following)

    def block_invitation(self):
        self.debug("Blocking the friend invitation from '%s' to '%s'"
                   % (self.following, self.follower))

        meta = { "apache_env" : { "KRB5CCNAME" : os.environ["KRB5CCNAME"] } }
        remote_account = ComponentProxy("ufoaccount.account.Account", meta, config.sync_host)
        remote_account.block_user(self.following)


class AcceptedFriendshipNotification(NotificationDocument):

    subtype = TextField(default="AcceptedFriendship")

    following = TextField()
    follower  = TextField()

    actions = DictField(Mapping.build(
                  proceed_pending_shares = TextField(default=_("Ok"))))

    def __init__(self, **fields):
        super(AcceptedFriendshipNotification, self).__init__()

        if fields.get('following') and fields.get('follower'):
          self.following = fields['following']
          self.follower  = fields['follower']

          fullname = utils.get_user_infos(self.following)['fullname']

          self.title   = _('Friendship invitation accepted')
          self.body    = _('%s has accepted your friendship invitation, '
                           'you can now share some document with him/her.') % fullname
          self.summary = _("Friend invitation accepted (%s)") % fullname

    def proceed_pending_shares(self):
        self.debug("Proceed pending shares from '%s' to '%s'"
                   % (self.following, self.follower))

        meta = { "apache_env" : { "KRB5CCNAME" : os.environ["KRB5CCNAME"] } }
        remote_sync = ComponentProxy("ufosync.sync.Sync", meta, config.sync_host)
        remote_sync.proceed_pending_shares(self.following)


class CanceledFriendshipNotification(NotificationDocument):

    subtype = TextField(default="CanceledFriendship")

    following = TextField()

    def __init__(self, **fields):
        super(CanceledFriendshipNotification, self).__init__()

        if fields.get('following'):
          self.following = fields['following']

          fullname = utils.get_user_infos(self.following)['fullname']

          self.title   = _('A friendship has been canceled')
          self.body    = _('%s has remove you from his friend list, '
                           'you can not access to his files any more.') % fullname
          self.summary = _("Friendship canceled (%s)") % fullname


class NewShareNotification(NotificationDocument):

    subtype = TextField(default="NewShare")

    following = TextField()
    filepath  = TextField()

    def __init__(self, **fields):
        super(NewShareNotification, self).__init__()

        if fields.get('following') and fields.get('filepath'):
          self.following = fields['following']
          self.filepath  = fields['filepath']

          fullname = utils.get_user_infos(self.following)['fullname']

          self.title   = _('A new file has been shared')
          self.body    = _('A new file \'%s\' has been shared by %s.') \
                           % (os.path.basename(self.filepath), fullname)
          self.summary = _("New file shared (%s)") % fullname


class CanceledShareNotification(NotificationDocument):

    subtype = TextField(default="CanceledShare")

    following = TextField()
    filepath  = TextField()

    def __init__(self, **fields):
        super(CanceledShareNotification, self).__init__()

        if fields.get('following') and fields.get('filepath'):
          self.following = fields['following']
          self.filepath  = fields['filepath']

          fullname = utils.get_user_infos(self.following)['fullname']

          self.title   = _('A share has been canceled')
          self.body    = _('%s has canceled the share of \'%s\', '
                           'so you can\'t access the file any more.') \
                           % (fullname, os.path.basename(self.filepath))
          self.summary = _("Share canceled (%s)") % fullname
