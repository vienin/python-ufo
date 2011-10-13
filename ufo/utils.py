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
import krbV
import pwd
import magic
import string
import random
import syslog
import traceback

import xmlrpclib as rpc

from threading import RLock

import exceptions
from ufo import errors

from ufo.debugger import Debugger
from ufo import config

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


class CallProxy(object):
    def __init__(self, func, meta):
        self.func = func
        self.meta = meta

    def __call__(self, *args, **kw):
        return self.func(self.meta, *args, **kw)


class ComponentProxy(object):
    def __init__(self, component, host = "http://localhost/xmlrpc", transport=None, meta = {}, ufo_in_server=None):
        meta = meta.copy()
        if not meta.has_key("apache_env") and os.environ.has_key("KRB5CCNAME"):
            meta["apache_env"] = { "KRB5CCNAME" : os.environ["KRB5CCNAME"] }
        self.meta = meta
        if ufo_in_server == None:
            ufo_in_server = config.ufo_in_server
        self.ufo_in_server = ufo_in_server
        if not ufo_in_server:
            if not transport:
                from ipalib.rpc import KerbTransport
                transport = KerbTransport()
            self.server = rpc.Server(host, transport)
            self.component = getattr(self.server, component.split('.')[-1].lower())
        else:
            mod_name, klass_name = get_mod_func(component)
            klass = getattr(import_module(mod_name), klass_name)
            self.component = klass()

    def __getattr__(self, name):
        if self.ufo_in_server:
            return CallProxy(getattr(self.component, name), self.meta)
        else:
            return getattr(self.component, name) 


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

def get_user_infos(login=None, uid=None):
    assert login != None or uid != None

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
        principal = get_current_principal(_meta['apache_env'].get('KRB5CCNAME')).split('@')[0]

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

# Those functions were taken from the Django framework
def _resolve_name(name, package, level):
    """Return the absolute name of the module to be imported."""
    if not hasattr(package, 'rindex'):
        raise ValueError("'package' not set to a string")
    dot = len(package)
    for x in xrange(level, 1, -1):
        try:
            dot = package.rindex('.', 0, dot)
        except ValueError:
            raise ValueError("attempted relative import beyond top-level "
                              "package")
    return "%s.%s" % (package[:dot], name)

def import_module(name, package=None):
    """Import a module.

    The 'package' argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    """
    if name.startswith('.'):
        if not package:
            raise TypeError("relative imports require the 'package' argument")
        level = 0
        for character in name:
            if character != '.':
                break
            level += 1
        name = _resolve_name(name[level:], package, level)
    __import__(name)
    return sys.modules[name]

def get_mod_func(callback):
    try:
        dot = callback.rindex('.')
    except ValueError:
        return callback, ''
    return callback[:dot], callback[dot+1:]

