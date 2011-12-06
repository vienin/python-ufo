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

'''UFO file synchronization client library.'''

import os
import stat
import errno
import shutil
import difflib

# Fuse paths are UNIX-like whatever the operating system
import posixpath

from ufo.utils import MutableStat, CacheDict, get_user_infos
from ufo.debugger import Debugger
from ufo.database import *
import ufo.acl as acl

def _wrap_bypass(row):
    return row

def normpath(func):
    def handler(self, path, *args, **kw):
        return func(self, posixpath.normpath(path), *args, **kw)
    return handler

def norm2path(func):
    def handler(self, path, path2, *args, **kw):
        return func(self, posixpath.normpath(path), posixpath.normpath(path2), *args, **kw)
    return handler

class SyncDocument(UTF8Document):

    doctype  = TextField(default="SyncDocument")
    filename = TextField()
    dirpath  = TextField()
    type     = TextField()
    stats    = DictField(Mapping.build(
                   st_atime   = FloatField(),
                   st_ctime   = FloatField(),
                   st_gid     = IntegerField(),
                   st_mode    = IntegerField(),
                   st_mtime   = FloatField(),
                   st_size    = LongField(),
                   st_uid     = IntegerField()))
    xattrs   = DictField()
    acl      = ListField(DictField())

    # TODO: Use a dedicated document class for tags
    tags = ListField(TextField())

    def __init__(self, **fields):
        super(SyncDocument, self).__init__(**fields)

        # Handle the virtual properties like 'mode' and 'uid'
        for key, value in fields.items():
            if key not in SyncDocument.stats.mapping._fields.keys():
                setattr(self, key, value)

        if fields.has_key("stats"):
            self.set_stats(fields["stats"])

    def set_stats(self, stat_result):
        for field in SyncDocument.stats.mapping._fields.keys():
            if isinstance(stat_result, dict):
                self.stats[field] = stat_result[field]
            else:
                if hasattr(stat_result, field):
                    self.stats[field] = getattr(stat_result, field)
  
    def get_stats(self):
        stat_result = MutableStat()
        for field in SyncDocument.stats.mapping._fields.keys():
            # if field in ['st_uid', 'st_gid', 'st_mode']:
            #     setattr(stat_result, field, getattr(self, field[3:]))
            if field == 'st_ino' and self.id:
                setattr(stat_result, field, int(self.id[16:], 16))
            else:
                setattr(stat_result, field, getattr(self.stats, field))
    
        return stat_result

    def add_tag(self, tag):
      if tag not in self.tags:
        self.tags.append(tag)

    def del_tag(self, tag):
      if tag in self.tags:
        self.tags.remove(tag)

    def __getattr__(self, attr):
        st_attr = "st_" + attr
        if SyncDocument.stats.mapping._fields.has_key(st_attr):
            return self.stats[st_attr]
        else:
            return self.__dict__[attr]

    def __setattr__(self, attr, value):
        if attr == "stats" and type(value) != dict:
            stat_result = {}
            for field in SyncDocument.stats.mapping._fields.keys():
                 stat_result[field] = getattr(value, field)
            value = stat_result
        else:
            st_attr = "st_" + attr
            if SyncDocument.stats.mapping._fields.has_key(st_attr):
                self.stats[st_attr] = value
                return

        object.__setattr__(self, attr, value)

    @property
    def posix_acl(self):
       if self.acl:
           return acl.ACL.from_json(self.acl, self.mode)

       return acl.ACL.from_mode(self.mode)

    def __str__(self):
        return ('<%s id:%s path:%s type:%s>'
                % (self.doctype,
                   self.id,
                   posixpath.join(self.dirpath, self.filename),
                   self.type))

    def __repr__(self):
        return str(self)

    @property
    def path(self):
        return posixpath.join(self.dirpath, self.filename)

    @property
    def gecos(self):
        if self.type == "application/x-directory":
            return get_user_infos(uid=self.uid)['fullname']
        else:
            return ""

    def isdir(self):
        return stat.S_ISDIR(self.mode)

    def islink(self):
        return stat.S_ISLNK(self.mode)

    def isfile(self):
        return stat.S_ISREG(self.mode)

    by_path = ViewField('syncdocument',
                        language = 'javascript',
                        map_fun = "function (doc) {" \
                                    "if (doc.doctype === 'SyncDocument') {" \
                                      "if (doc.dirpath === '/') {" \
                                        "emit('/' + doc.filename, doc);" \
                                      "} else {" \
                                        "emit(doc.dirpath + '/' + doc.filename, doc);" \
                                      "}" \
                                    "}" \
                                  "}")

    by_type = ViewField('syncdocument',
                        language = 'javascript',
                        map_fun = "function (doc) {" \
                                    "if (doc.doctype === 'SyncDocument' && doc.type != 'application/x-directory') {" \
                                      "emit(doc.type.split('/'), doc);" \
                                    "}" \
                                  "}",
                        reduce_fun = "_count",
                        reduce = False,
                        wrapper = _wrap_bypass)

    by_dir = ViewField('syncdocument',
                       language = 'javascript',
                       map_fun = "function (doc) {" \
                                   "if (doc.doctype === 'SyncDocument') {" \
                                     "emit(doc.dirpath, doc);" \
                                   "}" \
                                 "}")

    by_dir_prefix = ViewField('syncdocument',
                              language = 'javascript',
                              map_fun = "function (doc) {" \
                                          "if (doc.doctype === 'SyncDocument') {" \
                                            "var last = '';" \
                                            "var current = doc.dirpath;" \
                                            "while (current !='/' && current != last) {" \
                                              "emit(current, doc);" \
                                              "current = current.slice(0, current.lastIndexOf('/'));" \
                                            "}" \
                                          "}" \
                                        "}",
                              reduce_fun = "function (keys,values,rereduce) {" \
                                             "if(rereduce == false) {" \
                                               "var size = 0;" \
                                               "for (var i = 0; i<values.length; i++) {" \
                                                 "if (values[i].stats)" \
                                                   "size += values[i].stats.st_size;" \
                                               "}" \
                                               "return size;" \
                                             "}" \
                                             "else {" \
                                               "return sum(values);" \
                                             "}" \
                                           "}",
                              reduce = False,
                              wrapper = _wrap_bypass)

    by_tag = ViewField('syncdocument',
                       language = 'javascript',
                       map_fun = "function (doc) {" \
                                   "if (doc.doctype === 'SyncDocument' && doc.tags) {" \
                                     "for (var i=0; i<doc.tags.length; i++) {" \
                                       "emit([doc.tags[i], doc.stats.st_uid], doc);" \
                                     "}" \
                                   "}" \
                                 "}",
                       reduce_fun = "_count",
                       reduce = False,
                       wrapper = _wrap_bypass)

    by_keyword = ViewField('syncdocument',
                       language = 'javascript',
                       map_fun = "function (doc) {" \
                                   "if (doc.doctype === 'SyncDocument') {" \
                                     "for (var i=0; i<doc.filename.length-2; i++) {" \
                                       "emit(doc.filename.slice(i).toLowerCase(), doc);" \
                                     "}" \
                                   "}" \
                                 "}")

    by_provider_and_participant = ViewField('syncdocument',
                                            language = 'javascript',
                                            map_fun = "function (doc) {" \
                                                        "if (doc.doctype === 'SyncDocument' && doc.acl) {" \
                                                          "for (var i=0; i<doc.acl.length; i++) {" \
                                                            "if (doc.dirpath === '/') {" \
                                                              "emit([doc.stats.st_uid, doc.acl[i].qualifier, doc.dirpath+doc.filename], doc);" \
                                                            "} else {" \
                                                              "emit([doc.stats.st_uid, doc.acl[i].qualifier, doc.dirpath+'/'+doc.filename], doc);" \
                                                            "}" \
                                                          "}" \
                                                        "}" \
                                                      "}",
                                            reduce_fun = "_count",
                                            reduce = False,
                                            wrapper=_wrap_bypass)

def create(func):
    def cache_create(self, *args, **kw):
        if not self.caching: return
        docs = func(self, *args, **kw)
        for doc in docs:
            self._cachedMetaDatas.cache(doc.path, doc)
        return docs
    cache_create.op = 'create'
    return cache_create

def create_file(func):
    def cache_create_file(self, *args, **kw):
        if not self.caching: return
        file = func(self, *args, **kw)
        self._cachedMetaDatas.cache(file.document.path, file.document)
        return file
    cache_create_file.op = 'create'
    return cache_create_file

def read(func):
    def cache_read(self, *args, **kw):
        if not self.caching: return
        for doc in func(self, *args, **kw):
            self._cachedMetaDatas.cache(doc.path, doc)
            yield doc
    return cache_read

def update(func):
    def cache_update(self, *args, **kw):
        if not self.caching: return
        docs = list(func(self, *args, **kw))
        for doc in docs:
            self._cachedMetaDatas.cache(doc.path, doc)
        return docs
    cache_update.op = 'update'
    return cache_update

def rename(func):
    def cache_rename(self, old, new, *args, **kw):
        rename = False
        for doc in func(self, old, new, *args, **kw):
            if not rename:
                oldkey = old
                rename = True
            else:
                oldkey = posixpath.join(doc.dirpath.replace(new, old, 1),
                                      doc.filename)

            if self._cachedMetaDatas.has_key(oldkey):
                self._cachedMetaDatas.invalidate(oldkey)
    cache_rename.op = 'rename'
    return cache_rename

def delete(func):
    def cache_delete(self, *args, **kw):
        if not self.caching: return
        docs = list(func(self, *args, **kw))
        for doc in docs:
            if self._cachedMetaDatas.has_key(doc.path):
                self._cachedMetaDatas.invalidate(doc.path)
        return docs
    cache_delete.op = 'delete'
    return cache_delete

class CouchedFile(Debugger):

    flags = None
    file_ptr = None
    document = None
    filesystem = None
    fixed = False

    @normpath
    def __init__(self, path, flags, uid, gid, mode, filesystem, document=None):
        self.filesystem = filesystem
        self.flags = flags

        if mode:
            open_args = (path, flags, mode)
        else:
            open_args = (path, flags)
        
        try:
          self.file_ptr = self.filesystem.realfs.open(*open_args)

        except (OSError, IOError), e:
          self.debug("Could not open %s, %s"
                     % (path, e.message))
          raise

        try:
            self.document = self.filesystem[path]
        except Exception, e:
            if flags & os.O_CREAT:
                if document:
                    self.debug("Using document %s" % document)
                    document._data['_id'] = document.id
                    self.filesystem.doc_helper.database.save(document._data)
                    self.document = document
                    self.fixed = True
                else:
                    self.debug("Creating default new document")

                    stats = MutableStat(os.lstat(self.filesystem.real_path(path)))
                    stats.st_uid = uid
                    stats.st_gid = gid
                    fields = { 'filename' : posixpath.basename(path),
                               'dirpath'  : posixpath.dirname(path),
                               'mode'     : mode,
                               'type'     : "application/x-empty",
                               'stats'    : stats }

                    self.document = self.filesystem.doc_helper.create(**fields)

            else:
                raise e

    def close(self, release=True):
        path = posixpath.join(self.document.dirpath, self.document.filename)
        realpath = self.filesystem.real_path(path)

        try:
            self.file_ptr.close()
            newstats = os.lstat(realpath)

        except (OSError, IOError), e:
            self.debug("Could not close %s (%s), %s" % (path, realpath, e.message))
            raise

        if release and not self.fixed and self.flags & (os.O_RDWR | os.O_WRONLY | os.O_TRUNC | os.O_APPEND):
            self.debug("Updating document %s because it has been modified" % path)

            newstats = self.filesystem.realfs.lstat(path)
            mimetype = self.filesystem.realfs.get_mime_type(path).basic()
            stats = self.document.get_stats()

            self.document.type = mimetype
            for attr in ['st_mtime', 'st_mtime', 'st_blocks', 'st_size']:
                if hasattr(newstats, attr):
                    setattr(stats, attr, getattr(newstats, attr))
            self.document.set_stats(stats)

            return self.filesystem.doc_helper.update(self.document)

    def __getattr__(self, attr):
      return getattr(self.file_ptr, attr)

    def __del__(self):
      self.close()


class CouchedFileSystem(Debugger):
    '''
    3 type of call:
        - "Read"   : Calls that only read datas.
                        -> 1 read access to the database to get the document
    
        - "Create" : Calls that create new files on the filesystem.
                        -> 1 write access to the filesystem to create the file
                        -> 1 write access to the database to create the document
                        -> 1 read access to database to get the parent directory document
                        -> 1 write access to database to update the parent directory document

        - "Update" : Calls that modify files on the filesystem (metadatas, filename, etc)
                        -> 1 write access to the filesystem to modify the file
                        -> 1 read access to database to get the document
                        -> 1 write access to database to update the document
    '''

    doc_helper = None

    def __init__(self, mount_point, db_name, server="http://localhost:5984",
                 auth=None, db_metadatas=False, fstype="auto", caching=True):

        self.mount_point = mount_point
        self.db_metadatas = db_metadatas
        self.fstype = fstype
        self.caching = caching

        if fstype == "nfs4":
            from ufo.fsbackend.nfs4 import NFS4FileSystem
            self.realfs = NFS4FileSystem(mount_point)
        else:
            from ufo.fsbackend import GenericFileSystem
            self.realfs = GenericFileSystem(mount_point)

        self._cachedMetaDatas = CacheDict(60)  # Dict to keep database docs in memory during
        self._cachedRevisions = CacheDict(60)  # a system call sequence to avoid database
                                               # access overheads.

        # Instantiate couchdb document helper
        self.doc_helper = DocumentHelper(SyncDocument, db_name, server, auth=auth, batch=False)


    @create
    @normpath
    def makedirs(self, path, mode, uid=None, gid=None):
        updated = []
        p = ""
        dirs = path.split(os.sep)[1:]
        for d in dirs:
            p += os.sep + d
            try:
                self[p]
            except OSError, e:
                updated.extend(self.mkdir(p, mode, uid, gid))

        return updated

    @create
    @normpath
    def mkdir(self, path, mode=0700, uid=None, gid=None, document=None):
        '''
        Call type : "Create"
        '''

        # TODO: test if couchdb is responding before apply changes on fs
        updated = []

        # Firstly make the directory on the filesystem
        self.realfs.mkdir(path, mode)

        # Then create the document into the database
        if not document:
            stats = MutableStat(self.realfs.lstat(path))
            stats.st_uid = uid
            stats.st_gid = gid
            fields = { 'filename' : posixpath.basename(path),
                       'dirpath'  : posixpath.dirname(path),
                       'mode'     : mode | stat.S_IFDIR,
                       'type'     : "application/x-directory",
                       'stats'    : stats }

            updated.append(self.doc_helper.create(**fields))

        else:
            document._data['_id'] = document.id
            self.doc_helper.database.save(document._data)
            updated.append(document)

        # Finally update the stats of the parent directory into the database
        if posixpath.dirname(path) != os.sep:
            parent = self[posixpath.dirname(path)]
            parent.set_stats(self.realfs.lstat(os.path.dirname(path)))

            updated.extend(self.doc_helper.update(parent))
        
        return updated

    @norm2path
    @create
    def symlink(self, dest, symlink, uid=None, gid=None, document=None):
        '''
        Call type : "Create"
        '''
        updated = []

        # Firstly make the symlink on the filesystem
        self.realfs.symlink(dest, symlink)

        stats = MutableStat(self.realfs.lstat(symlink))
        if uid:
            stats.st_uid = uid
        if gid:
            stats.st_gid = gid

        if not document:
            # Then create the document into the database
            fields = { 'filename' : posixpath.basename(symlink),
                       'dirpath'  : posixpath.dirname(symlink),
                       'mode'     : 0777 | stat.S_IFLNK,
                       'type'     : "application/x-symlink",
                       'stats'    : stats }

            updated.append(self.doc_helper.create(**fields))

        else:
            document._data['_id'] = document.id
            self.doc_helper.database.save(document._data)
            updated.append(document)

        # Finally update the stats of the parent directory into the database
        parent = self[posixpath.dirname(symlink)]
        parent.set_stats(self.realfs.lstat(os.path.dirname(symlink)))

        updated.extend(self.doc_helper.update(parent))

        return updated

    @update
    @normpath
    def chmod(self, path, mode):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the mode change on the filesystem
            self.realfs.chmod(path, mode)

        # Then update the document into the database
        document = self[path]
        document.mode = (document.mode & 070000) | mode

        return self.doc_helper.update(document)

    @update
    @normpath
    def chown(self, path, uid, gid):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the uid/gid change on the filesystem
            self.realfs.chown(path, uid, gid)

        # Then update the document into the database
        document = self[path]
        document.uid = uid
        document.gid = gid

        return self.doc_helper.update(document)

    @update
    @normpath
    def tag(self, path, tag, remove=False):
        '''
        Call type : "Update"
        '''

        # Then update the document into the database
        document = self[path]
        if remove:
            document.del_tag(tag)
        else:
            document.add_tag(tag)

        return self.doc_helper.update(document)

    @update
    @normpath
    def setxattr(self, path, key, value=None, db_only=True):
        '''
        Call type : "Update"
        '''

        document = self[path]
        is_acl = key == "system.posix_acl_access"

        if is_acl:
            if value == None:
                new_acl = acl.ACL()
            else:
                new_acl = acl.ACL.from_xattr(value)

            from ufo.user import user
            set_acl = False

            old_acl = document.posix_acl
            # If there is any existing ACL, we compute a 'diff'
            # between the old ACL and new one to detect the entry to remove
            s1 = map(repr, old_acl)
            s2 = map(repr, new_acl)
            diff = difflib.context_diff(s1, s2)
            for ace_str in filter(lambda x: x[0] == '-' and x[-1] != '\n', diff):
                ace = acl.ACE.from_string(ace_str[2:])
                if ace.kind & acl.ACL_USER or ace.kind & acl.ACL_GROUP:
                    set_acl = True

            # Now we detect if one of the person to share the file with
            # is a not a friend yet, in this case we issue a friend request
            # and do not set the corresponding ACE
            file_acl = acl.ACL()
            for ace in new_acl:
                if ace.kind & acl.ACL_USER:
                    if ace.qualifier != "public" and not user.friends.has_key(ace.qualifier):
                        friend = user.pending_friends.get(ace.qualifier)
                        if not friend:
                            friend = user.request_friend(ace.qualifier)
                        friend.pending_shares[document.id] = ace.perms.upper().replace('-', '')
                        self.debug("Adding %s to the pending shares for %s" % (document.id, ace.qualifier))
                        user.friend_helper.update(friend)
                        continue

                    set_acl = True

                elif ace.kind & acl.ACL_GROUP:
                    set_acl = True

                file_acl.append(ace)

                current = document.dirpath
                while current != os.sep:
                    parent = self[current]
                    if not (parent.mode & stat.S_IXOTH):
                        self.chmod(current, (self[current].mode & 0777) | stat.S_IXOTH)
                    current = os.path.dirname(current)

            if value != None:
                if not set_acl:
                    return []

                # We compute a new value for the extended attribute
                value = file_acl.to_json()
                document.mode = (document.mode & ~7) | file_acl.get(acl.ACL_OTHER)._perms

        if not db_only:
            if value == None:
                self.realfs.removexattr(path, key)
            else:
                if is_acl:
                    self.realfs.set_acl(path, file_acl)
                else:
                    self.realfs.setxattr(path, key, value)

        if value == None:
            if is_acl:
                self.acl = []

            elif document.xattrs.has_key(key):
                del document.xattrs[key]

        else:
            if is_acl:
                document.acl = value

            else:
                if document.xattrs:
                    document.xattrs[key] = eval('u' + repr(value))
                    self.doc_helper.update(document)
                else:
                    _tuple = { key : eval('u' + repr(value)) }
                    document.xattrs = dict(**_tuple)

        return self.doc_helper.update(document)

    @normpath
    def getxattr(self, path, key):
        '''
        Call type : "Read"
        '''

        document = self[path]

        if key == "system.posix_acl_default":
            return acl.ACL.from_mode(0700)

        elif key == "system.posix_acl_access":
            return document.posix_acl.to_xattr()

        return eval(repr(document.xattrs[key])[1:])

    @update
    @normpath
    def utime(self, path, times):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the times change on the filesystem
            self.realfs.utime(path, times)

        # Then update the document into the database
        document = self[path]
  
        stats = document.get_stats()
        stats.st_atime, stats.st_mtime = times
        document.set_stats(stats)

        return self.doc_helper.update(document)

    @rename
    @norm2path
    def rename(self, old, new, overwrite=False):
        '''
        Call type : "Update"
        '''

        # Updating directory and filename of the document
        document = self[old]
        try:
            dest = self[new]
            if not overwrite:
                raise OSError(errno.EEXIST, os.strerror(errno.EEXIST))

        except Exception, e:
            dest = None

        if dest and stat.S_ISDIR(dest.mode):
            document.dirpath = new
            new = posixpath.join(new, document.filename)
        else:
            document.filename = posixpath.basename(new)
            document.dirpath  = posixpath.dirname(new)

        documents = [ document ]

        if dest:
            self.unlink(new)

        # Firstly rename the file on the filesystem
        self.realfs.rename(old, new)

        # Updating directory subtree documents
        if stat.S_ISDIR(document.mode):
            # TODO: make this smarter
            for doc in self.doc_helper.by_dir_prefix(key=old):
                doc.dirpath = doc.dirpath.replace(old, new, 1)
                documents.append(doc)

        return self.doc_helper.update(documents)

    @delete
    @normpath
    def unlink(self, path, nodb=False):
        '''
        Call type : "Update"
        '''

        # TODO: Use View Collation to get the file and the shares
        # in one request

        # Firstly remove the file from the filesystem
        self.realfs.unlink(path)

        if not nodb:
            # Then remove the document from the database
            doc = self[path]
            self.doc_helper.delete(doc)
            return [ doc ]

        return []

    @delete
    @normpath
    def rmdir(self, path, nodb=False, force=False):
        '''
        Call type : "Update"
        '''

        deleted = []

        # Firstly remove the file from the filesystem
        if force:
            shutil.rmtree(self.real_path(path), ignore_errors=True)
        else:
            self.realfs.rmdir(path)

        if not nodb:
            folder = self[path]

            # Updating directory subtree documents  
            if stat.S_ISDIR(folder.mode):

                # TODO: make this smarter
                for doc in self.doc_helper.by_dir_prefix(key=path):
                    self.doc_helper.delete(doc)
                    deleted.append(doc)

                # Then remove the document from the database
                self.doc_helper.delete(folder)
                deleted.append(folder)

        return deleted

    @normpath
    def stat(self, path):
        '''
        Call type : "Read"
        '''

        return self[path].get_stats()

    @read
    @normpath
    def listdir(self, path):
        '''
        Call type : "Read"
        '''

        for doc in self.doc_helper.by_dir(key=path):
            yield doc

    @normpath
    @update  
    def truncate(self, path, length):
        document = self[path]
        real_path = self.real_path(path)

        # Truncate the file
        fd = os.open(real_path, os.O_WRONLY)
        os.ftruncate(fd, length)
        os.close(fd)

        # Update the document stats
        document.set_stats(os.stat(real_path))

        return self.doc_helper.update(document)

    @create_file
    @normpath
    def open(self, path, flags, uid=None, gid=None, mode=0700, document=None):
        return CouchedFile(path, flags, uid, gid, mode, self, document)

    @create
    @normpath
    def populate(self, path):
        '''
        Call type : "Create"
        '''

        stats = self.realfs.lstat(path)
        mimetype = self.realfs.get_mime_type(path).basic()

        fields = { 'filename' : posixpath.basename(path),
                   'dirpath'  : posixpath.dirname(path),
                   'mode'     : stats.st_mode,
                   'type'     : mimetype,
                   'stats'    : stats }

        return [ self.doc_helper.create(**fields) ]

    @normpath
    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        # Copied from Python 'os' module
        
        # We may not have read permission for top, in which case we can't  
        # get a list of the files the directory contains.  os.path.walk    
        # always suppressed the exception then, rather than blow up for a  
        # minor reason when (say) a thousand readable directories are still
        # left to visit.  That logic is copied here.
        try:
            # Note that listdir and error are globals in this module due
            # to earlier import-*.
            names = self.doc_helper.by_dir(key=top)
                                
        except error, err:
            if onerror is not None:
                onerror(err)
            return

        dirs, nondirs = [], []
        for name in names:
            if name.isdir():
                dirs.append(name)
            else:
                nondirs.append(name)

        if topdown:
            yield self[top], dirs, nondirs
        for name in dirs:
            if followlinks or not name.islink():
                for x in self.walk(name.path, topdown, onerror, followlinks):
                    yield x
        if not topdown:
            yield self[top], dirs, nondirs

    @normpath
    def exists(self, path):
        try:
            self[path]
            return True
        except:
            return False

    @normpath
    def _get(self, path):
        # The root directory does not exists in the database
        if path == '/':
            return RootSyncDocument(self.realfs.lstat(path))
                  
        if self._cachedMetaDatas.isObsolete(path):
            try:
                document = self.doc_helper.by_path(key=path, pk=True)
                self._cachedMetaDatas.cache(path, document)
                return document

            except DocumentException, e:
                self._cachedMetaDatas.cache(path, None)
                raise OSError(errno.ENOENT, os.strerror(errno.ENOENT))

        if self._cachedMetaDatas.get(path):
            return self._cachedMetaDatas.get(path)

        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT))

    @normpath
    def du(self, path):
        return self.doc_helper.by_dir_prefix(key=path, pk=True, reduce=True)['value']

    def copy(self, src, dest, document=None):
        return self.realfs.copy(src, dest, document)

    def real_path(self, path):
        # Never use 'os.path.join' anywhere instead of for real path.
        return os.path.join(self.mount_point, path[1:])

    def __getitem__(self, path):
      return self._get(path)


class RootSyncDocument(SyncDocument):
  '''
  Class that represent root directory document.
  '''

  def __init__(self, stats):
    fixedfields = { 'filename' : "/",
                    'dirpath'  : "",
                    'mode'     : stats.st_mode | stat.S_IFDIR,
                    'type'     : "application/x-directory",
                    'stats'    : stats }

    super(RootSyncDocument, self).__init__(**fixedfields)

    self['_id'] = "00000000000000000000000000000000"
    self['_rev'] = "0-0123456789abcdef0123456789abcdef"

