import os
import sys
from config import LOG_LEVEL
from loguru import logger

LOG_FORMAT = "{time:DD/MM/YYYY HH:mm:ss.SSS} │ <level>{level: <8}</> ├→ <level>{message}</>"
LOG_PREFIX = 'logger.py'

logger.remove()

if sys.stdout:
    logger.add(sys.stdout, level=LOG_LEVEL, format=LOG_FORMAT, colorize=True)

if sys.platform == "win32":
    appdata_directory = os.getenv('APPDATA')
    if not appdata_directory:
        logger.error(f'{LOG_PREFIX:<20} Could not determine appdata directory')
        logger.debug(f'{LOG_PREFIX:<20} appdata_directory: {appdata_directory}')
        sys.exit(1)
        
    LOG_PATH = os.path.join(appdata_directory, "Watcher")
else:
    home_directory = os.path.expanduser("~")
    LOG_PATH = os.path.join(home_directory, ".Watcher")

os.makedirs(LOG_PATH, exist_ok=True)

LOG_FILE = f'{LOG_PATH}/watcher.log'

logger.add(LOG_FILE, level=LOG_LEVEL, format=LOG_FORMAT, rotation="10 MB", retention="7 days")
logger.debug(f'{LOG_PREFIX:<20} log_file: {LOG_FILE}')