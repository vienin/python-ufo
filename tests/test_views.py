import unittest
from ufo.views import *
from ufo.filesystem import *
from ufo.acl import *

JOHN_ID = 123456

def setup_db():
    fs = CouchedFileSystem("/tmp", "test_views")
    fs.doc_helper.sync()

    f = fs.open("/image.png", os.O_CREAT | os.O_WRONLY)
    f.close()
    f = fs["/image.png"]
    f.type = "image/png"
    f.tags = [ "pictures" ]
    f.stats.st_uid = -1
    posix_acl = f.posix_acl
    posix_acl.append(ACE(ACL_USER, ACL_READ, JOHN_ID))
    f.acl = posix_acl.to_json()
    fs.doc_helper.update(f)

    f = fs.open("/movie.avi", os.O_CREAT | os.O_WRONLY)
    f.close()
    f = fs["/movie.avi"]
    f.uid = JOHN_ID
    f.type = "video/avi"
    posix_acl = f.posix_acl
    posix_acl.append(ACE(ACL_USER, ACL_READ, -1))
    f.acl = posix_acl.to_json()
    fs.doc_helper.update(f)

class ViewTestCase(unittest.TestCase):
    def setUp(self):
        self.helper = DocumentHelper(self.view_class, "test_views")
        self.helper.sync()

class ByTypeTestCase(ViewTestCase):
    view_class = SortedByTypeSyncDocument

    def test_root(self):
        assert list(self.helper.getDocuments())[0].filename == "image"

    def test_type(self):
        assert list(self.helper.getDocuments("image"))[0].filename == "png"

class ByTagTestCase(ViewTestCase):
    view_class = TaggedSyncDocument

    def test_root(self):
        assert list(self.helper.getDocuments())[0].filename == "pictures"

    def test_type(self):
        assert list(self.helper.getDocuments("pictures"))[0].filename == "image.png"

class MySharesTestCase(ViewTestCase):
    view_class = MySharesSyncDocument

    def test_root(self):
        assert list(self.helper.getDocuments())[0].filename == "nobody"

    def test_user(self):
        assert list(self.helper.getDocuments(JOHN_ID))[0].filename == "image.png"

class BuddySharesTestCase(ViewTestCase):
    view_class = BuddySharesSyncDocument

    def test_root(self):
        assert list(self.helper.getDocuments())[0].filename == "nobody"

    def test_user(self):
        assert list(self.helper.getDocuments(JOHN_ID))[0].filename == "movie.avi"

setup_db()
suite = unittest.TestLoader().loadTestsFromTestCase(MySharesTestCase)

if __name__ == '__main__':
    unittest.main()
