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

debug_mode = True

from ipalib.config import Env
from ufo.debugger import Debugger
# On charge l'environnement d'IPA
deb = Debugger()
deb._setName("config.py")
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

    # Only member of this group can call the Storage component procedures
    storage_admins_group = 'ufoadmins'
    # the root principal on the nfs server. See also the idmapd.conf
    # your server
    nfsadmin_principal = 'nfsadmin@%s' % env.realm.encode()


    ######################################################
    # Storage
    ######################################################
    # address of the host providing the Storage Component
    # this variable is used by the Sync component
    storage_host = 'https://%s/xmlrpc' % env.server

    # directory where shares can be finded 
    shares_dir = u"/mnt/nfs/shares/"


    ######################################################
    # Sync
    ######################################################
    # address of the host providing the Storage Component
    # this variable is used by the Account component
    sync_host = 'https://%s/xmlrpc' % env.server


    ######################################################
    # Account
    ######################################################
    # address of the host providing the Account Component
    # this variable is used by the other components
    account_host = 'https://%s/xmlrpc' % env.server


    ######################################################
    # Messaging
    ######################################################
    # address and port of the host providing the AMQP
    # this variable is used by the other components
    messaging_host = 'tom.gamma.agorabox.org'
    messaging_port = '5672'

except AttributeError:
    # seems that config file doesn't contains
    # xmlrpc_uri 
    deb.debug("Seems we're not on a functional ipa host, maybe you should run ipa-client-install first")
    # Re raise the exception as we don't know what to do
    raise
