import pathlib
import sqlite3

from usermanagement.user_operations import UserDataMngr


class AlarmChecker:
    def __init__(self, config):
        # set up database connection to manage projects
        self.connection = sqlite3.connect(pathlib.Path(__file__).parents[1] / "stuff.db")
        #        self.connection = sqlite3.connect("/var/www/flask/kim_kk_dev_site/stuff.db")
        self.cursor = self.connection.cursor()
        self.config = config

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

    def get_alarms_for_user(self, user):
        query = "SELECT setalarms FROM alarms WHERE username = ?;"
        req = self.cursor.execute(query, (user,)).fetchall()
        if not req:  # no values
            return []
        alarmlist = req[0][0].split()
        return alarmlist

    def set_alarms_for_user(self, user, alarmlist):
        query = "UPDATE alarms SET setalarms = ? WHERE username = ?"
        self.cursor.execute(query, (' '.join(alarmlist), user))
        self.connection.commit()

    def get_users_for_map(self, mapid):
        query = "SELECT username FROM alarms WHERE setalarms LIKE ?;"
        req = self.cursor.execute(query, ("%" + str(mapid) + "%",)).fetchall()
        return req

    def get_discord_ids_for_map(self, mapid):
        usernames = self.get_users_for_map(mapid)
        um = UserDataMngr(self.config)
        ids = list(map(lambda u: um.get_discord_id(u[0]), usernames))
        return ids
