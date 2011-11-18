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

import sys
import syslog
import traceback

from ufo import config

class Debugger(object):
  '''
  This class implements a generic debuging method that all debuggable
  objects should use.
  '''

  _name = None

  def _setName(self, name):
    '''
    Set the name of the class to report to the syslog with.
    '''

    self._name = name

  def _validateName(self):
    '''
    Validate that the name has been set, or if it hasn't, set it to
    the class name.
    '''

    if self._name == None:
      self._name = self.__class__.__name__

  def _getName(self):
    '''
    Validate that the name has been set via _validateName, and then
    return the debug name.
    '''

    self._validateName()
    return self._name

  def debug(self, args):
    '''
    Quick method to output some debugging information which states the
    thread name a colon, and whatever arguments have been passed to
    it.

    Args:
      args: a list of additional arguments to pass, much like what
        print() takes.
    '''

    self._validateName()

    if config.debug_mode:
      name = '%s(%s)' % (self._getName(), self._getCaller()[2])
      s = '%s: %s' % (name, args)
      if len(s) > 252:
        s = s[:252] + '...'

      syslog.syslog(syslog.LOG_WARNING, s)

  def debug_exception(self):
    if config.debug_mode:
      exc_info = sys.exc_info()

      self.debug('*** Unhandled exception occurred')
      self.debug('***     Type: %s' % str(exc_info[0]))
      self.debug('***    Value: %s' % str(exc_info[1]))
      self.debug('*** Traceback:')

      for line in traceback.extract_tb(exc_info[2]):
        self.debug('***    %s(%d) in %s: %s' % line)

  def _getCaller(self, backsteps=1):
    '''
    Quick method to get the previous caller's method information.

    Returns:
      A tuple of the form (filename, lineno, funcname, text).
    '''

    tb = traceback.extract_stack(limit=backsteps+2)
    return tb[0]
