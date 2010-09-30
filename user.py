from ipalib import api
from ipalib.errors import RequirementError, NotFound
import errors
import os

from ufo.sync import  DocumentHelper, FriendDocument
from ufo.constants import FriendshipStatus, Notification
import config

#########################################################
# USER CLASS
#########################################################
class User(config.Debuggable):
    
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
        
        self.followings         = {} # dic of FriendDocument objects {'login':object, ...}
        self.followers          = {} # dic of FriendDocument objects {'login':object, ...}
        self.pending_followings = {} # dic of FriendDocument objects {'login':object, ...}
        self.pending_followers  = {} # dic of FriendDocument objects {'login':object, ...}
        self.blocked_users      = {} # dic of FriendDocument objects {'login':object, ...}
        
        self.user_name = user_name
        # to use the ticket forwarded by mod_kerb
        os.environ["KRB5CCNAME"]=meta['apache_env']['KRB5CCNAME']    
        
        try:
            api.bootstrap(context='webservices', in_tree=False)
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
        try:
            api.Backend.xmlclient.connect()
        except StandardError:
            # this Exception can be ignored :
            # connect: 'context.xmlclient' already exists in thread 'MainThread'
            pass
        
        # create the document helper, it is usefull to manipulate all 
        # documents stored in the CouchDB Data base
        self._doc_helper = DocumentHelper(FriendDocument, user_name)

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
            self._debug("Start")
            for k,v in args.iteritems():
                # if we receive a bad attribute
                if (k not in self.__dict__):
                    self._debug(("%s is a bad attribute")% (k))
                    raise errors.BadAttributeUserError
                else:
                    setattr(self, k, unicode(v))
        except Exception, e:
            self._debug("ERROR. Exception raised : %s" % str(e))
        finally:
            self._debug("End")

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
            self._debug("Start")
            try:
                response = api.Command.user_show(unicode(self.user_name), all=True)
            except NotFound, e:
                if (e.errno == 4001):
                    # user not found
                    self._debug(("The user '%s' do not exist")% 
                                (self.user_name))
                    raise errors.UserNotFoundError
                else:
                    self._debug(("The user %s do not exist, but errno is equal to %i instead 4001")% (self.user_name, e.errno))
                    raise e
            except Exception, e:
                self._debug(("An unknown exception is raised when we try to populate the user %s. Exception : %s")% (self.user_name, str(e)))
                raise e
            

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
            
            if (self.user_name == 'admin'): 
                # TODO : see if we can get givenname for admin user
                self.first_name = u'Administrator'
            else:
                self.first_name     = response['result']['givenname'][0]
                
            self.last_name      = response['result']['sn'][0]
            self.home_directory = response['result']['homedirectory'][0]
            self.login_shell    = response['result']['loginshell'][0]
            self.groups         = response['result']['memberof_group']
            self.uidnumber      = int(response['result']['uidnumber'][0])
            self.gidnumber      = int(response['result']['gidnumber'][0])
            self.realm          = response["result"]["krbprincipalname"][0].split('@')[1]
            to_return =  dict(
                user_name      = self.user_name,
                first_name     = self.first_name,
                last_name      = self.last_name,
                home_directory = self.home_directory,
                login_shell    = self.login_shell,
                groups         = self.groups,
                uidnumber      = self.uidnumber,
                gidnumber      = self.gidnumber
                )
            try:
                # Mail
                self.mail = response['result']['mail'][0]
                to_return['mail'] = self.mail
            except KeyError:
                # this user do not have a mail
                self.mail = None
            try:
                # Street
                self.street = response['result']['street'][0]
                to_return['street'] = self.street
            except KeyError:
                # this user do not have a street
                self.street = None

            # followers
            self.followers = {}
            for f in list(FriendDocument.by_status(self._doc_helper.database, key=FriendshipStatus.FOLLOWER)):
                self.followers[f.login] = f
            # self.followers is something like : 
            # {'lambert': FriendDocumentObject, 'michu': FriendDocumentObject, ...}

            # pending_followers
            self.pending_followers = {}
            for f in list(FriendDocument.by_status(self._doc_helper.database, 
                                           key=FriendshipStatus.PENDING_FOLLOWER)):
                self.pending_followers[f.login] = f
            # self.pending_followers is something like : 
            # {'lambert': FriendDocumentObject, 'michu': FriendDocumentObject, ...}

            # followings
            self.followings = {}
            for f in list(FriendDocument.by_status(self._doc_helper.database, 
                                           key=FriendshipStatus.FOLLOWING)):
                self.followings[f.login] = f
            # self.followings is something like : 
            # {'lambert': FriendDocumentObject, 'michu': FriendDocumentObject, ...}

            # pending_followings
            self.pending_followings = {}
            for f in list(FriendDocument.by_status(self._doc_helper.database, 
                                           key=FriendshipStatus.PENDING_FOLLOWING)):
                self.pending_followings[f.login] = f
            # self.pending_followings is something like : 
            # {'lambert': FriendDocumentObject, 'michu': FriendDocumentObject, ...}

            # blocked users
            self.blocked_users = {}
            for f in list(FriendDocument.by_status(self._doc_helper.database, 
                                           key=FriendshipStatus.BLOCKED_USER)):
                self.blocked_users[f.login] = f
            # self.blocked_users is something like : 
            # {'lambert': FriendDocumentObject, 'michu': FriendDocumentObject, ...}
      
            self._debug(("The user %s was populated.") % (self.user_name))
            return to_return
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug("End")

    def create(self):
        """
        Create the user on the ldap. 
        You must call initialize before with at least : 
        first_name, last_name and realm attributes.
        This method update also the user object (see populate method)
        Exemple : 
        TODO : add an example of use
        """
        if (self.user_name  == None or
            self.first_name == None or
            self.last_name == None or
            self.realm  == None ):
            raise errors.RequiredAttributeUserError
        other_args = dict(givenname=unicode(self.first_name), 
                          sn=unicode(self.last_name), 
                          gecos=unicode(self.user_name),
                          krbprincipalname=unicode(self.user_name +
                                                   '@' + self.realm),
                          all=True, raw=True)                          
        
        if (self.mail != None):
            other_args['mail'] = self.mail
        if (self.street != None):
            other_args['street'] = self.street
        if (self.home_directory != None):
            other_args['homedirectory'] = self.home_directory
    
        try:
            api.Command.user_add(unicode(self.user_name), **other_args)
            self._debug(("The user %s was added on the ldap.") % (self.user_name))
            self.populate()
        except RequirementError, e:
            # a required parameter is not provided
            # the following exception is raised
            # RequirementError with 3007 as errno
            raise errors.RequiredAttributeUserError
        except Exception, e:
            self._debug(('An unknown exception was raised during the adding of %s on the ldap')%
                        (self.user_name))
            raise e

    def update(self):
        """
        Update the informations about the user on the ldap.
        Attention you must call initialize() method before.
        """
        ipa_kw = {}     
        if (self.first_name != None):
            ipa_kw['givenname']=unicode(self.first_name)
        if (self.last_name != None):
            ipa_kw['sn']=unicode(self.last_name)
        if (self.home_directory != None):
            ipa_kw['homedirectory']=unicode(self.home_directory)
        if (self.mail != None):
            ipa_kw['mail']=unicode(self.mail)
        if (self.user_password != None):
            # TODO : pas trop top le password dans l objet...
            ipa_kw['userpassword']=unicode(self.user_password)
        if (self.street != None):
            ipa_kw['street']=unicode(self.street)

        # update on the ldap
        self._debug("ipa_kw : %s" % ipa_kw)
        api.Command.user_mod(unicode(self.user_name), all=True, raw=True, **ipa_kw)
        
        # update the database (FriendDocuments)
        self._doc_helper.update(self.followings.values())
        self._doc_helper.update(self.followers.values())
        self._doc_helper.update(self.pending_followings.values())
        self._doc_helper.update(self.pending_followers.values())
        self._doc_helper.update(self.blocked_users.values())

        self._debug(("The user %s was updated.") % (self.user_name))

    def delete(self):
        """
        Delete the user from the ldap
        """
        try:
            api.Command.user_del(unicode(self.user_name))
            self._debug(("The user %s was deleted.") % (self.user_name))
        except NotFound, e:
            if (e.errno == 4001):
                # user not found
                raise errors.UserNotFoundError
            else:
                self._debug(("The user %s do not exist, but errno is equal to %i instead 4001")%
                            (self.user_name, e.errno))
                raise e
        except Exception, e:
            self._debug(("An unknown exception is raised when we try to populate the user %s. Exception : %s")%
                        (self.user_name, str(e)))
            raise e

################################################################################
# FRIENDSHIP METHODS
################################################################################
    def add_pending_following(self, new_pending_following, notify = True):
        """
        add a new friend to the pending followings list of the current user.
        The concerned user will be notified (notify=True) or not (notify=False) 
        of this addition
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError

            # check if the user is already a pending following or 
            # a blocked user. If it is, we raise an exception
            if new_pending_following in self.blocked_users.keys():
                raise BlockedUserError()
            elif new_pending_following in self.pending_followings.keys():
                raise PendingFollowingError()
            
            # add new_pending_following in the pending followings list
            if notify :
                notification = Notification.NOTIFY
            else:
                notification = Notification.NOT_NOTIFY
              
            friend_object = FriendDocument(login        = unicode(new_pending_following),
                                   status       = FriendshipStatus.PENDING_FOLLOWING,
                                   notification = notification,)
                                   
            self.pending_followings[unicode(new_pending_following)] = friend_object
            # add the friend_object in the database
            friend_object.store(self._doc_helper.database)
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def remove_pending_following(self, pending_following):
        """
        remove the friend from the pending followings list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError
            # object to delete from the database
            friend_object = self.pending_followings[unicode(pending_following)]
            self._doc_helper.delete(friend_object)
            # remove pending_following from the pending followings list
            del self.pending_followings[unicode(pending_following)]          
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def add_following(self, new_following, notify = True):
        """
        description ...

        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError

            # To adding the new_following friend we just change the status 
            # of the pending_following corresponding to this friend to 
            # FriendshipStatus.FOLLOWING instead of 
            # FriendshipStatus.PENDING_FOLLOWING
            
            # First, we must find this pending_following.
            # We suppose that we can not have two friends on the data base with
            # the same login, which means that, we can consider friend as a unique key
            if new_following in self.pending_followings.keys():
                # it is ok
                # fetch the friend object
                friend_object = self.pending_followings[new_following]
                # change the status from 'PENDING_FOLLOWING' to 'FOLLOWING'
                friend_object.status = FriendshipStatus.FOLLOWING
                if notify :
                    friend_object.notification = Notification.NOTIFY
                else:
                    friend_object.notification = Notification.NOT_NOTIFY
                # delete this object from the pending_followings list
                del self.pending_followings[new_following]
                # update the 'followings' list
                self.followings[new_following] = friend_object
                # update the database
                self._doc_helper.update(self.followings[new_following])
            else:
                # we cannot adding a following friend directly 
                # without passing by the "pending_following" state
                # we log this and we ignore this call of the method
                self._debug('WARNING. We cannot adding a following friend directly'
                            +' without passing by the "pending_following" state.')

        except Exception, e:
            self._debug("ERROR. Exception raised : %s" % str(e))
            raise e
        finally:
            self._debug("End")

    def remove_following(self, following):
        """
        remove the friend from the followings list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError
            # object to delete from the database
            friend_object = self.followings[unicode(following)]
            self._doc_helper.delete(friend_object)
            # remove following from the followings list
            del self.followings[unicode(following)]
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def add_pending_follower(self, new_pending_follower, notify = True):
        """
        add a new friend to the pending followers list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap and database
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError

            # check if the user is already a pending follower or 
            # a blocked user. If it is, we raise an exception
            if new_pending_follower in self.blocked_users.keys():
                raise BlockedUserError()
            elif new_pending_follower in self.pending_followers.keys():
                raise errors.PendingFollowerError()
                      
            if notify :
                notification = Notification.NOTIFY
            else:
                notification = Notification.NOT_NOTIFY
              
            # add new_pending_follower in the pending followers list
            friend_object = FriendDocument(login        = unicode(new_pending_follower),
                                   status       = FriendshipStatus.PENDING_FOLLOWER,
                                   notification = notification,)
                                   
            self.pending_followers[unicode(new_pending_follower)] = friend_object
            # add the friend_object in the database
            friend_object.store(self._doc_helper.database)
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def remove_pending_follower(self, pending_follower):
        """
        remove the friend from the pending followers list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError
            # object to delete from the database
            friend_object = self.pending_followers[unicode(pending_follower)]
            self._doc_helper.delete(friend_object)
            # remove pending_follower from the pending followers list
            del self.pending_followers[unicode(pending_follower)]          
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def add_follower(self, new_follower, notify = True):
        """
        description ...

        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError

            # To adding the new_follower friend we just change the status 
            # of the pending_follower corresponding to this friend to 
            # FriendshipStatus.FOLLOWER instead of 
            # FriendshipStatus.PENDING_FOLLOWER.

            # First, we must find this pending_follower.
            # We suppose that we can not have two friend on the data base,
            # with the same login, which means that we can consider friend 
            # as a unique key
            if new_follower in self.pending_followers.keys():
                # it is ok
                # fetch the friend object
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
                self._doc_helper.update(self.followers[new_follower])
            else:
                # we cannot adding a follower friend directly 
                # without passing by the "pending_follower" state
                # we log this and we ignore this call of the method
                self._debug('WARNING. We cannot adding a following friend directly witou passing by the "pending_following" state.')
        except Exception, e:
            self._debug("ERROR. Exception raised : %s" % str(e))
            raise e
        finally:
            self._debug("End")

    def remove_follower(self, follower):
        """
        remove the friend from the followers list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError
            # object to delete from the database
            friend_object = self.followers[unicode(follower)]
            self._doc_helper.delete(friend_object)
            # remove follower from the followers list
            del self.followers[unicode(follower)]          
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def add_blocked_user(self, blocked_user, notify = True):
        """
        description ...

        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError

            # FIXME : when we add a new blocked_user, check if it figures 
            # on the others lists

            # check if the user is already a blocked one
            if blocked_user in self.blocked_users.keys():
                # nothing to do; exit
                self._debug("the user %s is already a blocked user" % (blocked_user))
                return
            elif blocked_user in self.pending_followers.keys():
                self._debug("WARNING: you can not blocked an pending follower")
                raise Exception("you can not blocked an pending follower")
            elif blocked_user in self.pending_followings.keys():
                self._debug("WARNING: you can not blocked an pending following")
                raise Exception("you can not blocked an pending following")
            elif blocked_user in self.followers.keys():
                self._debug("WARNING: you can not blocked a follower")
                raise Exception("you can not blocked a follower")
            elif blocked_user in self.followings.keys():
                self._debug("WARNING: you can not blocked a following")
                raise Exception("you can not blocked a following")
            else:
                if notify :
                    notification = Notification.NOTIFY
                else:
                    notification = Notification.NOT_NOTIFY
                
                # add blocked_user in the blocked_users list
                friend_object = FriendDocument(login        = unicode(blocked_user),
                                       status       = FriendshipStatus.BLOCKED_USER,
                                       notification = notification,)
                
                # add blocked_user in the blocked_users list
                self.blocked_users[unicode(blocked_users)] = friend_object
                # update the database
                friend_object.store(self._doc_helper.database)

        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

    def remove_blocked_user(self, blocked_user):
        """
        remove the blocked_user from the blocked_users list of the current user
        """
        try:
            self._debug('Start')
            # populate the object user with the informations 
            # fetched from ldap
            try:
                self.populate()
            except errors.UserNotFoundError:
                raise errors.UserNotFoundError
            # object to delete from the database
            friend_object = self.blocked_users[unicode(blocked_user)]
            self._doc_helper.delete(friend_object)
            # remove blocked_user from the blocked_users list
            del self.blocked_users[unicode(blocked_user)]
        except Exception, e:
            self._debug("ERROR. Raised exception : %s" % str(e))
            raise e
        finally:
            self._debug('End')

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

