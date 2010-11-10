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


##
# Used if Storage component is installed
##

# Only member of this group can call the Storage component procedures 
storage_admins_group = 'ufoadmins'
# the root principal on the nfs server. See also the idmapd.conf 
# your server
nfsadmin_principal = 'nfsadmin@GAMMA.AGORABOX.ORG'


######################################################
# Storage
######################################################
# address of the host providing the Storage Component
# this variable is used by the Sync component
storage_host = 'https://jerry.gamma.agorabox.org/xmlrpc'

# directory where shares can be finded 
shares_dir = u"/mnt/nfs/shares/"


######################################################
# Sync
######################################################
# address of the host providing the Storage Component
# this variable is used by the Account component
sync_host = 'https://jerry.gamma.agorabox.org/xmlrpc'


######################################################
# Account
######################################################
# address of the host providing the Account Component
# this variable is used by the other components
account_host = 'https://jerry.gamma.agorabox.org/xmlrpc'


######################################################
# Messaging
######################################################
# address and port of the host providing the AMQP
# this variable is used by the other components
messaging_host = 'tom.gamma.agorabox.org'
messaging_port = '5672'

