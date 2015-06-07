#!/usr/bin/env python
import pika, os, uuid, logging,sys, ConfigParser
import json
import time
import threading

logging.basicConfig()

#####################################################################################################################
# CR: I'll write all my comments starting with CR: if you don't mind, so you'll understand why I made those changes #
# TODO: I'll write stuff starting with TODO if it need to be done eventually                                        #
#####################################################################################################################

# For cli
default_configuration_file = 'rabbitcoat.conf'

def validate(value, current, default=None):
    if ((value is None) or (value == "")):
        if ((not (default is None)) and ((current is None) or (current == ""))):
            return default
        else:
            return current
    else:
        return value

class RabbitFrame(threading.Thread):

    def __init__(self, logger, config, queue, server=None, user=None, password=None, vhost=None, timeout=None):
        self.server = self.user = self.password = self.vhost = self.timeout = None

        self.logger = logger
        self.queue = queue
        
        # Is the frame ready to start
        self._ready = False

        self._ioloop = None
        
        # Later this could be changed, but code declaring the exchange will need to be added.
        self.exchange = queue
        self.closing = False

        self.config = config
        self.__loadConfiguration()
        self.__initInfrastructure(server, user, password, vhost, timeout)

    def __loadConfiguration(self):

        parser = ConfigParser.SafeConfigParser(allow_no_value=True)
        parser.read(self.config)
        
        self.server    = validate(parser.get('RABBITMQ', 'server')      ,self.server)
        self.user      = validate(parser.get('RABBITMQ', 'user')        ,self.user)
        self.vhost     = validate(parser.get('RABBITMQ', 'vhost')       ,self.vhost    ,self.user)
        self.password  = validate(parser.get('RABBITMQ', 'password')    ,self.password)
        self.timeout   = validate(parser.getint('RABBITMQ', 'timeout')     ,self.timeout  ,5)

    def __setInfrastructure(self, server=None, user=None, password=None, vhost=None, timeout=None):
        self.server   = validate(server,self.server)
        self.user     = validate(user,self.user)
        self.password = validate(password,self.password)
        self.vhost    = validate(vhost,self.vhost)
        self.timeout  = validate(timeout,self.timeout)

    def __initInfrastructure(self, server=None, user=None, password=None, vhost=None, timeout=None):
        self.__setInfrastructure(server, user, password, vhost, timeout) #override config file if the user wants
        ampq_url = "amqp://%s:%s@%s/%s" % (self.user,self.password,self.server,self.vhost)
        self.url = os.environ.get('CLOUDAMQP_URL',ampq_url)
        
        self._connect()
        
        self._ioloop = threading.Thread(target=self.connection.ioloop.start, name='%s_ioloop' %self.queue, args=())
        self._ioloop.start()
                              
    def _connect(self):
        params = pika.URLParameters(self.url)
        params.socket_timeout = self.timeout
        self.connection = pika.SelectConnection(params,
                                     on_open_callback = self._onOpen,
                                     on_close_callback = self._onClose,
                                     stop_ioloop_on_close=False)
    
    def _onOpen(self, connection):
        self.connection.channel(on_open_callback=self._onChannelOpen) # start a channel

    def _onClose(self, connection, reply_code, reply_text):
        self.channel = None
        if self.closing:
            self.connection.ioloop.stop()
        else:
            self.logger.error('Channel closed, reopening')
            if not self.closing:
                # Create a new connection
                self._connect()
                # Since this gets called by the thread, we don't need to start another thread
                self.connection.ioloop.start()
    
    def _onChannelOpen(self, channel):
        self.channel = channel
        
        self.channel.add_on_close_callback(self._onChannelClose)
        
        self.channel.exchange_declare(self._onExchangeOk,
                                      self.exchange) # self.EXCHANGE_TYPE)

    def _onChannelClose(self, channel, reply_code, reply_text):
        # When a channel is closed it's because of bad usage, close the channel
        self.closing = True
        self.connection.close()

    def _onExchangeOk(self, unused_frame):
        self.channel.queue_declare(self._onQueueOk, self.queue, durable=True)
        
    def _onQueueOk(self, method_frame):
        self.channel.queue_bind(self._onBindOk, self.queue, self.exchange)

    def _onBindOk(self, unused_frame):
        self._ready = True
        
class RabbitSender(RabbitFrame):
    
    failure_sleep = 10
    max_retries = 3
    
    def __init__(self, logger, config, queue, reply_to=None):
        RabbitFrame.__init__(self, logger, config, queue)
        
        self.lock = threading.Lock()
        self.reply_to = reply_to
        
        while not self._ready:
            time.sleep(0.5)
    
    def Send(self, data=None, corr_id=None, reply_to_queue=None):
        if corr_id == None:
            corr_id = str(uuid.uuid4())
    
        message        = json.dumps(data)
        reply_to_queue = validate(reply_to_queue, self.reply_to)

        # Make this thread safe just in case
        retries = 0
        while True:
            # send a message
            try:
                with self.lock:
                    self.channel.basic_publish(exchange=self.exchange, 
                                               routing_key=self.queue, 
                                               body=message,
                                               properties=pika.BasicProperties(
                                                   delivery_mode = 2, # make message persistent
                                                   correlation_id = corr_id,
                                                   reply_to = reply_to_queue,
                                               ))
                self.logger.debug("Sender: produced message to queue %s with:\n\tcorrelation ID: %s\n\tbody: %s" %(self.queue, corr_id, message))                
                return corr_id
            except Exception:
                retries += 1
                # Never happened more than once
                if retries >= self.max_retries:
                    self.logger.exception("Error publishing to queue %s" %(self.queue))
                    return None
                time.sleep(self.failure_sleep)            

# This is what the callback function looks like
def printCallback(data, properties):
    print 'Receiver: %s' %data
    
class RabbitReceiver(RabbitFrame, threading.Thread):

    def __init__(self, logger, config, queue, callback, read_repeatedly=False):
        RabbitFrame.__init__(self, logger, config, queue)
        threading.Thread.__init__(self, name='RabbitReceiver %s' %queue)

        self.read_repeatedly = read_repeatedly
        self.callback = callback
        
        while not self._ready:
            time.sleep(0.5)

    def __wrapper(self, ch, method, properties, body):
        # Take care of parsing and acknowledging
        try:
            if (body is not None):
                data = json.loads(body)
                self.callback(data, properties)          
            
            ch.basic_ack(delivery_tag = method.delivery_tag)
        except Exception:
            self.logger.exception('Error in rabbitcoat receiver on queue %s, %s' %(self.queue, body))
        
    def run(self):
        ''' Bind a callback to the queue '''
        #TODO: This should be moved to a log eventually
        self.logger.debug("Receiver: starting to consume messeges on queue %s" %self.queue)

        self.channel.basic_consume(self.__wrapper,
                              self.queue,
                              no_ack=self.read_repeatedly)

# A basic print response for debugging
def printResponse(body):
    return "response: got %s" % str(body)
    
class SimpleRabbitResponder(RabbitReceiver):
    '''A simple responder that responds to one queue only
    '''
    def __init__(self, config, inbound_queue, response_function, out_queue, read_repeatedly=False):
        RabbitReceiver.__init__(self, config, queue, self.__responderCallback, read_repeatedly)
        
        self.sender = RabbitSender(self.config, out_queue)
            
        self.response_function = self.response_function

    def __responderCallback(self, data, properties):
        '''Respond to the relevant queue        
        This goes through __callback first, so it receives just json data and properties.
        '''
        response = self.response_function(data)
        
        self.sender.Send(data=response, corr_id=properties.correlation_id)

class VersatileRabbitResponder(RabbitReceiver):
    '''
    A class that supports multiple out queues, rather than one like SimpleRabbitResponder.
    '''

    def __init__(self, config, inbound_queue, response_function, default_out_queue=None, read_repeatedly=False):
        RabbitReceiver.__init__(self, config, queue, self.__callback, read_repeatedly)
        
        '''
        CR: This is a design I thought of... How about we make a constant sender for each queue we're using?
        Most of the gears will be using one outbound queue, and it would be inefficient to declare a sender each time
        Some gears (which work with many others, like the parser that parses many articles) work with many queues,
        So why not create a sender for each queue we encounter? Since we'll probably use it a lot, and there aren't too many queues
        
        Feel free to change this but I think it's better than the other option
        '''
        self.senders = {}
        # In case outbound queue isn't specified, reply_to MUST be specified in every message!
        if default_out_queue != None:
            sender = RabbitSender(self.config, default_out_queue)
            # Define a default sender, when reply_to is None
            self.senders[None] = sender
            self.senders[default_out_queue] = sender
            
        self.response_function = self.response_function

    def __callback(self, ch, method, properties, body):
        '''
        Respond to the relevant queue
        '''        
        response = self.response_function(body)
        reply_to = properies.reply_to
        
        if self.senders.has_key(reply_to):
            sender = self.senders[reply_to]
        # We have no idea where to send the response
        elif reply_to is None:
            #TODO: Logging
            print 'ERROR: no where to reply'
            ch.basic_ack(delivery_tag = method.delivery_tag)
            return
        else:
            sender = RabbitSender(self.config, reply_to)
            self.senders[reply_to] = sender
        
        ''' CR: The other option
        # Only declare a new sender if it's different from the constant one
        if (reply_to != None) and (reply_to != self.outbound_queue):
            sender = RabbitSender(self.config, properties.reply_to, inbound_queue)
        '''
        sender.Send(self, data=response, corr_id=properties.correlation_id)        
        
        ch.basic_ack(delivery_tag = method.delivery_tag)
    
class RabbitRequester(RabbitSender):

    def __init__(self, config, outbound_queue, callback, inbound_queue, read_repeatedly=False):
        RabbitSender.__init__(self, config, outbound_queue, inbound_queue)

    def ask(self,send_queue=None, reply_to_queue=None,message=None,callback=None,corr_id=str(uuid.uuid4())):
        self.Send(send_queue, message,corr_id,reply_to_queue)

        '''
        CR: Not changing this because I don't need it, but you send one message and the thread goes on forever, not a good idea
        '''
        receiver = RabbitReceiver(config, reply_to_queue, callback,False)
        receiver.run()
        

def main(argv):
    #rabbit = rabbitcoat()
    #rabbit.Receive()
    print "testers unimplemented *yet*- use cli.py"


if __name__ == "__main__":
    main(sys.argv[1:])
