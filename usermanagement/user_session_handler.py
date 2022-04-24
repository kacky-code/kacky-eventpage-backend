import logging
import pathlib
import sqlite3

from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, username, config):
        """
        Sets up obj, creates a database connection.
        """
        self.username = username
        self.logger = logging.getLogger(config["logger_name"])
        # set up database connection to manage projects
        self.connection = sqlite3.connect(pathlib.Path(__file__).parents[1] / "stuff.db")
        # self.connection = sqlite3.connect("/var/www/flask/kim_kk_dev_site/stuff.db")
        self.cursor = self.connection.cursor()

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        db_username_query = "SELECT username FROM kack_users WHERE username = ?"

        db_username_data = self.cursor.execute(db_username_query, (self.username,)).fetchall()
        if len(db_username_data) == 0:
            return None
        elif len(db_username_data) > 1:
            self.logger.critical(f"Username {self.username} is multiple times in the database! How even?")
            return None
        else:
            # return user id
            if db_username_data[0][0]:
                return db_username_data[0][0]
            else:
                return None

    def login(self, user: str, cryptpwd: str):
        """
        Checks if the user can be logged in or not

        Parameters
        ----------
        user : str
            username of user to log in
        cryptpwd : str
            password of the user

        Returns
        -------
        bool
            True if user can be logged in, False if something is wrong
        """
        query = "SELECT username, passwd FROM kack_users WHERE username = ?"
        dbdata = self.cursor.execute(query, (user, )).fetchall()
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
