#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

setup(name='python-ufo',
      version='0.1',
      description='UFO client librairy',
      author='Kevin Pouget',
      author_email='pouget@agorabox.org',
      packages=['ufo'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Web Environment',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GPLv2 License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Utilities'],
      install_requires=['setuptools'],
     )

