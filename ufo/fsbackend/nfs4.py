import subprocess
from ufo.fsbackend import GenericFileSystem

patched_acl = False

class NFS4FileSystem(GenericFileSystem):
    def set_acl(self, path, acl):
        if patched_acl:
            # We just set the whole set of ACL's on the remote file by using... setfacl
            # NFSv4 uses special ACLs so we need a patched version of getfacl/setfacl
            input = "# file: %s\n# owner: %s\n# group: %s\n%s\n" % \
                    (path, user.login, user.login, repr(acl))
            process = subprocess.Popen([ "setfacl", "--restore=-" ],
                                       stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            _, err = process.communicate(input)

        else:
            # TODO: Convert the POSIX ACL to an NFS4 ACL using Python bindings
            process = subprocess.Popen([ "nfs4_setfacl", "-S", "-", self.real_path(path) ],
                                       stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            _, err = process.communicate(acl.to_nfs4())

        if err:
            raise OSError(process.returncode, err)

    def setxattr(self, path, key, value):
        # Doing nothing
        pass

    def removexattr(self, path, key):
        # Doing nothing
        pass

    def getxattr(self, path, key):
        # Doing nothing
        pass

    def check(self):
        if self.pingServerOK() and os.path.ismount(self.mount_point):
            return True

        return False

