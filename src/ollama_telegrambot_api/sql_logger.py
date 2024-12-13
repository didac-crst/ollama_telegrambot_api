from dataclasses import dataclass
from time import time
import sqlite3
import os

@dataclass
class SQLiteLogger:
    logger_name: str
    directory_path: str = "./"
    
    def __post_init__(self):
        """
        Initialize the SQLiteLogger with the database and table name.
        
        :param db_name: Name of the SQLite database file (e.g., "log.db").
        :param table_name: Name of the table for logging.
        """
        extension = ".db"
        self.logger_file = f"{self.logger_name}{extension}"
        self.file_path = os.path.join(self.directory_path, self.logger_file)
        if not os.path.exists(self.file_path):
            open(self.file_path, 'w').close()
        self.connect()
        self._create_user_table()
        self._create_log_table()
        self.close()
    
    def connect(self):
        """
        Connect to the database.
        """
        self.conn = sqlite3.connect(self.file_path)
        self.cursor = self.conn.cursor()
    
    def _create_user_table(self):
        """
        
        Create a table for logging users if it doesn't exist.
        """
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT
            )
        """)
        self.conn.commit()
    
    def _create_log_table(self):
        """
        Create a table for logging messages if it doesn't exist.
        
        """
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS Logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                execution_time REAL NOT NULL,
                error BOOLEAN NOT NULL
            )
        """)
        self.conn.commit()
    
    def record_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """
        Record a user into the database.
        
        :param user_id: User ID.
        :param username: Username.
        :param first_name: First name.
        :param last_name: Last name.
        """
        self.cursor.execute(f"""
            INSERT INTO Users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def find_user(self, user_id: int):
        """
        Find a user in the database.
        
        :param user_id: User ID.
        :return: User information.
        """
        self.cursor.execute(f"""
            SELECT * FROM Users
            WHERE user_id = ?
        """, (user_id,))
        return self.cursor.fetchone()
    
    def record_log(self, user_id: int, question: str, answer: str, execution_time: float, timestamp: int, error: bool):
        """
        Record a log into the database.
        
        :param user_id: User ID.
        :param question: The question asked.
        :param answer: The answer to the question.
        :param execution_time: Time taken to answer the question.
        :param timestamp: Timestamp of the log.
        :param error: Whether an error occurred.
        """
        self.cursor.execute(f"""
            INSERT INTO Logs (user_id, timestamp, question, answer, execution_time, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, timestamp, question, answer, execution_time, error))
        self.conn.commit()
    
    def __call__(self, answer_dict: dict[str, any]) -> None:
        """
        Log a message into the database.
        
        """
        user_id = answer_dict['user_id']
        username = answer_dict['username']
        first_name = answer_dict['first_name']
        last_name = answer_dict['last_name']
        question = answer_dict['question']
        answer = answer_dict['answer']
        execution_time = answer_dict['execution_time']
        timestamp = int(time())
        error = answer_dict['error']
        # Check if user is already in the database. If not, record the user.
        self.connect()
        if not self.find_user(user_id):
            self.record_user(user_id, username, first_name, last_name)
        # Record the log
        self.record_log(user_id, question, answer, execution_time, timestamp, error)
        if error:
            print(f"Error: [{username}] {question[:30]}... -> {answer}")
        else:
            print(f"Logged: [{username}] {question[:30]}... -> {answer[:30]}...")
        self.close()
        
    def close(self):
        """Close the database connection."""
        self.conn.close()
