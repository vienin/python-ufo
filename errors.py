"""

    =============  ========================================
     Error codes                 Exceptions
    =============  ========================================
    6000 - 6199    `ShareDocError` and its subclasses
    6200 - 6299    `UserError` and its subclasses
    =============  ========================================





"""


class PrivateError(StandardError):
    """
    Base class for exceptions that are *never* forwarded in an RPC response.
    """
    # FIXME : faire la destinction entre les types des exceptions: prive ou 
    #         public
    format = ''

    def __init__(self, *arg, **kw):
        if self.format:
            self.msg = self.format % kw
            self.kw = kw
            for (key, value) in kw.iteritems():
                assert not hasattr(self, key), 'conflicting kwarg %s.%s = %r' % (
                    self.__class__.__name__, key, value,
                )
                setattr(self, key, value)
            StandardError.__init__(self, self.msg)

        else:
            StandardError.__init__(self, *arg)

class CCacheError(PrivateError):
    """
    **1101** Raised when component does not recieve Kerberose credentials.

    For example:
    >>> raise CCacheError()
    Traceback (most recent call last):
      ...
    CCacheError: did not receive Kerberos credentials
    """
    errno = 1101
    format = 'did not receive Kerberos credentials'

class BadComponentPerms(PrivateError):
    """
    **1105** Raised when a client has bad permissions on this component

    For example:

    >>> raise BadComponentPerms()
    Traceback (most recent call last):
      ...
    BadComponentPerms: Component permissions incorrect
    """

    errno = 1105
    format = 'Component permissions incorrect'


########################################################################
# Friendship Errors
########################################################################
class BadFriendshipStatus(PrivateError):
    """
    **6001** Raised when a bad friendship status is provided.

    For example:

    >>> raise BadFriendshipStatus()
    Traceback (most recent call last):
      ...
    BadFriendshipStatus: bad friendship status

    """
    errno = 6001
    format = 'bad friendship status'


class AlreadyFollowingError(PrivateError):
    """
    **6002** Raised when a user attempts to invite/accept a user already a following.

    For example:

    >>> raise AlreadyFollowingError()
    Traceback (most recent call last):
      ...
    AlreadyFollowingError: the user you attempt to invite/accept is already a following user.

    """
    errno = 6002
    format = 'the user you attempt to invite/accept is already a following user.'


class AlreadyFollowerError(PrivateError):
    """
    **6012** Raised when a user attempts to invite/accept a user already a follower.

    For example:

    >>> raise AlreadyFollowerError()
    Traceback (most recent call last):
      ...
    AlreadyFollowerError: the user you attempt to invite/accept is already a follower user.

    """
    errno = 6012
    format = 'the user you attempt to invite/accept is already a follower user.'


class NotFollowingError(PrivateError):
    errno = 6003
    format = 'User is not your following'


class NotFollowerError(PrivateError):
    errno = 6013
    format = 'User is not your follower'


class PendingFollowingError(PrivateError):
    """
    **6003** Raised when a user attempts to invite a following user who is already 
    in his pending followings list

    For example:

    >>> raise PendingFollowingError()
    Traceback (most recent call last):
      ...
    PendingFollowingError: user is in the pending followings list

    """
    errno = 6004
    format = 'user is in the pending followings list'


class PendingFollowerError(PrivateError):
    """
    **6013** Raised when a user attempts to invite a follower user who is already 
    in his pending followers list

    For example:

    >>> raise PendingFollowerError()
    Traceback (most recent call last):
      ...
    PendingFollowerError: user is in the pending followers list

    """
    errno = 6014
    format = 'user is in the pending followers list'


class BlockedUserError(PrivateError):
    """
    **6004** Raised when a user attempts to invite a blocked user to be 
    his/her following or his/her follower, 

    For example:

    >>> raise BlockedUserError()
    Traceback (most recent call last):
      ...
    BlockedUserError: blocked user

    """
    errno = 6004
    format = 'User not in the blocked users list'


########################################################################
# File Sharing Errors
########################################################################
class AlreadySharedDocError(PrivateError):
    """
    **6020** Raised when a user attempts to share an already shared document
    or a pending shared document
    For example:

    >>> raise AlreadySharedDocError()
    Traceback (most recent call last):
      ...
    AlreadySharedDocError: Document already shared with this user

    """
    errno = 6020
    format = 'Document already shared with this participant'


class BadOwnerError(PrivateError):
    errno = 6021
    format = 'User not the owner of the file'


class ConflictError(PrivateError):
    errno = 6022
    format = 'Document update conflict.'


########################################################################
# User errors
########################################################################
class UserExistsError(PrivateError): 
    """
    This exception is raised when :
      - the user already exists
    """
    errno = 6201
    format = 'the user already exists'

class UserNotFoundError(PrivateError): 
    """
    This exception is raised when :
      - user not found
    """
    errno = 6202
    format = 'user not found'

class BadAttributeUserError(PrivateError): 
    """
    This exception is raised when :
      - an unknown attribute is provided
    """
    errno = 6203
    format = 'an unknown attribute is provided'

class RequiredAttributeUserError(PrivateError): 
    """
    This exception is raised when :
      - a required attribute is not provided
    """
    errno = 6204
    format = 'a required attribute is not provided'

class UnknownUserError(PrivateError): 
    """
    This exception is raised when :
      - unknown problem occurred
    """
    errno = 6205
    format = 'unknown problem occurred'

