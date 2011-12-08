import os
import threading
import errno
import shutil

from ufo.debugger import Debugger
from ufo.utils import MimeType

class FSMountError(Exception):
  pass

class GenericFileSystem(Debugger):
    _fileLocks = {}

    _serverIp   = None
    _serverPort = None

    def __init__(self, mount_point):
        self.mount_point = mount_point

    def real_path(self, path):
        return os.path.join(self.mount_point, path[1:])

    def flags_to_stdio(self, flags):
        if flags & os.O_RDWR:
            if flags & os.O_APPEND:
                result = 'a+'
            else:
                result = 'w+'
      
        elif flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                result = 'a'
            else:
                result = 'w'
      
        else: # O_RDONLY
            result = 'r'

        try:
            if flags & os.O_BINARY:
                result += 'b'
        except AttributeError, e:
            # os.O_BINARY only exists on Windows
            pass

        return result

    def lstat(self, path):
        return os.lstat(self.real_path(path))

    def mkdir(self, path, mode):
        return os.mkdir(self.real_path(path), mode)

    def rmdir(self, path):
        return os.rmdir(self.real_path(path))

    def rmtree(self, path, ignore_errors=False):
        shutil.rmtree(self.real_path(path), ignore_errors=ignore_errors)

    def unlink(self, path):
        return os.unlink(self.real_path(path))

    def symlink(self, dest, symlink):
        return os.symlink(dest, self.real_path(symlink))

    def chmod(self, path, mode):
        return os.chmod(self.real_path(path), mode)

    def chown(self, path, uid, gid):
        return os.chown(self.real_path(path), uid, gid)

    def utime(self, path, times):
        return os.utime(self.real_path(path), times)

    def open(self, path, flags, mode=0700):
        fd = os.open(self.real_path(path), flags, mode)
        return os.fdopen(fd, self.flags_to_stdio(flags))

    def get_mime_type(self, path):
        return MimeType(self.real_path(path))

    def removexattr(self, path, key):
        import xattr
        return xattr.removexattr(self.real_path(path), key)

    def rename(self, old, new):
        return os.rename(self.real_path(old), self.real_path(new))

    def setxattr(self, path, key, value):
        import xattr
        return xattr.setxattr(self.real_path(path), key, value)

    def lockFile(self, filename):
        '''
        Method to lock a file. Blocks if the file is already locked.

        Args:
          filename: The full pathname of the file to lock.

        Returns:
          A boolean value.
        '''

        try:
            lock = self._fileLocks[filename]
        except KeyError:
            lock = self._fileLocks.setdefault(filename, threading.RLock())

        lock.acquire()

    def unlockFile(self, filename):
        '''
        Method to unlock a file.

        Args:
          filename: The full pathname of the file to unlock.

        Returns:
          A boolean value.
        '''

        self._fileLocks[filename].release()

    def check(self):
        os.access(self.mount_point)

