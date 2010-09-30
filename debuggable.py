import syslog
import traceback

import config

class Debuggable(object):
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

  def _debug(self, args):
    '''
    Quick method to output some debugging information which states the
    thread name a colon, and whatever arguments have been passed to
    it.

    Args:
      args: a list of additional arguments to pass, much like what
        print() takes.
    '''
    # FIXME : change the levels list bellow
    levels = {
      'CacheManager(_genCacheOpcodes)': 9,
      'CacheManager(_validateCache)':   9,
      'CacheManager(_generatePath)':    9,
      'CacheManager(_cacheStat)':       9,
      'CacheManager(_cacheFile)':       9,
      'CacheManager(_cacheDir)':        9,
      'CacheManager(statFile)':         9,
      }

    self._validateName()

    if config.debugMode:
      if not config.syslogOpen:
        syslog.openlog(config.progName)
        config.syslogOpen = True
        self._debug('Opened syslog.')

      name = '%s(%s)' % (self._getName(), self._getCaller()[2])
      s = '%s: %s' % (name, args)
      if len(s) > 252:
        s = s[:252] + '...'

      try:
        level = levels[name]
      except KeyError:
        level = 0

      if config.debugLevel >= level:
        syslog.syslog(syslog.LOG_WARNING, s)

  def _getCaller(self, backsteps=1):
    '''
    Quick method to get the previous caller's method information.

    Returns:
      A tuple of the form (filename, lineno, funcname, text).
    '''

    tb = traceback.extract_stack(limit=backsteps+2)
    return tb[0]
