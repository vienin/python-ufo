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

__version__ = (0, 0, 1)

debug_mode = False

from ipalib.config import Env

# Loading IPA environement
env = Env()
env._bootstrap()
env._finalize_core()

try:
    server = ""

    ufo_in_server = env.host in env.xmlrpc_uri

    if ufo_in_server:
        server = env.host.encode()
    else:
        server = env.server.encode()

    ##
    # Used if Storage component is installed
    ##
    realm = env.realm.encode()

    ######################################################
    # Storage
    ######################################################
    # address of the host providing the Storage Component
    # this variable is used by the Sync component
    storage_host = 'https://%s/xmlrpc' % server

    ######################################################
    # Sync
    ######################################################
    # address of the host providing the Storage Component
    # this variable is used by the Account component
    sync_host = 'https://%s/xmlrpc' % server

    ######################################################
    # Account
    ######################################################
    # address of the host providing the Account Component
    # this variable is used by the other components
    account_host = 'https://%s/xmlrpc' % server

except AttributeError, e:
    # seems that config file doesn't contains xmlrpc_uri
    import syslog
    syslog.syslog(syslog.LOG_WARNING,
                  "Seems we're not on a functional ipa host, maybe you should run ipa-client-install first")
