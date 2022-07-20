import hashlib
import json
import logging
import pathlib
import sqlite3


class UserDataMngr:
    """
    This class handles all data in the database, updating and reading. Login stuff is
    handled in usermanagement.user_session_handler.User.
    """

    def __init__(self, config):
        """
        Sets up obj, creates a database connection.
        """
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])

        # set up database connection to manage projects
        self.connection = sqlite3.connect(
            pathlib.Path(__file__).parents[3] / "stuff.db"
        )
        self.cursor = self.connection.cursor()
        # Create table if not exists
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS `kack_users` (
                            `id` INTEGER PRIMARY KEY,
                            `username` TEXT NOT NULL,
                            `passwd` TEXT NOT NULL,
                            `mail` TEXT NOT NULL,
                            `im_handle` TEXT,
                            `tm_login` TEXT
                            );"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS `alarms` (
                            `username` TEXT PRIMARY KEY,
                            `setalarms` TEXT
                            );"""
        )
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
        if not self.cursor.execute(query, (user,)).fetchall():
            self.logger.info(f"User {user} does not yet exist. Creating.")
            query = (
                "INSERT INTO kack_users(username, passwd, mail, tm_login) "
                "VALUES (?, ?, ?, '');"
            )
            self.cursor.execute(query, (user, cryptpwd, cryptmail))
            query = "INSERT INTO alarms(username, setalarms) VALUES (?, '');"
            self.cursor.execute(query, (user,))
            self.connection.commit()
            return True
        else:
            self.logger.error(f"User {user} already exists! Aborting user creation!")
            return False

    def set_discord_id(self, user: str, id: str):
        """
        Updates the users discord user handle in DB.

        Parameters
        ----------
        user: str
            user for whom update shall be done
        id: str
            updated discord handle
        """
        query = "SELECT im_handle FROM kack_users WHERE username = ?;"
        cur_IM = self.cursor.execute(query, (user,)).fetchall()
        try:
            cur_IM_dict = json.loads(cur_IM)
        except (json.decoder.JSONDecodeError, TypeError):
            # data either empty or borked
            cur_IM_dict = {"discord": id}
        else:
            # else Update
            cur_IM_dict["discord"] = id

        query = "UPDATE kack_users SET im_handle = ? WHERE username = ?"
        self.cursor.execute(query, (json.dumps(cur_IM_dict), user))
        self.connection.commit()

    def get_discord_id(self, user: str) -> str:
        """
        Read current Discord ID from the database

        Parameters
        ----------
        user : str
            username in the KK system

        Returns
        -------
        str
            Discord ID or "", if there is none stored
        """
        query = "SELECT im_handle FROM kack_users WHERE username = ?;"
        cur_IM = self.cursor.execute(query, (user,)).fetchall()
        if not cur_IM:
            return ""
        else:
            cur_IM = cur_IM[0][0]
        try:
            cur_IM = json.loads(cur_IM)
        except (json.decoder.JSONDecodeError, TypeError):
            return ""
        if "discord" in cur_IM:
            return cur_IM["discord"]
        else:
            return ""

    def set_tm_login(self, user: str, tmid: str):
        """
        Sets the users TM login in the DB.

        Parameters
        ----------
        user: str
            user for whom to set the TM login
        tmid:
            TM account name
        """
        query = "UPDATE kack_users SET tm_login = ? WHERE username = ?"
        self.cursor.execute(query, (tmid, user))
        self.connection.commit()

    def get_tm_login(self, user) -> str:
        """
        Returns the TM login for a user from DB

        Parameters
        ----------
        user: str
            User for who the TM account shall be returned

        Returns
        str
            TM login for specified user
        -------

        """
        query = "SELECT tm_login FROM kack_users WHERE username = ?;"
        return self.cursor.execute(query, (user,)).fetchall()[0][0]
