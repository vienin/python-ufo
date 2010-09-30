from debuggable import Debuggable

__version__ = (0, 0, 1)

debugMode = True
debugLevel = 0

progName   = "ufoWS"
syslogOpen = False


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

