import hashlib
import logging

import mariadb


class UserDataMngr:
    """
    This class handles all data in the database, updating and reading. Login stuff is
    handled in usermanagement.user_session_handler.User.
    """

    def __init__(self, config, secrets):
        """
        Sets up obj, creates a database connection.
        """
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])

        # set up database connection to manage projects
        try:
            self.connection = mariadb.connect(
                host=self.config["dbhost"],
                port=self.config["dbport"],
                user=secrets["dbuser"],
                passwd=secrets["dbpwd"],
                database=self.config["dbname"],
            )
        except mariadb.Error as e:
            self.logger.error(f"Connecting to database failed! {e}")
            raise e
        self.cursor = self.connection.cursor()

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

    def add_user(self, user, cryptpwd, cryptmail) -> bool:
        """
        Add a user to the database

        Parameters
        ----------
        user: str
            username for the new account
        cryptpwd: str
            hashed password for the new account
        cryptmail:
            hashed mail for the new account

        Returns
        -------
        bool
            True if account was created, False if creation failed
        """
        self.logger.info(f"Trying to create user {user}.")
        # Check if user already exists
        query = "SELECT username FROM kack_users WHERE username = ?;"
        self.cursor.execute(query, (user,))
        if not self.cursor.fetchall():
            self.connection.commit()
            self.logger.info(f"User {user} does not yet exist. Creating.")
            query = "INSERT INTO kack_users(username, password, mail) VALUES (?, ?, ?);"
            self.cursor.execute(query, (user, cryptpwd, cryptmail))
            self.connection.commit()
            return True
        else:
            self.logger.error(f"User {user} already exists! Aborting user creation!")
            return False

    def set_discord_id(self, userid: int, new_discord_id: str):
        query = "UPDATE `user_fields` SET `discord_handle` = ? WHERE `id` = ?"
        self.cursor.execute(query, (new_discord_id, userid))
        self.connection.commit()

    def get_discord_id(self, userid: str) -> str:
        """
        Read current Discord ID from the database

        Parameters
        ----------
        userid : str
            username in the KK system

        Returns
        -------
        str
            Discord ID
        """
        query = "SELECT `discord_handle` FROM `user_fields` WHERE `id` = ?;"
        self.cursor.execute(query, (userid,))
        return self.cursor.fetchone()[0]

    def set_tm20_login(self, user_id: int, tmid: str):
        """
        Sets the users TM login in the DB.

        Parameters
        ----------
        user_id: str
            user for whom to set the TM login
        tmid:
            TM account name
        """
        query = "UPDATE `user_fields` SET `tm20_login` = ? WHERE `id` = ?"
        self.cursor.execute(query, (tmid, user_id))
        self.connection.commit()

    def get_tm20_login(self, user_id: int) -> str:
        """
        Returns the TM login for a user from DB

        Parameters
        ----------
        user_id: str
            User for who the TM account shall be returned

        Returns
        -------
        str
            TM login for specified user
        -------

        """
        query = "SELECT `tm20_login` FROM `user_fields` WHERE `id` = ?;"
        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchone()[0]

    def set_tmnf_login(self, user_id: int, tmid: str):
        """
        Sets the users TM login in the DB.

        Parameters
        ----------
        user_id: str
            user for whom to set the TM login
        tmid:
            TM account name
        """
        query = "UPDATE `user_fields` SET `tmnf_login` = ? WHERE `id` = ?"
        self.cursor.execute(query, (tmid, user_id))
        self.connection.commit()

    def get_tmnf_login(self, user_id: int) -> str:
        """
        Returns the TM login for a user from DB

        Parameters
        ----------
        user_id: str
            User for who the TM account shall be returned

        Returns
        -------
        str
            TM login for specified user
        """
        query = "SELECT `tmnf_login` FROM `user_fields` WHERE `id` = ?;"
        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchone()[0]

    def get_spreadsheet_all(self, userid: int):
        query = "SELECT * FROM spreadsheet WHERE user_id = ?;"
        self.cursor.execute(query, (userid,))
        return self.cursor.fetchall()

    def get_spreadsheet_line(self, userid: int, mapid: int):
        query = "SELECT * FROM spreadsheet WHERE user_id = ? AND map_id = ?;"
        self.cursor.execute(query, (userid, mapid))
        return self.cursor.fetchall()

    def fetchone_and_only_one(self):
        qres = self.cursor.fetchall()
        if len(qres) > 1:
            raise AssertionError("Query returned more than one result set!")
        else:
            return qres
