import logging
import logging.config

from os import getenv
from dotenv import load_dotenv
from yaml import safe_load

from src.scanner import FileScanner
from src.bot import client

load_dotenv()

def setup_logging(config_path: str):
    try:
        with open(config_path, 'r') as fp:
            config = safe_load(fp)
            logging.config.dictConfig(config)
    except OSError:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s.%(msecs)03d:%(name)s:%(levelname)s:%(message)s',
            datefmt='%Y-%m-%d,%H:%M:%S'
        )
        logging.info("Logging config couldn't be read, defaulting to basicConfig")


def main():
    setup_logging('logging.conf.yaml')
    scanner = FileScanner(library_path=getenv('LIBRARY_PATH'), db_path="db/tracks.sqlite")
    scanner.scan()
    client.run(token=getenv("TOKEN"), log_handler=None)
    
if __name__ == '__main__':
    main()