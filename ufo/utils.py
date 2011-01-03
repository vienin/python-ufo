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
import time
import krbV
import pwd
import magic
import string
import random
import syslog
import traceback

from threading import RLock

import exceptions
from ufo import errors

from ufo.debugger import Debugger


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
        return self.__dict__[key]

    def __getslice__(self, start, end):
        result = []

        for key in self._keys[start:end]:
            result.append(self.__dict__[key])

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


def random_string(dir=None):
    ''' 
    Returns a random string with 10 chars 
    Example : zwEeymTWdh
    '''
    random.seed()
    d = [random.choice(string.letters) for x in xrange(10)]
    if (dir == None):
        return "".join(d)
    else:
        # if dir='/tmp///' we return some thing like '/tmp/zwEeymTWdh'
        return (str(dir).rstrip('/') + 
                '/' + 
                ''.join(d)
                )

def get_current_principal(krbccache):
    """
    @returns : principal name. Example : 'rachid@ALPHA.AGORABOX.ORG'
    """
    ctx = krbV.default_context()
    ccache = krbV.CCache(name=krbccache, context=ctx)
    cprinc_name = ccache.principal().name
    return unicode(cprinc_name)

def user_member_of(meta, principal_name, group_name):
    """
    Check if the principal_name is member of group_name
    """
    from user import User
    user = User(meta, principal_name)
    user.populate()
    if (group_name in user.groups):
        return True
    else:
        return False

def get_user_infos(login=None, uid=None):
    assert login or uid

    if login:
      key = login
      function = pwd.getpwnam
    else:
      key = uid
      function = pwd.getpwuid

    return { 'login'    : function(key).pw_name,
             'fullname' : function(key).pw_gecos,
             'uid'      : function(key).pw_uid,
             'gid'      : function(key).pw_gid }

def krb5principal(func):

  def wrapper(*__args, **__kwargs):
    _self = __args[0]
    _meta = __args[1]

    os.environ["KRB5CCNAME"] = _meta['apache_env'].get('KRB5CCNAME')
    try:
        principal = _meta['apache_env'].get('REMOTE_USER').split('@')[0]
    except Exception, e:
        principal = None

    return func.__call__(_self, _meta, principal, *__args[2:], **__kwargs)

  return wrapper

def fault_to_exception(fault):
    err = fault
    try:
        try:
            exception_type, exception_message = fault.faultString.split("'>:")
        except ValueError, e:
            exception_type, exception_message = fault.faultString.split("'>,")

        try:
            exception_type = exception_type.split("<class '")[1].split(".")[-1]
        except IndexError, e:
            exception_type = exception_type.split("<type '")[1].split(".")[-1]

        for module in (errors, exceptions):
            if hasattr(module, exception_type):
                err = getattr(module, exception_type).__call__(fault.faultCode, exception_message)

    except Exception, e:
        raise

    return err