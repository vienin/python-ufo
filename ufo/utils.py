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

import os
import sys
import time
import magic
import string

from threading import RLock
from ufo.user import user

class MutableStat(object):
    '''
    Placeholder object to represent a stat that is directly mutable.
    '''

    n_sequence_fields = 0
    n_unnamed_fields  = 0
    n_fields   = 0
    st_atime   = None
    st_blksize = 0
    st_blocks  = 0
    st_ctime   = None
    st_dev     = 0
    st_gid     = 0
    st_ino     = 0
    st_mode    = 0
    st_mtime   = None
    st_nlink   = 0
    st_rdev    = 0
    st_size    = 0L
    st_uid     = 0

    _keys = [ 'st_mode', 'st_ino', 'st_dev', 'st_nlink', 'st_uid', 'st_gid',
              'st_size', 'st_atime', 'st_mtime', 'st_ctime' ]

    def __init__(self, stat_result=None):
        if stat_result:
            for key in dir(stat_result):
                if not key.startswith('_'):
                    self.__dict__[key] = stat_result.__getattribute__(key)

    def __getitem__(self, idx):
        key = self._keys[idx]
        return self.__dict__.get(key, getattr(MutableStat, key))

    def __getslice__(self, start, end):
        result = []

        for key in self._keys[start:end]:
            result.append(self.__dict__.get(key, getattr(MutableStat, key)))

        return tuple(result)

    def __repr__(self):
        return repr(self[0:len(self._keys)])


class MimeType(object):
    '''
    Object to get various mimetype forms of a file.
    '''

    _magic = None
    _path  = None

    def __init__(self, path):
        self._magic = magic.open(magic.MAGIC_MIME)
        self._magic.load()

        self._path = path

    def basic(self):
        return str(self._magic.file(self._path).split(";")[0])


class CacheDict(dict):
  
  _cacheTimeout = 0
  _accesslock   = None

  def __init__(self, timeout):
    self._cacheTimeout = timeout
    self._accesslock   = RLock()

  def get(self, key):
    return self[key]['value']

  def cache(self, key, value):
    self[key] = { 'time' : time.time(), 'value' : value }
    
  def isObsolete(self, key):
    return (not self.has_key(key) or
            time.time() - self[key]['time'] > self._cacheTimeout)
    
  def invalidate(self, key):
    if self.has_key(key):
      return self.pop(key)['value']

  def acquire(self):
    self._accesslock.acquire()

  def release(self):
    self._accesslock.release()


def get_user_infos(login=None, uid=None):
    assert login != None or uid != None

    if type(login) == int:
        uid = login
        login = None

    try:
        try:
            import pwd
            import grp

            if login:
                pw = pwd.getpwnam(login)
            else:
                pw = pwd.getpwuid(uid)

            try:
                firstname, lastname = pw.pw_gecos.split(' ')
            except:
                firstname = pw.pw_gecos
                lastname = ""

            groups = [ pw.pw_gid ]

            for group in grp.getgrall():
                if pw.pw_name in group.gr_mem:
                    groups.append(group.gr_gid)

            return { 'login' : pw.pw_name,
                     'uid' : pw.pw_uid,
                     'gid' : pw.pw_gid,
                     'fullname' : pw.pw_gecos,
                     'groups' : groups }

        except:
            if login:
                if user.login == login:
                    friend = user
                else:
                    friend = user.friends[login]

            else:
                if user.uid == uid:
                    friend = user
                else:
                    friend = user.friends_id[uid]

            fullname = ""
            if friend.firstname:
                fullname += friend.firstname

            if friend.lastname:
                fullname += " " + friend.lastname

            return { 'login' : friend.login,
                     'uid' : friend.uid,
                     'gid' : friend.gid,
                     'fullname' : fullname,
                     'groups' : [] }

    except:
        if not login: login = "nobody"
        if not uid: uid = -1

        return { 'login' : login,
                 'uid' : uid,
                 'gid' : uid,
                 'fullname' : 'The one who talks loud to say nothing',
                 'groups' : [] }
