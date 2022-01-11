import logging
import sqlite3
import hashlib


class UserMngr:
    def __init__(self, config):
        """
        Sets up obj, creates a database connection.
        """
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])

        # set up database connection to manage projects
        self.connection = sqlite3.connect("users.db")
        self.cursor = self.connection.cursor()
        # Create table if not exists
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS `kack_users` (
                            `id` INTEGER PRIMARY KEY,
                            `username` TEXT NOT NULL,
                            `passwd` TEXT NOT NULL,
                            `mail` TEXT NOT NULL,
                            `im_handle` TEXT
                            );""")
        self.connection.commit()

        self.hashgen = hashlib.sha256

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit hook, closes DB connection if object is destroyed

        Parameters
        ----------
        exc_type
        exc_val
        exc_tb
        """
        self.connection.close()

    def __enter__(self):
        """
        Required for "with" instantiation to work correctly
        """
        return self

    def add_user(self, user, cryptpwd, cryptmail):
        self.logger.info(f"Trying to create user {user}.")
        # Check if user already exists
        if not self.cursor.execute(f"SELECT username FROM kack_users WHERE username = '{user}';").fetchall():
            self.logger.info(f"User {user} does not yet exist. Creating.")
            self.cursor.execute(f"INSERT INTO kack_users(username, passwd, mail) VALUES "
                                f"('{user}', '{cryptpwd}', "
                                f"'{self.hashgen(mail.encode()).hexdigest()}');")
            self.connection.commit()
            return True
        else:
            self.logger.error(f"User {user} already exists! Aborting user creation!")
            return False

    def login(self, user: str, cryptpwd: str):
        """
        Checks if the user can be logged in or not

        Parameters
        ----------
        user : str
            username of user to log in
        pwd : str
            password of the user (unhashed, only exists here temporarily)

        Returns
        -------
        bool
            True if user can be logged in, False if something is wrong
        """
        dbdata = self.cursor.execute(f"SELECT username, passwd FROM kack_users WHERE username = '{user}';").fetchall()
        if len(dbdata) == 0:
            return False
        elif len(dbdata) > 1:
            self.logger.critical(f"Username {user} is multiple times in the database! How even?")
            return False
        else:
            # user exists and pwd was loaded from db. check pwd.
            if cryptpwd == dbdata[0][1]:
                return True
            else:
                return False
