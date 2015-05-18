
from ConfigParser import SafeConfigParser
import logging
import uuid
from threading import Lock

import server
from helper import *
import rabbitcoat
import pygres

# Turn down requests and pika logging
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("pika").setLevel(logging.WARNING)

class SearchHandler(object):
    
    def __init__(self, search_id, query, google_id=None, factiva_id=None, lexis_id=None):
        '''
        Handle search resultss
        '''
        self.query = query
        
        self.lock = Lock()
        
        self.google_id = google_id
        self.factiva_id = factiva_id
        self.lexis_id = lexis_id
        
        self.google_results = None
        self.factiva_results = None
        self.lexis_results = None
        
        self.google_done = (google_id == None)
        self.factiva_done = (factiva_id == None)
        self.lexis_done = (lexis_id == None)        
        
    def SendResults(self, data, corr_id):
        # Send the results to the handler. Return true if the search is finished.
        with self.lock: # To avoid sending the results twice
            if corr_id == google_id:
                self.google_results = data
            elif corr_id == factiva_id:
                self.factiva_results = data
            elif corr_id == lexis_id:
                self.lexis_results = data
                
            if self.google_done and self.factiva_done and self.lexis_done:
                return True
            
        return False           
            
    def GetResults(self):
        results = {}
        if self.google_results != None:
            results[GOOGLE_KEY] = self.google_results
        if self.factiva_results != None:
            results[FACTIVA_KEY] = self.factiva_results
        if self.lexis_results != None:
            results[LEXIS_KEY] = self.lexis_results
        return results
            
class SearchManager(object):
    '''
    A manager for searching data on people.
    Later this will serve clients through a web application.
    '''
    
    def __init__(self, config='conf/manager.conf', rabbit_config='conf/rabbitcoat.conf', pygres_config='conf/pygres.conf'):
        self.logger = getLogger('manager')
        
        # A dictionary of correlation ids and their handlers
        self.queues = {}
        self.handlers = {}
        
        #self.db_manager = None
        self.db_manager = pygres.PostgresManager(pygres_config)
        self.server = server.ManagerServer(self, config)
    
        self.__loadConfig(config)
        
        self.google_sender = rabbitcoat.RabbitSender(rabbit_config, self.google_queue)
        self.factiva_sender = rabbitcoat.RabbitSender(rabbit_config, self.factiva_queue)
        self.lexis_sender = rabbitcoat.RabbitSender(rabbit_config, self.lexis_queue)
        
        self.receiver = rabbitcoat.RabbitReceiver(rabbit_config, self.out_queue, self.__rabbitCallback)
        
        self.receiver.start()
        self.server.start()
        
    def __loadConfig(self, config):
        parser = SafeConfigParser()
        parser.read(config)
        
        # The queue to which the output of the search would be delivered
        self.out_queue = parser.get('MANAGER', 'out_queue')
        
        self.google_queue = parser.get('MANAGER', 'google_queue')
        self.factiva_queue = parser.get('MANAGER', 'factiva_queue')
        self.lexis_queue = parser.get('MANAGER', 'lexis_queue')            
    
    def HandleRequest(self, search_request):
        '''
        Handle a dictionary representing a search request. 
            
        Data should contain the values listed in helper.py, full name is automatic 
        '''
        print 'Handling request: %s' %search_request
        data = search_request[DATA_KEY]
        
        google_id = None
        factiva_id = None
        lexis_id = None
        if search_request[GOOGLE_KEY]:
            google_id = self.google_sender.Send(data)
        if search_request[FACTIVA_KEY]:
            factiva_id = self.factiva_sender.Send(data)
        if search_request[LEXIS_KEY]:
            lexis_id = self.lexis_sender.Send(data)
        
        print 'ids: %s, %s, %s' %(google_id, factiva_id, lexis_id)
        search_id = str(uuid.uuid4())
        
        handler = SearchHandler(search_id, data, google_id, factiva_id, lexis_id)
        self.handlers[search_id] = handler
        # None key won't matter
        self.queues[google_id] = handler
        self.queues[factiva_id] = handler
        self.queues[lexis_id] = handler
        
        return search_id
    
    def GetArticle(self, id):
        return self.db_manager.GetArticle(id)
    
    def __saveResults(self, handler):
        results = hander.GetResults()
        self.db_manager.SaveResults(handler.search_id, handler.query, handler.results)
    
    def __rabbitCallback(self, data, properties):
        corr_id = properties.correlation_id
        # Unknown search result, ignore it
        if not self.queues.has_key(corr_id):
            return
            
        handler = self.queues.pop(corr_id)
        if handler.SendResults(data, corr_id):
            # Save the results to the db
            self.__saveResults(handler)
            # No longer needed
            self.handlers.pop(handler.search_id)            
        
    def GetResults(self, search_id):
        '''
        Get the results of a search. Later would be fed to a web application
        '''
        if self.handlers.has_key(search_id):
            return 'Search in progress'
        
        return self.db_manager.GetSearch(search_id)
            
def main():
    manager = SearchManager()
        
if __name__ == '__main__':
    main()