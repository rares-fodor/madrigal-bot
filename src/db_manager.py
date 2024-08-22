import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

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
            logging.info(f"Connected to db {self.filename}")
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to db: {e}")
            raise
    
    def executescript(self, path: str):
        if not self.connection:
            self.connect()

        try:
            with open(path, 'r') as fp:
                self.cursor.executescript(fp.read())
                logging.info(f"Executed script at {path}")
        except Exception as e:
            logging.error(f"Failed to execute script: {e}")
            raise
    
    def close(self):
        if self.connection:
            self.connection.close()
            logging.info(f"Closed connection to db {self.filename}")
    

