import logging
from typing import Dict

import mariadb


class User:
    """
    This class satisfies the user object required for using flask_login. Handling user
    data and reading/updating the database mostly is handles in
    usermanagement.user_operations.UserDataMngr.
    """

    def __init__(self, username: str, config: Dict, secrets):
        """
        Sets up obj, creates a database connection.
        """
        self.username = username
        self.logger = logging.getLogger(config["logger_name"])
        # set up database connection to manage projects
        try:
            self.connection = mariadb.connect(
                host=config["dbhost"],
                port=config["dbport"],
                user=secrets["dbuser"],
                passwd=secrets["dbpwd"],
                database=config["dbname"],
            )
        except mariadb.Error as e:
            self.logger.error(f"Connecting to database failed! {e}")
            raise e
        self.cursor = self.connection.cursor()

    def exists(self):
        query = "SELECT id FROM kack_users WHERE username = ?;"
        self.cursor.execute(query, (self.username,))
        dbdata = self.cursor.fetchall()
        if len(dbdata) == 0:
            return None
        else:
            return self

    def get_id(self):  # -> usermanagement.user_session_handler.User:
        """
        Provides a User/UserMixin for each user. UID will be username, as in DB.
        Required by flask_login.UserMixin.
        Returns
        -------

        """
        db_username_query = "SELECT id FROM kack_users WHERE username = ?"

        self.cursor.execute(db_username_query, (self.username,))
        db_username_data = self.cursor.fetchall()
        if len(db_username_data) == 0:
            return None
        elif len(db_username_data) > 1:
            self.logger.critical(
                f"Username {self.username} is multiple times in the database! How even?"
            )
            return None
        else:
            # return user id
            if db_username_data[0][0]:
                return db_username_data[0][0]
            else:
                return None

    def login(self, cryptpwd: str) -> bool:
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
        query = "SELECT password FROM kack_users WHERE username = ?;"
        self.cursor.execute(query, (self.username,))
        dbdata = self.cursor.fetchall()
        if len(dbdata) == 0:
            return False
        elif len(dbdata) > 1:
            self.logger.critical(
                f"Username {self.username} is multiple times in the database! How even?"
            )
            return False
        else:
            # user exists and pwd was loaded from db. check pwd.
            if cryptpwd == dbdata[0][0]:
                return True
            else:
                return False
