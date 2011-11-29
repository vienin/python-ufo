import unittest
from ufo.views import *
from ufo.filesystem import *
from ufo.acl import *
from ufo.user import *

def setup_db():
    helper = DocumentHelper(FriendDocument, "test_friends")
    helper.sync()
    friend = helper.create(login="john",
                           uid=123456,
                           gid=123456,
                           firstname="John",
                           lastname="Doe")

class FriendsTestCase(unittest.TestCase):
    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self.helper = DocumentHelper(FriendDocument, "test_friends")

    def test_user(self):
        user = User(self.helper.database, login="john")
        assert user.firstname == "John"
        
    def test_friends(self):
        user = User(self.helper.database, login="john")
        user.create_friend("sam", FriendshipStatus.PENDING_FRIEND)
        assert user.pending_friends["sam"].status == FriendshipStatus.PENDING_FRIEND

        user.create_friend("ken", FriendshipStatus.FRIEND)
        assert user.friends["ken"].status == FriendshipStatus.FRIEND

setup_db()
suite = unittest.TestLoader().loadTestsFromTestCase(FriendsTestCase)

if __name__ == '__main__':
    unittest.main()
