import logging
import logging.handlers
import sys
import os

GENERIC_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'}

MAX_LOG_SIZE = 5 * 1024 * 1024 # 5MB
BACKUP_COUNT = 5

# Main queue keys
RESULTS_KEY = 'results'
ERROR_KEY = 'error'
QUERY_KEY = 'query' # Used for ranking and as results key
REASON_KEY = 'reason'

# Manager specific
DATA_KEY = 'data'
GOOGLE_KEY = 'google'
FACTIVA_KEY = 'factiva'
LEXIS_KEY = 'lexis'

# Main result keys
ID_KEY = 'id'
SOURCE_KEY = 'source'
TITLE_KEY = 'title'
URL_KEY = 'url'
SCORE_KEY = 'score'

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

class SearchEngines(object):
    '''
    Stored in postgres to determine which source the article came from
    '''
    GOOGLE = 'google'
    FACTIVA = 'factiva'
    LEXIS = 'lexis'

def getLogger(name, level=logging.INFO, file_level = logging.DEBUG, max_size = MAX_LOG_SIZE, backup_count = BACKUP_COUNT):
    log_dir = os.environ.get('OPENSHIFT_LOG_DIR', '')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    file_handler = logging.handlers.RotatingFileHandler('%s%s.log' %(log_dir, name), mode='a', maxBytes=max_size, backupCount=backup_count, encoding=None, delay=0)
    file_handler.setLevel(file_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
            