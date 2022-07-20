import logging
import pathlib
import sqlite3
from typing import Dict

from flask_login import UserMixin

import kacky_schedule.usermanagement.user_session_handler


class User(UserMixin):
    """
    This class satisfies the user object required for using flask_login. Handling user data and reading/updating
    the database mostly is handles in usermanagement.user_operations.UserDataMngr.
    """
    def __init__(self, username: str, config: Dict):
        """
        Sets up obj, creates a database connection.
        """
        self.username = username
        self.logger = logging.getLogger(config["logger_name"])
        # set up database connection to manage projects
        self.connection = sqlite3.connect(pathlib.Path(__file__).parents[3] / "stuff.db")
        self.cursor = self.connection.cursor()

    def is_authenticated(self) -> bool:
        """
        Returns if user is authenticated. Required by flask_login.UserMixin.

        Returns
        -------
        bool
        """
        return True

    def is_active(self) -> bool:
        """
        Returns if User account is active. Not used in project. Required by flask_login.UserMixin.

        Returns
        -------
        bool
        """
        return True

    def is_anonymous(self) -> bool:
        """
        Returns if user is anonymous. Not used in project. Required by flask_login.UserMixin.

        Returns
        -------
        bool
        """
        return False

    def get_id(self):# -> usermanagement.user_session_handler.User:
        """
        Provides a User/UserMixin for each user. UID will be username, as in DB. Required by flask_login.UserMixin.
        Returns
        -------

        """
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

    def login(self, user: str, cryptpwd: str) -> bool:
        """
        Checks if the user can be logged in or not.

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
