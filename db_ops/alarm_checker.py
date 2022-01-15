import pathlib
import sqlite3

from usermanagement.usermanager import UserMngr


class AlarmChecker:
    def __init__(self, config):
        # set up database connection to manage projects
        self.connection = sqlite3.connect(pathlib.Path(__file__).parents[1] / "stuff.db")
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
        req = self.cursor.execute(f"SELECT setalarms FROM alarms WHERE username = '{user}';").fetchall()
        if not req:     # no values
            return []
        alarmlist = req[0][0].split()
        return alarmlist

    def set_alarms_for_user(self, user, alarmlist):
        self.cursor.execute(f"UPDATE alarms SET setalarms = '{' '.join(alarmlist)}'"
                            f"WHERE username = '{user}'")
        self.connection.commit()

    def get_users_for_map(self, mapid):
        req = self.cursor.execute(f"SELECT username FROM alarms WHERE setalarms LIKE '%{mapid}%';").fetchall()
        return req

    def get_discord_ids_for_map(self, mapid):
        usernames = self.get_users_for_map(mapid)
        um = UserMngr(self.config)
        ids = list(map(lambda u: um.get_discord_id(u[0]), usernames))
        return ids
