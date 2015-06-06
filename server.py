import threading
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, send_file
from flask_wtf import Form
from wtforms import StringField, BooleanField, validators
from ConfigParser import SafeConfigParser
import os
from StringIO import StringIO

from json import dumps

from helper import *
#import pygres

def createErrorPage(data):
    #TODO: This?
    return 'This should create a normal error page<br>%s' %data
    
class SearchForm(Form):
    name = 'SearchForm'
    full_name = StringField('full_name')
    first_name = StringField('first_name')
    last_name = StringField('last_name')
    id = StringField('id')
    origin_country = StringField('origin_county')
    current_country = StringField('current_country')
    use_google = BooleanField(GOOGLE_KEY)
    use_factiva = BooleanField(FACTIVA_KEY)
    use_lexis = BooleanField(LEXIS_KEY)
    
ARTICLE_PAGE = 'ShowArticle'
class ManagerServer(threading.Thread):

    server_name = 'ManagerServer'
    default_secret = '\xfb\x13\xdf\xa1@i\xd6>V\xc0\xbf\x8fp\x16#Z\x0b\x81\xeb\x16'
    
    def __init__(self, manager, config='conf/manager.conf'):
        threading.Thread.__init__(self, name=self.server_name)
        self.manager = manager
        self.logger = manager.logger
        
        self.logger.info('Initializing ManagerServer')
        
        self.__loadConfig(config)
        
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY=self.secret_key)
        
        self.__route()
    
    def __loadConfig(self, config):
        # Don't need config for now, maybe later.
    
        self.secret_key = os.environ.get('SECRET_KEY',self.default_secret)
        self.host = os.environ.get('OPENSHIFT_PYTHON_IP', 'localhost')
        self.port = int(os.environ.get('OPENSHIFT_PYTHON_PORT', 8080))
    
    def __showArticle(self):
        try:
            id = int(request.args.get('id'))
        except Exception:
            # Bad parameters
            return '', 400
        
        self.logger.debug('Showing article %s' %id)
        try:
            res = self.manager.GetArticle(id)

            if res == None:
                return '', 404

            return res[DATA_KEY], 200
        except Exception, e:
            self.logger.exception('Exception in show article: %s' %e)
            return 'Server encountered error', 500
    
    def __searchResults(self):
        '''
        Get the results of a search. Later would be fed to a web application
        '''
        id = request.args.get('id')
        if not id:
            return '', 400
        
        res = self.manager.GetResults(search_id)
        return dumps(res), 200
    
    def __validateRequest(self, search_request, form):
        '''
        Update the request and return the error if any
        '''
        engines = (form.use_google.data, form.use_factiva.data, form.use_lexis.data)
        if not any(engines):
            return 'Atleast one search engine should be used.'
        
        search_request.update(dict(zip((GOOGLE_KEY, FACTIVA_KEY, LEXIS_KEY), engines)))
        
        data = { ID_PARAM: form.id.data,
                 ORIGIN_PARAM: form.origin_country.data,
                 COUNTRY_PARAM: form.current_country.data }
        
        first_name = form.first_name.data
        last_name = form.last_name.data
        full_name = form.full_name.data
        
        if first_name and last_name:
            full_name = '%s %s' %(first_name, last_name)
            data.update( { FIRST_NAME_PARAM: first_name,
                           LAST_NAME_PARAM: last_name,
                           NAME_PARAM: full_name} )
        elif full_name:
            # Lexis requires to know which is which
            if search_request[LEXIS_KEY]:
                return 'Lexis requires First & Last name to be used'
            data[NAME_PARAM] = full_name
        else:
            return 'First & Last name OR Full name should be supplied'
        
        search_request[DATA_KEY] = data
        #TODO: Add original name
    
        return None
    
    def __startSearch(self):
        search_request = {}
        form = SearchForm(request.form)
        
        error = self.__validateRequest(search_request, form)
        if error:
            print 'Error: %s' %error
            return dumps({ERROR_KEY: error}), 400
        
        #return 'Finished'
        search_id = self.manager.HandleRequest(search_request)
        return dumps({ID_KEY: search_id}), 200      
    
    def __showResults(self):
        id = request.args.get('id')
        show_complete = request.args.get('show_complete', False)
        if not id:
            return '', 400
        res = self.manager.GetResults(id, show_complete)
        if not res:
            return '', 404
        return dumps(res)
    
    def __index(self):
        return render_template('index.html')
    
    def __static(self, resource):
        print resource
        return send_from_directory('static/', resource)
    
    def __route(self):
        # Route the relevant pages to the functions
        self.app.add_url_rule('/article', None, self.__showArticle, methods={'GET'})
        self.app.add_url_rule('/search', None, self.__startSearch, methods={'POST'})
        self.app.add_url_rule('/results', None, self.__showResults, methods={'GET', 'POST'})
        self.app.add_url_rule('/', None, self.__index)
        self.app.add_url_rule('/<path:resource>', None, self.__static)        
        
    def run(self):
        self.app.run(host=self.host, port=self.port)
        
def main():

    server = ManagerServer(getLogger('searchServer'), None)
    server.run()

if __name__ == '__main__':
    main()
