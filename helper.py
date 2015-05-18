import logging
import logging.handlers
import sys
from ConfigParser import SafeConfigParser

MAX_LOG_SIZE = 10 * 1024 * 1024 # 50MB
BACKUP_COUNT = 5

# Main queue keys
RESULTS_KEY = 'results'
WEIGHT_KEY = 'weight'

# Manager specific
DATA_KEY = 'data'
GOOGLE_KEY = 'google'
FACTIVA_KEY = 'factiva'
LEXIS_KEY = 'lexis'

# Main result keys
ID_KEY = 'id'
SOURCE_KEY = 'source'
QUERY_KEY = 'query'
TITLE_KEY = 'title'
URL_KEY = 'url'

# Google specific
MATCHES_KEY = 'matches'

# Parameters from the manager
NAME_PARAM = 'name' # Full name, automatic in the manager
FIRST_NAME_PARAM = 'first_name' # First name 
LAST_NAME_PARAM = 'last_name' # Last name
ORIGIN_NAME_PARAM = 'source_name' # Full name in original language, automatic in manager
ORIGIN_FIRST_PARAM = 'source_first' # First name in original language
ORIGIN_LAST_PARAM = 'source_last' # Last name in original language
ID_PARAM = 'id' # List of identifiers (Personal ID, company identifier)
ORIGIN_PARAM = 'origin' # Country of origin
COUNTRY_PARAM = 'country' # The country where the trade is executed

SOURCE_KEY = 'source'

class ArticleSources(object):
    '''
    Stored in postgres to determine which source the article came from
    '''
    GOOGLE = 0
    FACTIVA = 1
    LEXIS = 2

def getLogger(name, level=logging.INFO, file_level = logging.DEBUG, max_size = MAX_LOG_SIZE, backup_count = BACKUP_COUNT):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    file_handler = logging.handlers.RotatingFileHandler('%s.log' %name, mode='a', maxBytes=max_size, backupCount=backup_count, encoding=None, delay=0)
    file_handler.setLevel(file_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
            