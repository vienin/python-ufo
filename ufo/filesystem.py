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
import uuid
import errno
import shutil
import xattr
import difflib
import subprocess

from ufo.utils import MutableStat, MimeType, CacheDict, get_user_infos
from ufo.debugger import Debugger
from ufo.database import *
import ufo.acl as acl

def normpath(func):
    def handler(self, path, *args, **kw):
        return func(self, os.path.normpath(path), *args, **kw)
    return handler

def norm2path(func):
    def handler(self, path, path2, *args, **kw):
        return func(self, os.path.normpath(path), os.path.normpath(path2), *args, **kw)
    return handler

def _reduce_sum(keys, values):
    return sum(values)

class SyncDocument(UTF8Document):

    doctype  = TextField(default="SyncDocument")
    filename = TextField()
    dirpath  = TextField()
    uid      = IntegerField()
    gid      = IntegerField()
    mode     = IntegerField()
    type     = TextField()
    stats    = DictField(Mapping.build(
                   n_sequence_fields = IntegerField(),
                   n_unnamed_fields  = IntegerField(),
                   n_fields   = IntegerField(),
                   st_atime   = FloatField(),
                   st_blksize = IntegerField(),
                   st_blocks  = IntegerField(),
                   st_ctime   = FloatField(),
                   st_dev     = IntegerField(),
                   st_gid     = IntegerField(),
                   st_ino     = IntegerField(),
                   st_mode    = IntegerField(),
                   st_mtime   = FloatField(),
                   st_nlink   = IntegerField(),
                   st_rdev    = IntegerField(),
                   st_size    = LongField(),
                   st_uid     = IntegerField()))
    xattrs   = DictField()

    # TODO: Use a dedicated document class for tags
    tags = ListField(TextField())

    def __init__(self, stats=None, **fields):
        super(SyncDocument, self).__init__(**fields)

        if stats:
            self.set_stats(stats)

    def set_stats(self, stat_result):
        for field in self.stats._fields.keys():
            if isinstance(stat_result, dict):
                self.stats[field] = stat_result[field]
            else:
                self.stats[field] = getattr(stat_result, field)
  
    def get_stats(self):
        stat_result = MutableStat()
        for field in self.stats._fields.keys():
            if field in ['st_uid', 'st_gid', 'st_mode']:
                setattr(stat_result, field, getattr(self, field[3:]))
            elif field == 'st_ino' and self.id:
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

    @property
    def posix_acl(self):
	try:
            posix_acl_access = eval(repr(self.xattrs.get('system.posix_acl_access', u''))[1:])
            if posix_acl_access:
                return acl.ACL.from_xattr(posix_acl_access)
            else:
                return acl.ACL.from_mode(self.stats['st_mode'])
        except:
            return acl.ACL()

    @ViewField.define('syncdocument')
    def by_path(doc):
        from os.path import join
        if doc['doctype'] == "SyncDocument":
            yield join(doc['dirpath'], doc['filename']), doc

    @ViewField.define('syncdocument')
    def by_type(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['type'], doc

    @ViewField.define('syncdocument')
    def by_uid(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['uid'], doc

    @ViewField.define('syncdocument')
    def by_uid_and_path(doc):
        from os.path import join
        if doc['doctype'] == "SyncDocument":
            yield [ doc['uid'] ] + doc['dirpath'].split('/')[1:] + [ doc['filename'] ], doc

    @ViewField.define('syncdocument')
    def by_dir(doc):
        if doc['doctype'] == "SyncDocument":
            yield doc['dirpath'], doc

    @ViewField.define('syncdocument')
    def by_dir_prefix(doc):
        from os import sep
        from os.path import dirname
        if doc['doctype'] == "SyncDocument":
            last = ''
            current = doc['dirpath']
            while current != sep and current != last:
                yield current, doc
                last = current
                current = dirname(current)

    @ViewField.define('syncdocument')
    def by_tag(doc):
        if doc['doctype'] == "SyncDocument":
          for tag in doc['tags']:
            yield tag, doc

    @ViewField.define('syncdocument')
    def by_id(doc):
      if doc['doctype'] == "SyncDocument":
        yield doc['_id'], doc

    @ViewField.define('syncdocument')
    def by_keyword(doc):
      if doc['doctype'] == 'SyncDocument' and doc['filename']:
          for i in xrange(len(doc['filename']) - 2):
              yield doc['filename'][i:].lower(), doc

    @ViewField.define('syncdocument')
    def by_provider_and_participant(doc):
        from ufo.acl import ACL, ACL_XATTR, ACL_USER
        if doc['doctype'] == 'SyncDocument' and doc.get('xattrs', {}).has_key(ACL_XATTR):
            try:
                acl = ACL.from_xattr(eval(repr(doc['xattrs'][ACL_XATTR])[1:]))
                for ace in acl:
                    if ace.kind & ACL_USER:
                        yield [ int(doc['uid']), ace._qualifier, doc['dirpath'] + "/" + doc['filename'] ], doc
            except: pass

    @ViewField.define('syncdocument')
    def by_participant(doc):
        import pwd
        from ufo.acl import ACL, ACL_XATTR, ACL_USER
        if doc['doctype'] == 'SyncDocument' and doc.get('xattrs', {}).has_key(ACL_XATTR):
            try:
                acl = ACL.from_xattr(eval(repr(doc['xattrs'][ACL_XATTR])[1:]))
                for ace in acl:
                    if ace.kind & ACL_USER:
                        yield pwd.getpwuid(ace._qualifier).pw_name, doc
            except: pass

    def __str__(self):
        return ('<%s id:%s path:%s type:%s>'
                % (self.doctype,
                   self.id,
                   os.path.join(self.dirpath, self.filename),
                   self.type))

    def __repr__(self):
        return str(self)

    @property
    def path(self):
        return os.path.join(self.dirpath, self.filename)

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

def create(func):
    def cache_create(self, *args, **kw):
        if not self.caching: return
        docs = func(self, *args, **kw)
        for doc in docs:
            self._cachedMetaDatas.cache(doc.path, doc)
        return docs
    return cache_create

def create_file(func):
    def cache_create_file(self, *args, **kw):
        if not self.caching: return
        file = func(self, *args, **kw)
        self._cachedMetaDatas.cache(file.document.path, file.document)
        return file
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
    return cache_update

def delete(func):
    def cache_delete(self, *args, **kw):
        if not self.caching: return
        docs = list(func(self, *args, **kw))
        for doc in docs:
            if self._cachedMetaDatas.has_key(doc.path):
                self._cachedMetaDatas.invalidate(doc.path)
        return docs
    return cache_delete

class CouchedFile(Debugger):

    flags = None
    file_ptr = None
    document = None
    filesystem = None

    @normpath
    def __init__(self, path, flags, uid, gid, mode, filesystem):
        self.filesystem = filesystem
        self.flags = flags

        open_args = (self.filesystem.real_path(path), flags)
        if mode != None:
            open_args += (mode,)

        try:
          fd = os.open(*open_args)
          self.file_ptr = os.fdopen(fd, self.filesystem.flags_to_stdio(flags))

        except (OSError, IOError), e:
          self.debug("Could not open %s (%s), %s"
                     % (path, self.filesystem.real_path(path), e.message))
          raise

        try:
            self.document = self.filesystem[path]
        except Exception, e:
            if flags & os.O_CREAT:
                self.debug("Creating document %s in database from file %s"
                           % (path, self.filesystem.real_path(path)))

                stats = os.lstat(self.filesystem.real_path(path))
                fields = { 'filename' : os.path.basename(path),
                           'dirpath'  : os.path.dirname(path),
                           'uid'      : uid,
                           'gid'      : gid,
                           'mode'     : mode,
                           'type'     : "application/x-empty",
                           'stats'    : stats }

                self.document = self.filesystem.doc_helper.create(**fields)
            else:
                raise e

    def close(self, release=True):
        path = os.path.join(self.document.dirpath, self.document.filename)
        realpath = self.filesystem.real_path(path)

        try:
            self.file_ptr.close()

        except (OSError, IOError), e:
            self.debug("Could not close %s (%s), %e" % (path, realpath, e.message))
            raise

        if release and self.flags & (os.O_RDWR | os.O_WRONLY | os.O_TRUNC | os.O_APPEND):
            self.debug("Updating document %s because it has been modified" % path)

            newstats = os.lstat(realpath)
            mimetype = MimeType(realpath).basic()
            stats = self.document.get_stats()

            self.document.type = mimetype
            stats.st_mtime  = newstats.st_mtime
            stats.st_atime  = newstats.st_atime
            stats.st_blocks = newstats.st_blocks
            stats.st_size   = newstats.st_size
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
                 spnego=False, db_metadatas=False, fstype="auto", caching=True):

        self.mount_point = mount_point
        self.db_metadatas = db_metadatas
        self.fstype = fstype
        self.caching = caching

        self._cachedMetaDatas = CacheDict(60)  # Dict to keep database docs in memory during
        self._cachedRevisions = CacheDict(60)  # a system call sequence to avoid database
                                               # access overheads.

        # Instantiate couchdb document helper
        self.doc_helper = DocumentHelper(SyncDocument, db_name, server, spnego, batch=False)


    @normpath
    @create
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

    @normpath
    @create
    def mkdir(self, path, mode, uid=None, gid=None):
        '''
        Call type : "Create"
        '''

        # TODO: test if couchdb is responding before apply changes on fs
        updated = []

        # Firstly make the directory on the filesystem
        os.mkdir(self.real_path(path), mode)

        # Then create the document into the database
        stats = os.lstat(self.real_path(path))
        if not uid: uid = stats.st_uid
        if not gid: gid = stats.st_gid

        fields = { 'filename' : os.path.basename(path),
                   'dirpath'  : os.path.dirname(path),
                   'uid'      : uid,
                   'gid'      : gid,
                   'mode'     : mode | stat.S_IFDIR,
                   'type'     : "application/x-directory",
                   'stats'    : stats }

        updated.append(self.doc_helper.create(**fields))

        # Finally update the stats of the parent directory into the database
        if os.path.dirname(path) != os.sep:
            parent = self[os.path.dirname(path)]
            parent.set_stats(os.lstat(os.path.dirname(self.real_path(path))))

            updated.extend(self.doc_helper.update(parent))
        
        return updated

    @norm2path
    @create
    def symlink(self, dest, symlink, uid=None, gid=None):
        '''
        Call type : "Create"
        '''
        updated = []

        # Firstly make the symlink on the filesystem
        os.symlink(dest, self.real_path(symlink))

        if not uid:
            uid = stats.st_uid
        if not gid:
            gid = stats.st_gid

        # Then create the document into the database
        stats = os.lstat(self.real_path(symlink))
        fields = { 'filename' : os.path.basename(symlink),
                   'dirpath'  : os.path.dirname(symlink),
                   'uid'      : uid,
                   'gid'      : gid,
                   'mode'     : 0777 | stat.S_IFLNK,
                   'type'     : "application/x-symlink",
                   'stats'    : stats }
    
        updated.append(self.doc_helper.create(**fields))

        # Finally update the stats of the parent directory into the database
        parent = self[os.path.dirname(symlink)]
        parent.set_stats(os.lstat(os.path.dirname(self.real_path(symlink))))

        updated.extend(self.doc_helper.update(parent))

        return updated

    @normpath
    @update
    def chmod(self, path, mode):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the mode change on the filesystem
            os.chmod(self.real_path(path), mode)

        # Then update the document into the database
        document = self[path]
        document.mode = (document.mode & 070000) | mode

        return self.doc_helper.update(document)

    @normpath
    @update
    def chown(self, path, uid, gid):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the uid/gid change on the filesystem
            os.chown(self.real_path(path), uid, gid)

        # Then update the document into the database
        document = self[path]
        document.uid = uid
        document.gid = gid

        return self.doc_helper.update(document)

    @normpath
    @update
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

    @normpath
    @update
    def setxattr(self, path, key, value=None, db_only=True):
        '''
        Call type : "Update"
        '''

        document = self[path]

        if key == "system.posix_acl_access":
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
                value = file_acl.to_xattr()
                document.mode = (document.mode & ~7) | file_acl.get(acl.ACL_OTHER)._perms

        if not db_only:
            if value == None:
                xattr.removexattr(self.real_path(path), key, value)
            else:
                if key == "system.posix_acl_access" and self.fstype == "nfs4":
                    # TODO: Convert the POSIX ACL to an NFS4 ACL using Python bindings
                    process = subprocess.Popen([ "nfs4_setfacl", "-S", "-", self.real_path(path) ],
                                               stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                    _, err = process.communicate(file_acl.to_nfs4())

                    if err:
                        raise OSError(process.returncode, err)

                else:
                    xattr.setxattr(self.real_path(path), key, value)

        if value == None:
            del document.xattrs[key]
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

        return eval(repr(document.xattrs[key])[1:])

    @normpath
    @update
    def utime(self, path, times):
        '''
        Call type : "Update"
        '''

        if not self.db_metadatas:
            # Firstly make the times change on the filesystem
            os.utime(self.real_path(path), times)

        # Then update the document into the database
        document = self[path]
  
        stats = document.get_stats()
        stats.st_atime, stats.st_mtime = times
        document.set_stats(stats)

        return self.doc_helper.update(document)

    @norm2path
    @update
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
            new = os.path.join(new, document.filename)
        else:
            document.filename = os.path.basename(new)
            document.dirpath  = os.path.dirname(new)

        documents = [ document ]

        if dest:
            self.unlink(new)

        # Firstly rename the file on the filesystem
        os.rename(self.real_path(old), self.real_path(new))

        # Updating directory subtree documents
        if stat.S_ISDIR(document.mode):
            # TODO: make this smarter
            for doc in self.doc_helper.by_dir_prefix(key=old):
                doc.dirpath = doc.dirpath.replace(old, new, 1)
                documents.append(doc)

        return self.doc_helper.update(documents)

    @normpath
    @delete
    def unlink(self, path, nodb=False):
        '''
        Call type : "Update"
        '''

        # TODO: Use View Collation to get the file and the shares
        # in one request

        # Firstly remove the file from the filesystem
        os.unlink(self.real_path(path))

        if not nodb:
            # Then remove the document from the database
            doc = self[path]
            self.doc_helper.delete(doc)
            return [ doc ]

        return []

    @normpath
    @delete
    def rmdir(self, path, nodb=False, force=False):
        '''
        Call type : "Update"
        '''

        deleted = []

        # Firstly remove the file from the filesystem
        if force:
            shutil.rmtree(self.real_path(path), ignore_errors=True)
        else:
            os.rmdir(self.real_path(path))

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

    @normpath
    @read
    def listdir(self, path):
        '''
        Call type : "Read"
        '''

        path = os.path.normpath(path)
        for doc in self.doc_helper.by_dir(key=path):
            yield doc

    @normpath
    @create_file
    def open(self, path, flags, uid=None, gid=None, mode=None):
        return CouchedFile(path, flags, uid, gid, mode, self)

    @normpath
    @create
    def populate(self, path):
        '''
        Call type : "Create"
        '''

        stats = os.lstat(self.real_path(path))
        mimetype = MimeType(self.real_path(path)).basic()

        fields = { 'filename' : os.path.basename(path),
                   'dirpath'  : os.path.dirname(path),
                   'uid'      : stats.st_uid,
                   'gid'      : stats.st_gid,
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
      
        return result

    @normpath
    def _get(self, path):
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

    def __getitem__(self, path):
      return self._get(path)

