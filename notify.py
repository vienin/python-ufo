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

import config
import json
import os

import xmlrpclib as rpc

from ipalib.rpc import KerbTransport
from amqplib import client_0_8 as amqp

from ufo.debugger import Debugger
from ufo.constants import Messaging, ShareDoc


class Notify(Debugger):

    def __init__(self):
        pass
    
    def notify_new_shared_doc(self,
                              meta,
                              notify_type,
                              provider,
                              participant,
                              document,
                              permissions):
    
        conn = amqp.Connection(host= config.messaging_host + ':' + 
                               config.messaging_port, 
                               userid="guest",
                               password="guest", 
                               virtual_host="/", 
                               insist=False)
        chan = conn.channel()

        # declare queue and exchange
        # we will send notifications to the queue 
        # to which the participant is subscribed
        chan.queue_declare(queue=participant, 
                           durable=True,
                           exclusive=False, 
                           auto_delete=False)
        chan.exchange_declare(exchange=Messaging.EXCHANGE_LABEL,
                              type="direct", 
                              durable=True, 
                              auto_delete=False,)
        
        # bind the queue with the exchange
        chan.queue_bind(queue=participant, 
                        exchange=Messaging.EXCHANGE_LABEL,
                        routing_key=participant)

        if notify_type == ShareDoc.NEW_SHARED_DOC_NOTIFY:
            dict_to_send = dict(notify_type = ShareDoc.NEW_SHARED_DOC_NOTIFY,
                                provider    = provider,
                                participant = participant,
                                document    = document, 
                                permissions = permissions)

            msg = amqp.Message(json.dumps(dict_to_send))
        else:
            # FIXME  raise another exception
            raise Exception("Error. notify_type not found")

        msg.properties["delivery_mode"] = 2
        chan.basic_publish(msg,
                           exchange=Messaging.EXCHANGE_LABEL,
                           routing_key=participant)
        chan.close()
        conn.close()

    def notify_friendship(self, meta, notify_type, user, new_friend):
        conn = amqp.Connection(host= config.messaging_host + ':' + 
                               config.messaging_port, 
                               userid="guest",
                               password="guest", 
                               virtual_host="/", 
                               insist=False)
        chan = conn.channel()

        # declare queue and exchange
        chan.queue_declare(queue=new_friend, 
                           durable=True,
                           exclusive=False, 
                           auto_delete=False)
        chan.exchange_declare(exchange=Messaging.EXCHANGE_LABEL,
                              type="direct", 
                              durable=True, 
                              auto_delete=False,)
        
        # bind the queue with the exchange
        chan.queue_bind(queue=new_friend, 
                        exchange=Messaging.EXCHANGE_LABEL,
                        routing_key=new_friend)
        
        if notify_type == ShareDoc.NEW_FRIEND_NOTIFY:
            dict_to_send = dict(notify_type = ShareDoc.NEW_FRIEND_NOTIFY,
                                src         = user,
                                dest        = new_friend)
            msg = amqp.Message(json.dumps(dict_to_send))
        elif notify_type == ShareDoc.FRIENDSHIP_INVIT_ACCEPTED_NOTIFY:
            dict_to_send = dict(notify_type = ShareDoc.FRIENDSHIP_INVIT_ACCEPTED_NOTIFY,
                                src         = user,
                                dest        = new_friend)
            msg = amqp.Message(json.dumps(dict_to_send))            
        else:
            # FIXME : raise another exception
            raise Exception("Error. notify_type not found")
        
        msg.properties["delivery_mode"] = 2
        chan.basic_publish(msg,
                           exchange=Messaging.EXCHANGE_LABEL,
                           routing_key=new_friend)
        chan.close()
        conn.close()

    def _recv_callback(self, meta, msg):
        try:     
            self.debug("Start")
            os.environ["KRB5CCNAME"]=meta['apache_env']['KRB5CCNAME']
            
            msg_body    = json.loads(msg.body)
            notify_type = msg_body["notify_type"]
            
            if notify_type == ShareDoc.NEW_FRIEND_NOTIFY:
                # dest is the new friend
                # src is the user who sent the invitation
                src  = msg_body["src"]
                dest = msg_body["dest"]
                self.debug("--> '%s' invites '%s' to be his/her friend" %
                            (src, dest))
                return msg_body

            elif notify_type == ShareDoc.FRIENDSHIP_INVIT_ACCEPTED_NOTIFY:
                # src is the user who receive the invitation
                # dest is the host, who invited src
                src  = msg_body["src"]
                dest = msg_body["dest"]
                self.debug("--> '%s' accepted the friendship invitation sent by '%s'" %
                            (src, dest))
                return msg_body
            
            elif notify_type == ShareDoc.NEW_SHARED_DOC_NOTIFY:
                provider    = msg_body["provider"]
                participant = msg_body["participant"]
                document    = msg_body["document"]
                permissions = msg_body["permissions"]
                # FIXME : don't forget to delete this print 
                # instruction after debugging
                self.debug("--> '%s' shares the document '%s' (%s) with '%s'." % 
                            (provider, document, permissions, participant))
                return msg_body

            else:
                raise Exception("Error. notify_type : %s not found" % 
                                notify_type)
        except ValueError,e :
            # ValueError: No JSON object could be decoded
            # this exception is raised when we receive a not json message
            # TODO : logging
            self.debug("ERROR, raised exception %s"% str(e))        
        except Exception, e:
            self.debug("ERROR, raised exception %s"% str(e))        
            raise e
        finally:
            self.debug("End")

    def get_notification(self, meta, dest_user):
        conn = amqp.Connection(host= config.messaging_host + ':' + 
                               config.messaging_port, 
                               userid="guest",
                               password="guest",
                               virtual_host="/",
                               insist=False)
        chan = conn.channel()
        
        # declare queue and exchange
        chan.queue_declare(queue=dest_user, 
                           durable=True,
                           exclusive=False, 
                           auto_delete=False)
        chan.exchange_declare(exchange=Messaging.EXCHANGE_LABEL,
                              type="direct", 
                              durable=True, 
                              auto_delete=False,)
        
        # bind the queue with the exchange
        chan.queue_bind(queue=dest_user, 
                        exchange=Messaging.EXCHANGE_LABEL,
                        routing_key=dest_user)
        
        # consume the message
        msg = chan.basic_get(dest_user)
        if msg:
            msg_body = self._recv_callback(meta, msg)
            chan.basic_ack(msg.delivery_tag)
            return msg_body
        else:
            return None
        
        chan.close()
        conn.close()
