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

import os

from ipalib import api
from ipalib.errors import RequirementError, NotFound

from ufo.errors import *
from ufo.debugger import Debugger
from ufo.database import DocumentHelper
from ufo.sharing import FriendDocument
from ufo.constants import FriendshipStatus, Notification
from ufo.config import ufo_in_server


class User(Debugger):
    
    def __init__(self, meta, user_name):
        """
        Instantiation of the user
        """
        self.user_name          = None
        self.first_name         = None
        self.last_name          = None
        self.realm              = None
        self.home_directory     = None
        self.login_shell        = None
        self.mail               = None
        self.user_password      = None  # TODO : pas top en terme de secu
        self.street             = None
        self.groups             = None
        self.uidnumber          = None
        self.gidnumber          = None
        self.quota              = None

        self.followings         = {} # dic of FriendDocument objects {'login':object, ...}
        self.followers          = {} # dic of FriendDocument objects {'login':object, ...}
        self.pending_followings = {} # dic of FriendDocument objects {'login':object, ...}
        self.pending_followers  = {} # dic of FriendDocument objects {'login':object, ...}
        self.blocked_users      = {} # dic of FriendDocument objects {'login':object, ...}

        self.user_name = user_name
        # to use the ticket forwarded by mod_kerb
        os.environ["KRB5CCNAME"]=meta['apache_env']['KRB5CCNAME']    

        try:
            api.bootstrap(context='webservices', in_tree=False, in_server=ufo_in_server)
        except StandardError:
            # the following exceptions can be ignored. That's no problem
            # API.bootstrap() already called
            pass

        try:
            api.finalize()            
        except StandardError:
            # the following exceptions can be ignored. That's no problem
            # API.finalize() already called
            pass

        if ufo_in_server:
            try:
                api.Backend.ldap2.connect(ccache=api.Backend.krb.default_ccname())
            except StandardError:
                # this Exception can be ignored :
                # connect: 'context.xmlclient' already exists in thread 'MainThread'
                pass
        else:
            try:
                api.Backend.xmlclient.connect()
            except StandardError:
                # this Exception can be ignored :
                # connect: 'context.xmlclient' already exists in thread 'MainThread'
                pass

        

    def initialize(self, args):
        """
        Initialize the object attributes by the informations 
        passed in arguments 'args'. 
        We must at least give the following attributes :
        - first_name
        - last_name
        - realm

        @param args: looks like :
        {'first_name'='my_first_name',
        last_name='my_last_name',
        realm = 'GAMMA.AGORABOX.ORG',
        home_directory='/home/user',
        mail='my_mail@domain.tld',
        street='some where',
        login_shell='/bin/sh'
        }

        """
        try:
            self.debug("Start")

            for k,v in args.iteritems():
                # if we receive a bad attribute
                if (k not in self.__dict__):
                    self.debug(("%s is a bad attribute")% (k))
                    raise BadAttributeUserError()
                else:
                    setattr(self, k, unicode(v))

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug("End")

    def populate(self):
        """
        TODO : consider the new status of friends (following, followers...)
        Initialize the object attributes by the informations 
        fetched from the ldap server
        @returns : some thing like :
        {'first_name'='my_first_name',
        last_name='my_last_name',
        home_directory='/home/user',
        mail='my_mail@domain.tld',
        street='some where',
        login_shell='/bin/sh',
        friends = [u'raca@GAMMA.AGORABOX.ORG', u'ufoadmin@GAMMA.AGORABOX.ORG']
        blocked_friends = [u'mechant@GAMMA.AGORABOX.ORG']
        }
        """
        try:
            self.debug("Start")

            try:
                response = api.Command.user_show(unicode(self.user_name), all=True)

            except NotFound, e:
                if (e.errno == 4001):
                    # user not found
                    self.debug("The user '%s' do not exist" % self.user_name)
                    raise UserNotFoundError()

                self.debug_exception()
                raise

            except Exception, e:
                if isinstance(e, PrivateError):
                    self.debug("Raising exception: %s, %s" % (type(e), e))
                else:
                    self.debug_exception()

                raise

            # WARNING : attributes are always in lowercase even if it is not the case in the ldap schema

            # response contains this structure 
            # {'result': {'cn': (u'rachid Alahyane',),
            #             'dn': u'uid=raca,cn=users,cn=accounts,dc=gamma,dc=agorabox,dc=org',
            #             'gecos': (u'raca',),
            #             'gidnumber': (u'45598597',),
            #             'givenname': (u'rachid',),
            #             'homedirectory': (u'/home/raca',),
            #             'ipauniqueid': (u'fbdfbfdc-64e7-11df-aa6f-525412000001',),
            #             'krbprincipalname': (u'raca@GAMMA.AGORABOX.ORG',),
            #             'loginshell': (u'/bin/sh',),
            #             'mail': (u'raca@yahoo.fr',),
            #             'memberof_group': (u'ipausers',),
            #             'objectclass': (u'top',
            #                             u'person',
            #                             u'organizationalperson',
            #                             u'inetorgperson',
            #                             u'inetuser',
            #                             u'posixaccount',
            #                             u'krbprincipalaux',
            #                             u'krbticketpolicyaux',
            #                             u'radiusprofile',
            #                             u'ipaobject'),
            #             'sn': (u'Alahyane',),
            #             'street': (u'quelques parts',),
            #             'uid': (u'raca',),
            #             'uidnumber': (u'45599032',)},
            #  'summary': None,
            #  'value': u'raca'}
            # if a simple user or : 
            # {'result': {'dn': u'uid=admin,cn=users,cn=accounts,dc=gamma,dc=agorabox,dc=org',
            #             'homedirectory': (u'/home/admin',),
            #             'loginshell': (u'/bin/bash',),
            #             'memberof_group': (u'admins',),
            #             'memberof_rolegroup': (u'replicaadmin',),
            #             'memberof_taskgroup': (u'managereplica', u'deletereplica'),
            #             'sn': (u'Administrator',),
            #             'uid': (u'admin',)},
            #  'summary': None,
            #  'value': u'admin'}        
            # if an admin user.
            
            if self.user_name == 'admin': 
                # TODO : see if we can get givenname for admin user
                self.first_name = u'Administrator'
            else:
                self.first_name = response['result']['givenname'][0]

            self.last_name      = response['result']['sn'][0]
            self.home_directory = response['result']['homedirectory'][0]
            self.login_shell    = response['result']['loginshell'][0]
            self.groups         = response['result'].get('memberof_group', [])
            self.uidnumber      = int(response['result']['uidnumber'][0])
            self.gidnumber      = int(response['result']['gidnumber'][0])
            self.realm          = response["result"]["krbprincipalname"][0].split('@')[1]

            to_return = { 'user_name'      : self.user_name,
                          'first_name'     : self.first_name,
                          'last_name'      : self.last_name,
                          'home_directory' : self.home_directory,
                          'login_shell'    : self.login_shell,
                          'groups'         : self.groups,
                          'uidnumber'      : self.uidnumber,
                          'gidnumber'      : self.gidnumber }

            try:
                self.mail = response['result']['mail'][0]
                to_return['mail'] = self.mail
            except KeyError:
                self.mail = None

            try:
                self.street = response['result']['street'][0]
                to_return['street'] = self.street
            except KeyError:
                self.street = None

            # Create the document helper, it is usefull to manipulate all
            # documents stored in the CouchDB database.
            self.friend_helper = DocumentHelper(FriendDocument, self.user_name)

            self.followers = {}
            self.followings = {}
            self.pending_followers = {}
            self.pending_followings = {}

            friends = { FriendshipStatus.FOLLOWER  : self.followers, 
                        FriendshipStatus.FOLLOWING : self.followings,
                        FriendshipStatus.PENDING_FOLLOWER  : self.pending_followers,
                        FriendshipStatus.PENDING_FOLLOWING : self.pending_followings }

            for friend_doc in self.friend_helper.by_status():
                friends[friend_doc.status][friend_doc.login] = friend_doc

            self.debug(("The user %s was populated.") % (self.user_name))
            return to_return

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug("End")

    def create(self):
        """
        Create the user on the ldap. 
        You must call initialize before with at least : 
        first_name, last_name and realm attributes.
        This method update also the user object (see populate method)
        Exemple : 
        TODO : add an example of use
        """
        if (not (self.user_name and self.first_name and self.last_name and self.realm)):
            raise RequiredAttributeUserError()

        other_args = { 'krbprincipalname' : unicode(self.user_name + '@' + self.realm),
                       'givenname' : unicode(self.first_name),
                       'gecos'     : unicode(self.user_name),
                       'sn'  : unicode(self.last_name), 
                       'all' : True,
                       'raw' : True }

        if (self.mail != None):
            other_args['mail'] = self.mail

        if (self.street != None):
            other_args['street'] = self.street

        if (self.home_directory != None):
            other_args['homedirectory'] = self.home_directory

        if (self.user_password != None):
            other_args['userpassword'] = self.user_password

        if (self.quota != None):
            other_args['setattr'] = u"quota=%s" % self.quota

        try:
            api.Command.user_add(unicode(self.user_name), **other_args)
            self.debug(("The user %s was added on the ldap.") % (self.user_name))
            self.populate()

        except RequirementError, e:
            # a required parameter is not provided the following exception is raised
            # RequirementError with 3007 as errno
            raise RequiredAttributeUserError()

        except Exception, e:
            self.debug(('An unknown exception was raised during the adding of %s on the ldap')%
                        (self.user_name))
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

    def update(self):
        """
        Update the informations about the user on the ldap.
        Attention you must call initialize() method before.
        """
        try:
            ipa_kw = {}     
            if self.first_name:
                ipa_kw['givenname']=unicode(self.first_name)

            if self.last_name:
                ipa_kw['sn']=unicode(self.last_name)

            if self.home_directory:
                ipa_kw['homedirectory']=unicode(self.home_directory)

            if self.mail:
                ipa_kw['mail']=unicode(self.mail)

            if self.user_password:
                # TODO : pas trop top le password dans l objet...
                ipa_kw['userpassword']=unicode(self.user_password)

            if self.street:
                ipa_kw['street']=unicode(self.street)

            # update on the ldap
            self.debug("ipa_kw : %s" % ipa_kw)
            api.Command.user_mod(unicode(self.user_name), all=True, raw=True, **ipa_kw)

            # update the database (FriendDocuments)
            self.friend_helper.update(self.followings.values())
            self.friend_helper.update(self.followers.values())
            self.friend_helper.update(self.pending_followings.values())
            self.friend_helper.update(self.pending_followers.values())
            self.friend_helper.update(self.blocked_users.values())

            self.debug("The user %s was updated." % self.user_name)

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

    def delete(self):
        """
        Delete the user from the ldap
        """
        try:
            api.Command.user_del(unicode(self.user_name))
            self.debug(("The user %s was deleted.") % (self.user_name))

        except NotFound, e:
            if e.errno == 4001:
                raise UserNotFoundError()

            self.debug("The user %s do not exist, but errno is equal to %i instead 4001"
                       % (self.user_name, e.errno))
            raise

        except Exception, e:
            self.debug("An unknown exception is raised when we try to populate the user %s."
                        % self.user_name)
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

    def get_picture(self):
        response = api.Command.user_show(unicode(self.user_name), all=True, raw=True)
        try:
            return response['result']['jpegphoto'][0]
        except:
            return ""

    def set_picture(self, picture):
        ipa_kw = { "setattr" : u"jpegphoto=" + picture }
        api.Command.user_mod(unicode(self.user_name), all=True, raw=True, **ipa_kw)

    def add_pending_following(self, new_pending_following, notify=True):
        """
        add a new friend to the pending followings list of the current user.
        The concerned user will be notified (notify=True) or not (notify=False) 
        of this addition
        """
        try:
            self.debug('Start')

            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # check if the user is already a pending following or 
            # a blocked user. If it is, we raise an exception
            if new_pending_following in self.blocked_users.keys():
                raise BlockedUserError()

            elif new_pending_following in self.followings.keys():
                raise AlreadyFollowingError()

            elif new_pending_following in self.pending_followings.keys():
                raise PendingFollowingError()

            # add new_pending_following in the pending followings list
            notification = { True  : Notification.NOTIFY,
                             False : Notification.NOT_NOTIFY }.get(notify)

            # Add the friend in the database
            friend_doc = self.friend_helper.create(login=unicode(new_pending_following),
                                                   status=FriendshipStatus.PENDING_FOLLOWING,
                                                   notification=notification)

            self.pending_followings[unicode(new_pending_following)] = friend_doc

        except PrivateError, e:
            self.debug("Raising exception: %s, %s" % (type(e), e))
            raise

        except Exception, e:
            self.debug_exception()
            raise

        finally:
            self.debug('End')

    def remove_pending_following(self, pending_following):
        """
        remove the friend from the pending followings list of the current user
        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # object to delete from the database
            friend_doc = self.pending_followings[unicode(pending_following)]
            self.friend_helper.delete(friend_doc)

            # remove pending_following from the pending followings list
            del self.pending_followings[unicode(pending_following)]

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def add_following(self, new_following, notify = True):
        """
        description ...

        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # To adding the new_following friend we just change the status 
            # of the pending_following corresponding to this friend to 
            # FriendshipStatus.FOLLOWING instead of 
            # FriendshipStatus.PENDING_FOLLOWING
            
            # First, we must find this pending_following.
            # We suppose that we can not have two friends on the data base with
            # the same login, which means that, we can consider friend as a unique key
            if new_following in self.pending_followings.keys():
                # it is ok, fetch the friend object
                friend_doc = self.pending_followings[new_following]

                # change the status from 'PENDING_FOLLOWING' to 'FOLLOWING'

                friend_doc.status = FriendshipStatus.FOLLOWING
                friend_doc.notification = { True  : Notification.NOTIFY,
                                            False : Notification.NOT_NOTIFY }.get(notify)

                # delete this object from the pending_followings list
                del self.pending_followings[new_following]

                # update the 'followings' list
                self.followings[new_following] = friend_doc

                # update the database
                self.friend_helper.update(friend_doc)

            else:
                # we cannot adding a following friend directly 
                # without passing by the "pending_following" state
                # we log this and we ignore this call of the method
                self.debug('WARNING. We cannot adding a following friend directly'
                            +' without passing by the "pending_following" state.')

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug("End")

    def remove_following(self, following):
        """
        remove the friend from the followings list of the current user
        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # object to delete from the database
            friend_doc = self.followings[unicode(following)]
            self.friend_helper.delete(friend_doc)

            # remove following from the followings list
            del self.followings[unicode(following)]

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def add_pending_follower(self, new_pending_follower, notify = True):
        """
        add a new friend to the pending followers list of the current user
        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap and database
            self.populate()

            # check if the user is already a pending follower or 
            # a blocked user. If it is, we raise an exception
            if new_pending_follower in self.blocked_users.keys():
                raise BlockedUserError()

            elif new_pending_follower in self.pending_followers.keys():
                raise PendingFollowerError()
                      
            if notify :
                notification = Notification.NOTIFY
            else:
                notification = Notification.NOT_NOTIFY

            # Add the friend in the database
            friend_doc = self.friend_helper.create(login=unicode(new_pending_follower),
                                                   status=FriendshipStatus.PENDING_FOLLOWER,
                                                   notification=notification)

            self.pending_followers[unicode(new_pending_follower)] = friend_doc

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def remove_pending_follower(self, pending_follower):
        """
        remove the friend from the pending followers list of the current user
        """
        try:
            self.debug('Start')

            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # object to delete from the database
            friend_doc = self.pending_followers[unicode(pending_follower)]
            self.friend_helper.delete(friend_doc)

            # remove pending_follower from the pending followers list
            del self.pending_followers[unicode(pending_follower)]  
        
        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def add_follower(self, new_follower, notify=True):
        """
        description ...

        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # To adding the new_follower friend we just change the status 
            # of the pending_follower corresponding to this friend to 
            # FriendshipStatus.FOLLOWER instead of FriendshipStatus.PENDING_FOLLOWER.

            # First, we must find this pending_follower.
            # We suppose that we can not have two friend on the data base,
            # with the same login, which means that we can consider friend 
            # as a unique key
            if new_follower in self.pending_followers.keys():
                # it is ok, fetch the friend object
                friend_object = self.pending_followers[new_follower]

                # change the status from 'PENDING_FOLLOWER' to 'FOLLOWER'
                friend_object.status = FriendshipStatus.FOLLOWER
                if notify :
                    friend_object.notification = Notification.NOTIFY
                else:
                    friend_object.notification = Notification.NOT_NOTIFY

                # delete this object from the pending_followers list
                del self.pending_followers[new_follower]

                # update the 'followers' list
                self.followers[new_follower] = friend_object

                # update the database
                self.friend_helper.update(self.followers[new_follower])

            else:
                # we cannot adding a follower friend directly 
                # without passing by the "pending_follower" state
                # we log this and we ignore this call of the method
                self.debug('WARNING. We cannot adding a following friend directly'
                           ' without passing by the "pending_following" state.')

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug("End")

    def remove_follower(self, follower):
        """
        remove the friend from the followers list of the current user
        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # object to delete from the database
            friend_object = self.followers[unicode(follower)]
            self.friend_helper.delete(friend_object)

            # remove follower from the followers list
            del self.followers[unicode(follower)]
       
        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def add_blocked_user(self, blocked_user, notify = True):
        """
        description ...

        """
        try:
            self.debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # FIXME : when we add a new blocked_user, check if it figures 
            # on the others lists

            # check if the user is already a blocked one
            if blocked_user in self.blocked_users.keys():
                # nothing to do; exit
                self.debug("the user %s is already a blocked user" % (blocked_user))
                return

            elif blocked_user in self.pending_followers.keys():
                self.debug("WARNING: you can not blocked an pending follower")
                raise Exception("you can not blocked an pending follower")

            elif blocked_user in self.pending_followings.keys():
                self.debug("WARNING: you can not blocked an pending following")
                raise Exception("you can not blocked an pending following")

            elif blocked_user in self.followers.keys():
                self.debug("WARNING: you can not blocked a follower")
                raise Exception("you can not blocked a follower")

            elif blocked_user in self.followings.keys():
                self.debug("WARNING: you can not blocked a following")
                raise Exception("you can not blocked a following")

            else:
                if notify :
                    notification = Notification.NOTIFY
                else:
                    notification = Notification.NOT_NOTIFY

                # Add the friend in the database
                friend_doc = self.friend_helper.create(login=unicode(blocked_user),
                                                       status=FriendshipStatus.BLOCKED_USER,
                                                       notification=notification)
    
                self.blocked_users[unicode(blocked_user)] = friend_doc

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def remove_blocked_user(self, blocked_user):
        """
        remove the blocked_user from the blocked_users list of the current user
        """
        try:
            self.debug('Start')

            # populate the object user with the informations 
            # fetched from ldap
            self.populate()

            # object to delete from the database
            friend_object = self.blocked_users[unicode(blocked_user)]
            self.friend_helper.delete(friend_object)

            # remove blocked_user from the blocked_users list
            del self.blocked_users[unicode(blocked_user)]

        except Exception, e:
            if isinstance(e, PrivateError):
                self.debug("Raising exception: %s, %s" % (type(e), e))
            else:
                self.debug_exception()

            raise

        finally:
            self.debug('End')

    def has_follower(self, user):
        """
        check if 'user' is a 'follower' of the current user
        return True or False
        """
        return user in self.followers.keys()

    def has_pending_follower(self, user):
        """
        check if 'user' is a 'pending follower' of the current user
        return True or False
        """
        return user in self.pending_followers.keys()

    def has_following(self, user):
        """
        check if 'user' is a 'following' of the current user
        return True or False
        """
        return user in self.followings.keys()

    def has_pending_following(self, user):
        """
        check if 'user' is a 'pending following' of the current user
        return True or False
        """
        return user in self.pending_followings.keys()

    def has_blocked_user(self, user):
        """
        check if 'user' is a 'blocked user' by the current user
        return True or False
        """
        return user in self.blocked_users.keys()

