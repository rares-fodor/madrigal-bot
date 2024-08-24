import sqlite3
import logging

logger = logging.getLogger('db_manager')

class DatabaseManager:
    def __init__(self, db_path: str) -> None:
        self.filename = db_path 
        self.connection = None
        self.cursor = None
    
    def connect(self):
        try:
            self.connection = sqlite3.connect(self.filename)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            logger.info(f"Connected to db {self.filename}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to db: {e}")
            raise
    
    def executescript(self, path: str):
        if not self.connection:
            self.connect()

        try:
            with open(path, 'r') as fp:
                self.cursor.executescript(fp.read())
                logger.info(f"Executed script at {path}")
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            raise
    
    def close(self):
        if self.connection:
            self.connection.close()
            logger.info(f"Closed connection to db {self.filename}")
