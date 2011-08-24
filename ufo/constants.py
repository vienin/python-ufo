"""
All constants used in our components
"""

class FriendshipStatus:
    PENDING_FOLLOWING = 'PENDING_FOLLOWING'
    PENDING_FOLLOWER  = 'PENDING_FOLLOWER'
    FRIEND            = 'FRIEND'
    PENDING_FRIEND    = 'PENDING_FRIEND'
    FOLLOWING         = 'FOLLOWING'
    FOLLOWER          = 'FOLLOWER'
    BLOCKED_USER      = 'BLOCKED_USER'
    NONE_FOLLOWING    = 'NONE_FOLLOWING' # neither, blocked user nor pending following nor following
    NONE_FOLLOWER     = 'NONE_FOLLOWER' # neither, blocked user nor pending follower nor follower
    NONE_FRIEND       = 'NONE_FRIEND' # neither, blocked user nor pending friend nor friend

class ShareDoc:
    # type of notifications
    NEW_SHARED_DOC_NOTIFY = "NEW_SHARED_DOC_NOTIFY"
    NEW_FRIEND_NOTIFY     = "NEW_FRIEND_NOTIFY"
    FRIENDSHIP_INVIT_ACCEPTED_NOTIFY = "FRIENDSHIP_INVIT_ACCEPTED_NOTIFY"
    # where the sqlite3 DB is stored
    DB_FILE               = "/tmp/share_db"
    # type of operations
    PENDING_SHARE_FLAG    = "PENDING"
    ENABLED_SHARE_FLAG    = "ENABLED"
    # permissions
    R_FLAG                = "R"
    RW_FLAG               = "RW"

class Notification:
    # notify or not notify !
    NOTIFY     = 'NOTIFY'
    NOT_NOTIFY = 'NOT_NOTIFY'
    
class Messaging:
    EXCHANGE_LABEL = "UFO_document_sharing"
    
