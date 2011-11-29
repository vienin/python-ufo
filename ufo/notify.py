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
import os
from datetime import datetime
import new
from gettext import dgettext

from ufo.debugger import Debugger
from ufo.constants import ShareDoc
from ufo.database import *
from ufo.utils import get_user_infos
from ufo.user import user

class TranslatableText:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return dgettext("python-ufo", self.text)

def _(message):
    return TranslatableText(message)

class action:
    def __init__(self, description):
        self.description = description

    def __call__(self, func):
        func.action = True
        func.description = self.description
        return func

class NotificationDocument(Document, Debugger):

    doctype   = TextField(default="NotificationDocument")
    subtype   = TextField(default="")
    date      = DateTimeField(default=datetime.now)
    initiator = TextField()
    target    = TextField()

    by_id = ViewField('notification',
                      language = 'javascript',
                      map_fun = "function (doc) {" \
                                  "if (doc.doctype === 'NotificationDocument') {" \
                                    "emit(doc._id, doc);" \
                                  "}" \
                                "}")

    by_subtype_and_initiator = ViewField('notification',
                                         language = 'javascript',
                                         map_fun = "function (doc) {" \
                                                     "if (doc.doctype === 'NotificationDocument' && doc.subtype && doc.initiator) {" \
                                                       "emit([doc.subtype, doc.initiator], doc);" \
                                                     "}" \
                                                   "}")

    def __init__(self, **fields):
        super(NotificationDocument, self).__init__()

        if fields.get('initiator') and fields.get('target'):
          self.initiator = fields['initiator']
          self.target  = fields['target']

    @action(_("Dismiss"))
    def dismiss(self):
        user.dismiss(self)

    def __getitem__(self, key):
        try:
            value = getattr(self, "pretty_" + key)
        except:
            try:
                value = getattr(self, key)
            except:
                value = super(Document, self).__getitem__(key)
        if isinstance(value, TranslatableText):
            return repr(value)
        else:
            return value

    @property
    def fullname(self):
        return get_user_infos(login=self.initiator)['fullname']

    @property
    def actions(self):
        actions = {}
        for k, v in self.__class__.__dict__.items():
            if type(v) == new.function and getattr(v, "action", False):
                actions[k] = repr(v.description)
        return actions

    @property
    def default_action(self):
        for action in self.actions.values():
            if getattr(getattr(self, action), "default", False):
                return action
        return "dismiss"

class NewFriendshipNotification(NotificationDocument):

    subtype = TextField(default="NewFriendship")

    title   = _('New friendship invitation')
    body    = _('You have been invited by %(fullname)s to be his/her friend.')
    summary = _("%(fullname)s wants to be your friend")

    def __init__(self, **fields):
        super(NewFriendshipNotification, self).__init__()

        if fields.get('initiator') and fields.get('target'):
          self.initiator = fields['initiator']
          self.target  = fields['target']

    @action(_("Accept"))
    def accept_invitation(self):
        self.debug("Accepting the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.accept_friend(self.initiator)

    @action(_("Refuse"))
    def refuse_invitation(self):
        self.debug("Refusing the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.refuse_friend(self.initiator)

    @action(_("Block user"))
    def block_invitation(self):
        self.debug("Blocking the friend invitation from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.block_user(self.initiator)


class FollowRequestNotification(NotificationDocument):

    subtype = TextField(default="FollowRequest")

    title   = _('New file sharing request')
    body    = _('%(fullname)s would like to be in your followers list.')
    summary = _("%(fullname)s wants to follow you")

    @action(_("Accept"))
    def accept_invitation(self):
        self.debug("Accepting the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.accept_following(self.initiator)

    @action(_("Refuse"))
    def refuse_invitation(self):
        self.debug("Refusing the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.refuse_following(self.initiator)

    @action(_("Block user"))
    def block_invitation(self):
        self.debug("Blocking the follow request from '%s' to '%s'"
                   % (self.initiator, self.target))

        user.block_user(self.initiator)


class AcceptedFriendshipNotification(NotificationDocument):

    subtype = TextField(default="AcceptedFriendship")

    title   = _('Friendship invitation accepted')
    body    = _('%(fullname)s has accepted your friendship invitation, '
                'you can now share some document with him/her.')
    summary = _("%(fullname)s has accepted your invitation")

    @action
    def accept_friend(self):
        self.debug("Proceed pending shares from '%s' to '%s'" % (self.initiator, self.target))
        # user.accept_friend(self.initiator)


class CanceledFriendshipNotification(NotificationDocument):

    subtype = TextField(default="CanceledFriendship")

    title   = _('A friendship has been canceled')
    body    = _('%(fullname)s has removed you from his friend list, '
                'you can not access his files any more.')
    summary = _("%(fullname)s has canceled his friendship with you")


class RefusedFriendshipNotification(NotificationDocument):

    subtype = TextField(default="RefusedFriendship")

    title   = _('%(fullname)s has refused your friend request')
    body    = _('%(fullname)s would rather be stranger than friends.')
    summary = _("%(fullname)s has refused your friend request")


class NewShareNotification(NotificationDocument):

    subtype = TextField(default="NewShare")
    files     = ListField(TextField())

    title   = _('Someone has shared some files with you')
    body    = _('%(fullname)s has shared the following files with you : %(files)s')
    summary = _("%(fullname)s has shared some files with you")

    def __init__(self, **fields):
        super(NewShareNotification, self).__init__(**fields)

        if fields.get('files'):
          self.files  = fields['files']


class CanceledShareNotification(NotificationDocument):

    subtype = TextField(default="CanceledShare")
    files     = ListField(TextField())

    title   = _('A share has been canceled')
    body    = _('%(fullname)s has canceled the share of \'%(file)s\', '
                'you can\'t access the file any more.')
    summary = _("%(fullname)s has canceled a share with you")

    def __init__(self, **fields):
        super(CanceledShareNotification, self).__init__()

        if fields.get('files'):
          self.files  = fields['files']
