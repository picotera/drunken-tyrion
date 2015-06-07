import psycopg2
import os
from threading import Lock
import time

from helper import *

from ConfigParser import SafeConfigParser

ARTICLES_TABLE = 'Articles'
SEARCHES_TABLE = 'Searches'

DEFAULT_CONF = 'conf/pygres.conf'

ENCODING = 'encoding'

CONFIG_SECTION = 'POSTGRESQL'

EXCEPTION_SLEEP = 60
def handle_excepts(inner_f):
    def _inner_f(self, *args, **kwargs):
        try:
            while True:
                try:
                    return inner_f(self, *args, **kwargs)
                except psycopg2.OperationalError:
                    self.logger.exception('Caught OperationError, sleeping and reconnecting')
                    time.sleep(EXCEPTION_SLEEP)
                    self._connect()
        except Exception:
            self.logger.exception("Exception on db action: %s" %(args,))
            return None
            
    return _inner_f

class PostgresConnection(object):
    '''
    A generic class of connections, in case we'll have more inheritants
    '''
    def __init__(self, logger, config=DEFAULT_CONF, setup=False):
        self.logger = logger
    
        self.__loadConfig(config)
        self._connect()
        self.lock = Lock()
    
        # This will drop the existing table!
        if setup:
            self.__setup()        

    def __loadConfig(self, config):
    
        parser = SafeConfigParser()
        parser.read(config)
        
        env = parser.getboolean(CONFIG_SECTION,'env_variables')
        # If these are environment variables, which is the case in openshift
        if env:
            self.host = os.environ[parser.get(CONFIG_SECTION,'host')]
            self.port = os.environ[parser.get(CONFIG_SECTION,'port')]
        else:
            self.host = parser.get(CONFIG_SECTION,'host')
            self.port = parser.getint(CONFIG_SECTION,'port')
            
        self.database = parser.get(CONFIG_SECTION,'database')
        self.user = parser.get(CONFIG_SECTION,'user')
        self.password = parser.get(CONFIG_SECTION,'password')
        
    def __setup(self):
        '''
        Important stuff to do before we start working
        
        WARNING: All connections to the DB must be closed first.
        '''
        self.cur.execute('DROP TABLE IF EXISTS %s' %ARTICLES_TABLE)
        self.cur.execute('CREATE TABLE %s(id serial, source varchar(8), data bytea)' %ARTICLES_TABLE)

        # A table to save searches
        #TODO: Add indexing to search ID?
        self.cur.execute('DROP TABLE IF EXISTS %s' %SEARCHES_TABLE)
        self.cur.execute('CREATE TABLE %s(id serial, search_id char(36), query text, results text)' %SEARCHES_TABLE)
        
        self.con.commit()
    
    def _connect(self):
        '''
        Connect to the database
        '''
        self.con = psycopg2.connect(host=self.host, port=self.port, database=self.database, user=self.user, password=self.password)
        self.cur = self.con.cursor()
    
    @handle_excepts
    def _getByValue(self, table, value_name, value, keys=None):
        query = 'SELECT * from %s WHERE %s=' %(table, value_name)
        query += '%s'
    
        with self.lock:
            self.cur.execute(query, (value,))
            res = self.cur.fetchone()
            
        if keys != None and res != None:
            # Create a dict
            d = {}
            for i in xrange(len(keys)):
                if keys[i] != None:
                    d[keys[i]] = res[i]
            res = d
            
        return res
    
    def _getById(self, table, id, keys=None):
        return self._getByValue(table, 'id', id, keys=keys)
        
class PostgresArticles(PostgresConnection):
    '''
    A class for handling articles
    '''
    def __init__(self, logger, config=DEFAULT_CONF, setup=False):
        PostgresConnection.__init__(self, logger, config, setup)
        # Do stuff?
    
    @handle_excepts
    def AddArticle(self, data, source):
        query = 'INSERT INTO %s' %ARTICLES_TABLE
        query += ' (source,data) VALUES(%s,%s) RETURNING id'
        with self.lock:
            self.cur.execute(query, (source, psycopg2.Binary(data)))
            id = self.cur.fetchone()[0]
            self.con.commit()
        
        return id
    
    def GetArticle(self, id):
        data = self._getById(ARTICLES_TABLE, id, keys=(ID_KEY, SOURCE_KEY, DATA_KEY))
        if not data:
            return None
        fixed_data = data.get(DATA_KEY)
        if not fixed_data:
            self.logger.exception("No data key in article %s'" %(data,))
        
        data[DATA_KEY] = str(fixed_data)
        return data     
        
class PostgresManager(PostgresArticles):
    '''
    A class to be used by the manager, to handle searches on top of articles
    '''
    def __init_(self, logger, config=DEFAULT_CONF, setup=False):
        PostgresArticles.__init__(self, logger, config, setup)
        
    @handle_excepts
    def SaveSearch(self, search_id, search_query, results):
        query = 'INSERT INTO %s' %SEARCHES_TABLE
        query += ' (search_id, query, results) VALUES(%s,%s,%s) RETURNING id'
        with self.lock:
            self.cur.execute(query, (search_id, search_query, results))
            id = self.cur.fetchone()[0]
            self.con.commit()
        
        return id
        
    def GetSearch(self, search_id):
        return self._getByValue(SEARCHES_TABLE, 'search_id', search_id, keys=(None, ID_KEY, QUERY_KEY, RESULTS_KEY))
        
def main():
    postgres = PostgresManager(getLogger('pygres'), setup=True)
    id = postgres.AddArticle("1) As you enter through the Shaded Woods door (after <producing the symbol of the King by wearing the King's Ring) on left is a corpse with Soul of a Nameless Soldier and Petrified Dragon Bone. To the right behind stairs in corner, is a corpse with Fire Seed. Another corpse near the tall grass has Poison Throwing Knife x10. There is a roaming pack of dogs in the tall grass that inflict bleed and petrification. In the grass is a corpse in with Alluring Skull x3. If you follow the ridge to the left you come across a mimic chest. Attack it and kill it to get Sunset Staff and Dark Mask. In a little wooden hut nearby is a the Foregarden bonfire. You may meet Lucatiel of Mirrah here, and if you kept her alive during three earlier boss fights, she will give you her sword and armor (Mirrah Greatsword, Lucatiel's Set).", 1)

    print 'id %s' %id
    data = postgres.GetArticle(id)
    print data
    '''
    id = postgres.SaveSearch("bca8b265-65f3-4bc2-83ce-0f3e01a9dc4d", "QUERY QUERY", "RESULT RESULT")
    print postgres.GetSearch("bca8b265-65f3-4bc2-83ce-0f3e01a9dc4d")
    '''
    

if __name__ == "__main__":
    main()