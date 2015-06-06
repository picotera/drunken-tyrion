
from ConfigParser import SafeConfigParser
import logging
import uuid
from threading import Lock
from StringIO import StringIO

import server
from helper import *
import rabbitcoat
import pygres
import json

# Turn down requests and pika logging
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("pika").setLevel(logging.WARNING)

STATUS_KEY = 'status'

class SearchHandler(object):
    
    def __init__(self, search_id, query, google_id=None, factiva_id=None, lexis_id=None):
        '''
        Handle search resultss
        '''
        self.query = query
        
        self.lock = Lock()
        
        self.search_id = search_id
        self.google_id = google_id
        self.factiva_id = factiva_id
        self.lexis_id = lexis_id
        
        self.google_results = None
        self.factiva_results = None
        self.lexis_results = None

        self.google_status = SearchStatus.COMPLETE if google_id == None else SearchStatus.PENDING
        self.factiva_status = SearchStatus.COMPLETE if factiva_id == None else SearchStatus.PENDING
        self.lexis_status = SearchStatus.COMPLETE if lexis_id == None else SearchStatus.PENDING
        
        self.complete = False
    
    def __allComplete(self):
        self.complete = searchComplete(self.google_status) and\
               searchComplete(self.factiva_status) and\
               searchComplete(self.lexis_status)
        return self.complete
    
    def SendResults(self, data, corr_id):
        # Send the results to the handler. Return true if the search is finished.
        
        reason = data.get(ERROR_KEY)
        if reason:
            status = SearchStatus.ERROR
        else:
            status = SearchStatus.COMPLETE
        with self.lock: # To avoid sending the results twice
            if corr_id == self.google_id:
                self.google_results = data
                self.google_status = status
            elif corr_id == self.factiva_id:
                self.factiva_results = data
                self.factiva_status = status
            elif corr_id == self.lexis_id:
                self.lexis_results = data
                self.lexis_status = status
                
            return self.__allComplete()
    
    def __getResult(self, all_results, key, search_results, get_complete=False):
        ''' Update the all_results dictionary with results of a specific engine '''
        print 'Search results: %s' %search_results
        
        if search_results != None:
            if get_complete:
                error = search_results.get(ERROR_KEY)
                if error:
                    all_results[key] = {STATUS_KEY: SearchStatus.ERROR, REASON_KEY: error}
                else:
                    all_results[key] = {STATUS_KEY: SearchStatus.COMPLETE, RESULTS_KEY: search_results[RESULTS_KEY]}
            else:
                all_results[key] = {STATUS_KEY: SearchStatus.COMPLETE}
        else:
            all_results[key] = {STATUS_KEY: SearchStatus.PENDING}
    
    def GetResults(self, show_complete = False):
        results = {}
        
        # Show complete results if required, or if search finished
        show_complete = show_complete or self.complete
        
        if self.complete:
            results[STATUS_KEY] = SearchStatus.COMPLETE
        else:
            results[STATUS_KEY] = SearchStatus.PENDING
        
        # Update the results dictionary
        if self.google_id:
            self.__getResult(results, GOOGLE_KEY, self.google_results, show_complete)
        if self.factiva_id:
            self.__getResult(results, FACTIVA_KEY, self.factiva_results, show_complete)
        if self.lexis_id:
            self.__getResult(results, LEXIS_KEY, self.lexis_results, show_complete)
        
        return results
            
STATUS_KEY = 'status'

searchComplete = lambda x: x==True or x == SearchStatus.COMPLETE or x == SearchStatus.ERROR
class SearchStatus(object):
    COMPLETE = 'complete'
    PENDING = 'pending'
    ERROR = 'error'

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
        self.db_manager = pygres.PostgresManager(self.logger, pygres_config)
        self.server = server.ManagerServer(self, config)
    
        self.__loadConfig(config)
        
        self.google_sender = rabbitcoat.RabbitSender(self.logger, rabbit_config, self.google_queue)
        self.factiva_sender = rabbitcoat.RabbitSender(self.logger, rabbit_config, self.factiva_queue)
        self.lexis_sender = rabbitcoat.RabbitSender(self.logger, rabbit_config, self.lexis_queue)
        
        self.receiver = rabbitcoat.RabbitReceiver(self.logger, rabbit_config, self.out_queue, self.__rabbitCallback)
        
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
        self.logger.info('Handling search request: %s' %search_request)
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
        #data = 'No db'
        data = self.db_manager.GetArticle(id)
        return data
    
    def __saveResults(self, handler):
        results = json.dumps(handler.GetResults())
        query = json.dumps(handler.query)
        self.logger.debug('Before saving: %s, %s, %s, %s, %s, %s' %(results, type(results), query, type(query), handler.search_id, type(handler.search_id)))
        self.logger.debug('Saving results to db %s' %results)
        self.db_manager.SaveSearch(handler.search_id, query, results)        
    
    def __rabbitCallback(self, data, properties):
        self.logger.debug('Rabbit callback with data: %s, %s' %(data, properties))
        try:
            corr_id = properties.correlation_id
            # Unknown search result, ignore it
            if not self.queues.has_key(corr_id):
                self.logger.debug("Untracked correlation ID, ignoring %s" %corr_id)
                return
                
            handler = self.queues.pop(corr_id)
            self.logger.debug("Sending results to search %s" %handler.search_id)
            if handler.SendResults(data, corr_id):                
                # Save the results to the db
                self.logger.debug("Finished search %s" %handler.search_id)
                self.__saveResults(handler)
                
                self.handlers.pop(handler.search_id)
                    
        except Exception:
            self.logger.exception('Exception in rabbit callback')
        
    def GetResults(self, search_id, show_complete=False):
        '''
        Get the results of a search. Later would be fed to a web application
        '''
        # This happens if the search is in progress
        handler = self.handlers.get(search_id)
        if handler:
            return handler.GetResults(show_complete)
        
        res = self.db_manager.GetSearch(search_id)
        if not res:
            return None
        results = json.loads(res[RESULTS_KEY])
        
        return results
            
def main():
    manager = SearchManager()
        
if __name__ == '__main__':
    main()