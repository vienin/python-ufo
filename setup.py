#!/usr/bin/env python

import sys

from distutils.core import setup
from DistUtilsExtra.command import *


cmdclass = { "build" : build_extra.build_extra }

# Temporary disabled i18n on Windows for build
if sys.platform != "win32":
    cmdclass["build_i18n"] = build_i18n.build_i18n

setup(name='python-ufo',
      version='0.7',
      description='UFO client library',
      author='Kevin Pouget',
      author_email='pouget@agorabox.org',
      packages=['ufo', 'ufo.fsbackend'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Web Environment',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GPLv2 License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Utilities'],
      install_requires=['setuptools'],
      cmdclass = cmdclass,
)
