import unittest
from ufo.views import *
from ufo.filesystem import *
from ufo.acl import *

JOHN_ID = 123456

class FileSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.fs = fs = CouchedFileSystem("/tmp", "test_fs")
        fs.doc_helper.sync()

        if not fs.exists("/test"):
            fs.mkdir("/test")
        f = fs.open("/test/image.png", os.O_CREAT | os.O_WRONLY)
        f.close()
        f = self.fs["/test/image.png"]
        f.stats.st_size = 1000
        self.fs.doc_helper.update(f)

    def test_acl(self):
        f = self.fs["/test/image.png"]
        posix_acl = f.posix_acl
        posix_acl.append(ACE(ACL_USER, ACL_READ, JOHN_ID))
        f.acl = posix_acl.to_json()
        self.fs.doc_helper.update(f)

    def test_df(self):
        assert self.fs.du("/test") == 1000

suite = unittest.TestLoader().loadTestsFromTestCase(FileSystemTestCase)

if __name__ == '__main__':
    unittest.main()
