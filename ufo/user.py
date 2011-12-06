import os
from new import instancemethod
from ufo.database import DocumentHelper
from ufo.constants import Notification, FriendshipStatus
from ufo.sharing import FriendDocument
from ufo.debugger import Debugger
from ufo.errors import *

class FriendFilter:
    def __init__(self, key="login", **kw):
        self.kw = kw
        self.key = key

    def __call__(self, *args):
        def friend_filter_func(_self):
            items = { }
            for login, friend in _self.contacts.items():
                match = True
                for key, value in self.kw.items():
                    if getattr(friend, key) != value:
                        match = False
                        break

                if match:
                    items[getattr(friend, self.key)] = friend

            return items
        return friend_filter_func

class Friend(Debugger):
    def __init__(self, doc):
        self.doc = doc

    def __getattr__(self, attr):
        return getattr(self.doc, attr)

    def __setattr__(self, attr, value):
        if hasattr(FriendDocument, attr):
            setattr(self.doc, attr, value)
        else:
            self.__dict__[attr] = value

    def __getitem__(self, index):
        return self.doc[index]

    def __setitem__(self, index, value):
        self.doc[index] = value

    def __repr__(self):
        return self.login

class User(Friend):
    _user_cache = {}
    _contacts = None

    def __init__(self, db, login, dry_run=False, reuse_cache=False):
        if not login:
            raise Exception("You need to specify a login")

        if not reuse_cache:
            self._user_cache = {}

        friend_helper = DocumentHelper(FriendDocument, db)
        document = self._user_cache.get(login)
        if not document:
            document = friend_helper.by_login(key=login, pk=True)
            self._user_cache[login] = document
        Friend.__init__(self, document)

        self.login = login
        self.friend_helper = friend_helper

        from ufo.filesystem import SyncDocument
        self.sync_helper = DocumentHelper(SyncDocument, db)

        if dry_run:
            def harmless_create(*args, **kw):
                return dict(**kw)

            def harmless_update(*args, **kw):
                pass

            def harmless_delete(*args, **kw):
                pass

            for helper in (self.friend_helper, self.sync_helper):
                helper.create = instancemethod(harmless_create, helper)
                helper.update = instancemethod(harmless_update, helper)
                helper.delete = instancemethod(harmless_delete, helper)

    def request_friend(self, friend):
        friendship_status = self.get_friendship_status(friend)

        if friendship_status == FriendshipStatus.BLOCKED_USER:
            raise BlockedUserError()

        elif friendship_status == FriendshipStatus.PENDING_FRIEND:
            raise PendingFriendError()

        elif friendship_status == FriendshipStatus.FRIEND:
            raise AlreadyFriendError()

        elif friendship_status == FriendshipStatus.NONE_FRIEND:
            new_friend = self.create_friend(friend, FriendshipStatus.PENDING_FRIEND)
            self.contacts[friend] = new_friend
            return new_friend

        else:
            raise BadFriendshipStatus()

    def create_friend(self, friend, status):
        document = self.friend_helper.create(login=unicode(friend),
                                             status=status)
        self._user_cache[friend] = document
        return Friend(document)

    def remove_friend(self, friend):
        friendship_status = self.get_friendship_status(friend)

        if friendship_status in (FriendshipStatus.FRIEND, FriendshipStatus.PENDING_FRIEND):
            self.friend_helper.delete(self.contacts[friend])
            if self._user_cache.has_key(friend):
                del self._user_cache[friend]
        else:
            raise BadFriendshipStatus()

    def get_friendship_status(self, friend):
        """
        @return: 
        - FriendshipStatus.BLOCKED_USER :
              if 'user' is in the blocked users list of 'friend' or if
              'friend' is in the blocked users list of 'user'

        - FriendshipStatus.NONE_FRIEND :
              if neither 'friend' is in the 'pending friends' list
              nor in the 'friends' list of 'user'. We also do not have the
              BLOCKED_USER status. NONE_FRIEND status means that 'friend' can
              be a new friend of 'user'.

        - FriendshipStatus.PENDING_FRIEND :
              if 'friend' is in the 'pending friends' list of 'user'.

        - FriendshipStatus.FRIEND :
              if 'friend' is in the 'friends' list of 'user'.
        """

        if friend == "public":
            self.debug("everyone is a friend of public")
            return FriendshipStatus.FRIEND

        if friend == self.login:
            raise BadFriendshipStatus()

        if self.blocked_users.has_key(friend):
            self.debug('return FriendshipStatus.BLOCKED_USER')
            return FriendshipStatus.BLOCKED_USER

        elif (not self.pending_friends.has_key(friend)
              and not self.friends.has_key(friend)):
            self.debug('return FriendshipStatus.NONE_FRIEND')
            return FriendshipStatus.NONE_FRIEND

        elif self.pending_friends.has_key(friend):
            self.debug('return FriendshipStatus.PENDING_FRIEND')
            return FriendshipStatus.PENDING_FRIEND

        elif self.friends.has_key(friend):
            self.debug('return FriendshipStatus.FRIEND')
            return FriendshipStatus.FRIEND
        else:
            raise BadFriendshipStatus()

    def accept_friend(self, friend):
        self.create_friend(friend, FriendshipStatus.FRIEND)

    def notify(self, type, initiator, **kw):
        DocumentHelper(type, self.login).create(initiator=initiator, target=self.login, **kw)

    def dismiss(self, notification):
        from ufo.notify import NotificationDocument
        DocumentHelper(NotificationDocument, self.login).delete(notification)

    def process_pending_shares(self, friend):
        # TODO: Use View Collation
        # TODO: Fix ACL applying
        import posix1e
        pending_friend = self.friends[friend]
        for share in pending_friend.pending_shares:
            file = self.sync_helper[share]
            new_acl = posix1e.ACL(text=str(file.posix_acl))
            ace = new_acl.append()
            ace.tag_type = posix1e.ACL_USER
            if "R" in share.permissions:
                ace.permset.read = True
            if "W" in share.permissions:
                ace.permset.write = True
            ace._qualifier = get_user_infos(login=friend)['uid']
            # new_acl.applyto(self.get_file_path(file.path))

        pending_friend.pending_shares = []
        self.friend_helper.update(pending_friend)

    def refuse_friend(self, friend):
        if self.pending_friends.has_key(friend):
            doc = self.pending_friends[friend]
            self.friend_helper.delete(doc)
            del self.contacts[friend]
        else:
            raise BadFriendshipStatus()

    def block_user(self, user):
        if self.contacts.has_key(user):
            self.contacts[user].status = FriendshipStatus.BLOCKED_USER
            self.friend_helper.update(self.contacts[user])
        else:
            self.contacts[user] = self.create_friend(user, FriendshipStatus.BLOCKED_USER)

    @property
    def fs(self):
        pass

    @property
    def contacts(self):
        if not self._contacts:
            contacts = {}
            for doc in self.friend_helper.by_login():
                self._user_cache[doc.login] = doc
                contacts[doc.login] = Friend(doc)
            self._contacts = True
            return contacts
        else:
            return self._user_cache

    @property
    @FriendFilter(status=FriendshipStatus.PENDING_FRIEND)
    def pending_friends(self): pass

    @property
    @FriendFilter(status=FriendshipStatus.FRIEND)
    def friends(self): pass

    @property
    @FriendFilter(status=FriendshipStatus.BLOCKED_USER)
    def blocked_users(self): pass

    @property
    @FriendFilter(key='uid')
    def friends_id(self): pass

class LazyUser:
    def __getattr__(self, attr):
        login = os.environ.get("REMOTE_USER", os.environ.get("USER"))
        return getattr(User(db=DocumentHelper(FriendDocument, login).database,
                            login=login, reuse_cache=True),
                       attr)

user = LazyUser()
