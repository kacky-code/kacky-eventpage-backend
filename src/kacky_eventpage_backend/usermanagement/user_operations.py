from typing import Union

from kacky_eventpage_backend.db_ops.db_base import DBConnection


class UserDataMngr(DBConnection):
    """
    This class handles all data in the database, updating and reading. Login stuff is
    handled in usermanagement.user_session_handler.User.
    """

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
        self._logger.info(f"Trying to create user {user}.")
        # Check if user already exists
        query = "SELECT username FROM kack_users WHERE username = ?;"
        self._cursor.execute(query, (user,))
        if not self._cursor.fetchall():
            self._connection.commit()
            self._logger.info(f"User {user} does not yet exist. Creating.")
            query = "INSERT INTO kack_users(username, password, mail) VALUES (?, ?, ?);"
            self._cursor.execute(query, (user, cryptpwd, cryptmail))
            self._connection.commit()
            return True
        else:
            self._logger.error(f"User {user} already exists! Aborting user creation!")
            return False

    def set_discord_id(self, userid: int, new_discord_id: str):
        query = "UPDATE `user_fields` SET `discord_handle` = ? WHERE `id` = ?"
        self._cursor.execute(query, (new_discord_id, userid))
        self._connection.commit()

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
        self._cursor.execute(query, (userid,))
        return self._cursor.fetchone()[0]

    def toggle_discord_alarm(self, userid: int, mapid: int):
        # get currently set alarms
        query = "SELECT alarms FROM user_fields WHERE id = ?"
        self._cursor.execute(query, (userid,))
        alarms = self._cursor.fetchone()[0]

        # toggle alarm in list. For this, make alarms string a list, remove
        # or set the alarm and write it back to DB
        alarms = dict.fromkeys([int(a) for a in alarms.split(";")])
        try:
            # Remove alarm if exists
            del alarms[mapid]
        except KeyError:
            # Alarm not in list, add it
            alarms[mapid] = None

        # make alarms a string again
        alarmstr = ";".join(str(a) for a in alarms.keys())

        query = "UPDATE user_fields SET alarms = ? WHERE id = ?;"
        self._cursor.execute(query, (alarmstr, userid))
        self._connection.commit()

    def get_discord_alarms(self, userid: int):
        query = "SELECT alarms from user_fields WHERE id = ?;"
        self._cursor.execute(query, (userid,))
        return [int(map) for map in self._cursor.fetchone()[0].split(";")]

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
        self._cursor.execute(query, (tmid, user_id))
        self._connection.commit()

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
        self._cursor.execute(query, (user_id,))
        return self._cursor.fetchone()[0]

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
        self._cursor.execute(query, (tmid, user_id))
        self._connection.commit()

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
        self._cursor.execute(query, (user_id,))
        return self._cursor.fetchone()[0]

    def get_spreadsheet_all(self, userid: Union[str, None]):
        default_line = {
            "map_diff": 0,
            "map_pb": "",
            "map_rank": None,
            "clip": "",
            "alarm": False,
            "finished": False,
        }
        if userid:
            query = """
                SELECT
                    spreadsheet.map_diff,
                    spreadsheet.map_pb,
                    spreadsheet.map_rank,
                    spreadsheet.clip,
                    maps.kacky_id
                FROM spreadsheet
                LEFT JOIN maps ON spreadsheet.map_id = maps.id
                WHERE user_id = ?;
            """
            self._cursor.execute(query, (userid,))
            # get column names to build a dictionary as result
            columns = [col[0] for col in self._cursor.description]
            qres = self._cursor.fetchall()
        else:
            qres = {
                m: {}
                for m in range(self._config["min_mapid"], self._config["max_mapid"] - 1)
            }
            return qres
        # make a dict from the result set
        sdict = [dict(zip(columns, row)) for row in qres]
        # make kacky_ids the key of a dict containing all the data (do this in
        # an extra step to use `kacky_id` key from the dict instead of some
        # hardcoded array position. Slightly more work, but should be fine
        sdict = {row["kacky_id"]: row for row in sdict}
        # STUPID CODE STARTS HERE
        # remove kacky_id from data, as it's the key now
        # also add missing keys with default values
        for map in sdict.values():
            del map["kacky_id"]
            if len(map) < len(default_line):
                for key in default_line:
                    if key not in map:
                        map[key] = default_line[key]
        # add missing maps which do not have any data stored
        for missmap in range(self._config["min_mapid"], self._config["max_mapid"] + 1):
            if missmap not in sdict.keys():
                sdict.setdefault(missmap, default_line.copy())
        discord_alarms = self.get_discord_alarms(userid)
        for alarm in discord_alarms:
            sdict[alarm]["alarm"] = True
        return sdict

    def get_spreadsheet_line(self, userid: int, mapid: int):
        query = "SELECT * FROM spreadsheet WHERE user_id = ? AND map_id = ?;"
        self._cursor.execute(query, (userid, mapid))
        return self._cursor.fetchall()

    def set_map_clip(self, userid: int, mapid: int, clip: str):
        query = """
            INSERT INTO spreadsheet(user_id, map_id, clip)
            VALUES (
                        ?,
                        (SELECT maps.id FROM maps WHERE maps.kacky_id = ?),
                        ?
                    )
            ON DUPLICATE KEY
            UPDATE spreadsheet.clip = ?;
        """
        self._cursor.execute(query, (userid, mapid, clip, clip))
        self._connection.commit()

    def set_map_difficulty(self, userid: int, mapid: int, diff: int):
        query = """
                    INSERT INTO spreadsheet(user_id, map_id, map_diff)
                    VALUES (
                                ?,
                                (SELECT maps.id FROM maps WHERE maps.kacky_id = ?),
                                ?
                            )
                    ON DUPLICATE KEY
                    UPDATE spreadsheet.map_diff = ?;
                """
        self._cursor.execute(query, (userid, mapid, diff, diff))
        self._connection.commit()

    def fetchone_and_only_one(self):
        qres = self._cursor.fetchall()
        if len(qres) > 1:
            raise AssertionError("Query returned more than one result set!")
        else:
            return qres
