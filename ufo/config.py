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
    storage_host = 'https://%s/xmlrpc' % server

    # directory where shares can be finded 
    fs_mount_point = u"/mnt/nfs/shares/"

    # the admin nfs keytab
    nfs_admin_keytab = '/etc/httpd/conf/nfs.keytab'

    ######################################################
    # Sync
    ######################################################
    # address of the host providing the Storage Component
    # this variable is used by the Account component
    sync_host = 'https://%s/xmlrpc' % server
    sync_public_user = 'public'
    sync_public_user_keytab = '/etc/httpd/conf/public.keytab'

    ######################################################
    # Account
    ######################################################
    # address of the host providing the Account Component
    # this variable is used by the other components
    account_host = 'https://%s/xmlrpc' % server

    ######################################################
    # CouchDB
    ######################################################
    couchdb_host = server
    couchdb_port = 5984

    ######################################################
    # Sync Spawner
    ######################################################
    sync_spawner_port = 5000
    sync_spawner_authkey = "jk28jsdf_39!39FksFd"

    ######################################################
    # Quota daemon
    ######################################################
    quota_daemon_port = 20000
    quota_daemon_authkey = "kjsdn,,2378(,sdfljs!"
    nfs_export = "/"

except AttributeError, e:
    # seems that config file doesn't contains xmlrpc_uri
    import syslog
    syslog.syslog(syslog.LOG_WARNING,
                  "Seems we're not on a functional ipa host, maybe you should run ipa-client-install first")
    # Re raise the exception as we don't know what to do
    raise
