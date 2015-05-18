import threading
from flask import Flask, request, render_template, send_from_directory, redirect, url_for
from flask_wtf import Form
from wtforms import StringField, BooleanField, validators
from ConfigParser import SafeConfigParser
import os

import json

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
    id = StringField('id', validators=[validators.Required(), validators.Length(2,20)])
    origin_country = StringField('origin_county', validators=[validators.Required(), validators.Length(2,15)])
    current_country = StringField('current_country', validators=[validators.Required(), validators.Length(2,15)])
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
    
    def __showArticle(self, id):
        self.logger.debug('Showing article %s' %id)
        try:
            try:
                id = int(id)
            except Exception:
                print 'Error'
                return createErrorPage('Invalid article ID supplied: %s' %id)

            res = self.manager.GetArticle(id)

            if res == None:
                return createErrorPage('Article not found: %s' %id)
               
            return res[DATA_KEY]
        except Exception, e:
            self.logger.exception('Exception in show article: %s' %e)
            return createErrorPage("Internal server error")
    
    def __searchResults(self, search_id):
        '''
        Get the results of a search. Later would be fed to a web application
        '''
        return json.dumps(self.manager.GetResults(search_id), indent=4)
    
    def __updateRequest(self, search_request, form):
        '''
        Update the request and return the error if any
        '''
        search_request.update({ GOOGLE_KEY: form.use_google.data,
                                FACTIVA_KEY: form.use_factiva.data,
                                LEXIS_KEY: form.use_lexis.data, })
        
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
    
    def __searchForm(self):        
        form = SearchForm()
        error = None
        
        # Perform basic validation, 
        if request.method == 'POST' and form.validate():
            search_request = {}
            form = SearchForm(request.form)
            
            error = self.__updateRequest(search_request, form)
            if not error:
                search_id = self.manager.HandleRequest(search_request)
                return redirect('/Results/%s' %search_id)

        # Return the form to the user       
        return render_template('search.html', form=form, error=error)            
    
    def __showResults(self, id):
        return self.manager.GetResults(id)
    
    def __index(self):
        return render_template('index.html')
    
    def __static(self, resource):
        return send_from_directory('static/', resource)
    
    def __route(self):
        # Route the relevant pages to the functions
        self.app.add_url_rule('/Article/<id>', None, self.__showArticle, methods={'GET'})
        self.app.add_url_rule('/Results/<id>', None, self.__showResults, methods={'GET', 'POST'})
        self.app.add_url_rule('/SearchForm', None, self.__searchForm, methods={'GET', 'POST'})
        self.app.add_url_rule('/', None, self.__index)
        self.app.add_url_rule('/<path:resource>', None, self.__static)        
        
    def run(self):
        self.app.run(host=self.host, port=self.port)
        
def main():

    server = ManagerServer(getLogger('searchServer'), None)
    server.run()

if __name__ == '__main__':
    main()
