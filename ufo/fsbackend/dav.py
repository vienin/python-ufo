import os
import urlparse
import urllib
import errno
import httplib
import simplejson
import base64
import pwd

import ufo.acl as acl
import ufo.auth
from ufo.fsbackend import GenericFileSystem
from ufo.utils import MutableStat

from webdav.WebdavResponse import PropertyResponse
from webdav import WebdavClient
from webdav.acp.Acl import ACL
from webdav.Constants import *

NS_MY= 'http://my.agorabox.org'
PRINCIPALS_BASE= '/webdav/_users/'
PRINCIPALS_ALL= '/webdav/_userdb/'

dav_errors_mappings = {
    401: errno.EPERM,
    403: errno.EPERM,
    404: errno.ENOENT,
    501: errno.EAGAIN
}

def davexcept_to_errno(func):
    def try_dav(*args, **kw):
        try:
            return func(*args, **kw)
        except WebdavClient.WebdavError, e:
            err = dav_errors_mappings.get(e.code, errno.EINTR)
            if err == errno.EINTR:
                raise
            raise OSError(err, str(e))

    return try_dav

class ChangeAcl(object):
    def __init__(self, switch=TAG_GRANT, _acl=[]):
        self.aceText= {}
        self.acl=_acl
        for ace in self.acl:
            if ace.kind == acl.ACL_USER:
                name = ace.qualifier
            elif ace.kind == acl.ACL_USER_OBJ:
                name = "owner"
            elif ace.kind == acl.ACL_OTHER:
                name = "all"
            else:
                continue
            if not ace._perms:
                continue
            text = '<D:%s>\n' % TAG_ACE
            text += '<D:%s><D:%s>%s</D:%s></D:%s>\n' % (TAG_PRINCIPAL, TAG_HREF, PRINCIPALS_BASE + name, TAG_HREF, TAG_PRINCIPAL)
            text += '<D:%s>' % switch
            if ace._perms & acl.ACL_READ:
                text += '<D:%s><D:%s /></D:%s>' % (TAG_PRIVILEGE, TAG_READ, TAG_PRIVILEGE)
            if ace._perms & acl.ACL_WRITE:
                text += '<D:%s><D:%s /></D:%s>' % (TAG_PRIVILEGE, TAG_WRITE, TAG_PRIVILEGE)
            text += '</D:%s>' % switch
            text += '</D:%s>\n' % TAG_ACE
            self.aceText[name]= text


class GrantAcl(ChangeAcl):
    def __init__(self, *names):
        ChangeAcl.__init__(self, TAG_GRANT, *names)

    def toXML(self):
        return '<D:%s xmlns:D="DAV:">' % TAG_ACL + \
            reduce(lambda l,r: l+r+'\n', self.aceText.values()) + \
            '</D:%s>' % TAG_ACL


class WebDAVFile:
    def __init__(self, resource, flags, mode):
        self.flags = flags
        self.mode = mode
        self.offset = 0
        self.resource = resource

    def seek(self, offset, whence=0):
        if whence == 0:
            self.offset = offset
        elif whence == 1:
            self.offset += offset
        else:
            self.offset = self.size - offset

    @property
    def size(self):
        return 0

    @davexcept_to_errno
    def write(self, data):
        length = len(data)
        extra_hdrs= { "Content-Range" : "bytes %d-%d/%d" % (self.offset, self.offset + length, self.size) }
        self.resource.uploadContent(data, extra_hdrs=extra_hdrs)
        self.offset += length
        return length

    @davexcept_to_errno
    def read(self, length=None):
        headers = {}
        if length:
            headers["Range"] = "bytes=%d-%d" % (self.offset, self.offset + length)
        try:
            data = self.resource.downloadContent(headers).read(length)
        except httplib.IncompleteRead, e:
            return e.partial
        self.offset += len(data)
        return data

    def close(self):
        pass


class WebDAVFileSystem(GenericFileSystem):
    def __init__(self, url, auth=None):
        self.url = url
        self.client = WebdavClient.CollectionStorer(url)
        self.connection = self.client.connection
        self.locks = {}
        if auth:
            auth.bind(self.connection, "webdav")

    def real_path(self, path):
        return path

    @staticmethod
    def _document_to_headers(document):
        headers = {}
        if document:
            headers["Sync-Document"] = base64.b64encode(simplejson.dumps(document._to_json(document)))
        return headers

    @davexcept_to_errno
    def mkdir(self, path, mode, document=None, *args, **kw):
        col = WebdavClient.CollectionStorer(self.url + os.path.dirname(path), self.connection)
        col.addCollection(os.path.basename(path), extra_hdrs=self._document_to_headers(document))

    @davexcept_to_errno
    def rmdir(self, path, *args, **kw):
        col = WebdavClient.CollectionStorer(self.url + os.path.dirname(path), self.connection)
        col.deleteResource(os.path.basename(path))

    @davexcept_to_errno
    def unlink(self, path, *args, **kw):
        col = WebdavClient.CollectionStorer(self.url + os.path.dirname(path), self.connection)
        col.deleteResource(os.path.basename(path))

    @davexcept_to_errno
    def lstat(self, path):
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        stats = MutableStat()
        for item in storer.readProperty(NS_MY, "stats").children:
            if item.name.endswith("time"):
                setattr(stats, item.name, float(item.textof()))
            else:
                setattr(stats, item.name, int(item.textof()))
        return stats

    @davexcept_to_errno
    def chmod(self, path, mode):
        pass

    @davexcept_to_errno
    def utime(self, path, times):
        # TODO
        pass

    @davexcept_to_errno
    def copy(self, src, dest, document=None):
        storer = WebdavClient.ResourceStorer(self.url + dest, self.connection)
        storer.uploadFile(src, extra_hdrs=self._document_to_headers(document))

    def get_mime_type(self, path):
        raise Exception("Not implemented")

    @davexcept_to_errno
    def set_acl(self, path, posix_acl):
        users = []
        webdav_acl = GrantAcl(posix_acl)
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        storer.setAcl(webdav_acl)

    @davexcept_to_errno
    def get_acl(self, path):
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        storer.getAcl()

    @davexcept_to_errno
    def rename(self, old, new):
        storer = WebdavClient.ResourceStorer(self.url + old, self.connection)
        storer.move(self.url + new)

    @davexcept_to_errno
    def symlink(self, src, dst, document=None):
        storer = WebdavClient.ResourceStorer(self.url + dst, self.connection)
        storer.mkRedirectRef(self.url + src, extra_hdrs=self._document_to_headers(document))

    @davexcept_to_errno
    def open(self, path, flags, mode=0700):
        return WebDAVFile(WebdavClient.ResourceStorer(self.url + path, self.connection), flags, mode)

    @davexcept_to_errno
    def ftruncate(self, path, length):
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        storer.writeProperties({ (NS_MY, "size") : str(length) })

    @davexcept_to_errno
    def lock(self, path):
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        lock = storer.lock(PRINCIPALS_BASE + str(os.getuid()))
        self.locks[path] = lock
        return lock

    @davexcept_to_errno
    def unlock(self, path):
        storer = WebdavClient.ResourceStorer(self.url + path, self.connection)
        lock = self.locks.get(path)
        if lock:
            del self.locks[path]
            return storer.unlock(lock)

    def setxattr(self, path, key, value):
        raise Exception("Not implemented")

    def removexattr(self, path, key):
        raise Exception("Not implemented")

    def getxattr(self, path, key):
        raise Exception("Not implemented")

