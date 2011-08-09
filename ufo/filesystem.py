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

from utils import MutableStat, MimeType
from debugger import Debugger
from database import *

def normpath(func):
    def handler(self, path, *args, **kw):
        return func(self, os.path.normpath(path), *args, **kw)
    return handler

def norm2path(func):
    def handler(self, path, path2, *args, **kw):
        return func(self, os.path.normpath(path), os.path.normpath(path2), *args, **kw)
    return handler

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
            mode_arg = (mode,)

        try:
          fd = os.open(*open_args)
          self.file_ptr = os.fdopen(fd, self.filesystem.flags_to_stdio(flags))

        except (OSError, IOError), e:
          self.debug("Could not open %s (%s), %s"
                     % (path, self.filesystem.real_path(path), e.message))
          raise

        try:
            self.filesystem[path]
            exists = True
        except Exception, e:
            exists = False

        if flags & os.O_CREAT and not exists:
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
            self.document = self.filesystem[path]

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

    def __init__(self, mount_point, db_name, server="http://localhost:5984", spnego=False, db_metadatas=False):
        self.mount_point = mount_point
        self.db_metadatas = db_metadatas

        # Instantiate couchdb document helper
        self.doc_helper = DocumentHelper(SyncDocument, db_name, server, spnego, batch=False)

    @normpath
    def makedirs(self, path, mode, uid=None, gid=None):
        p = ""
        dirs = path.split(os.sep)[1:]
        for d in dirs:
            p += os.sep + d
            try:
                self[p]
            except OSError, e:
                self.mkdir(p, mode, uid, gid)

    @normpath
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
    def rename(self, old, new):
        '''
        Call type : "Update"
        '''

        # Updating directory and filename of the document
        document = self[old]
        try:
            dest = self.doc_helper.by_path(key=new, pk=True)
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
            for doc in self.doc_helper.by_path(key=old, pk=True):
                doc.dirpath = doc.dirpath.replace(old, new, 1)
                documents.append(doc)

        return self.doc_helper.update(documents)

    @normpath
    def unlink(self, path, nodb=False):
        '''
        Call type : "Update"
        '''

        # Firstly remove the file from the filesystem
        os.unlink(self.real_path(path))

        if not nodb:
            # Then remove the document from the database
            self.doc_helper.delete(self[path])

    @normpath
    def rmdir(self, path, nodb=False, force=False):
        '''
        Call type : "Update"
        '''

        # Firstly remove the file from the filesystem
        if force:
            shutil.rmtree(self.real_path(path), ignore_errors=True)
        else:
            os.rmdir(self.real_path(path))

        if not nodb:
            # Then remove the document from the database
            self.doc_helper.delete(self[path])

    @normpath
    def stat(self, path):
        '''
        Call type : "Read"
        '''

        return self[path].get_stats()

    @normpath
    def listdir(self, path):
        '''
        Call type : "Read"
        '''

        path = os.path.normpath(path)
        for doc in self.doc_helper.by_dir(key=path):
            yield doc

    @normpath
    def open(self, path, flags, uid=None, gid=None, mode=None):
        return CouchedFile(path, flags, uid, gid, mode, self)

    @normpath
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
      try:
        return self.doc_helper.by_path(key=path, pk=True)

      except DocumentException, e:
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT))

    def __getitem__(self, path):
      return self._get(path)
