import datetime
import random
import string
from typing import Union

from kacky_eventpage_backend.db_ops.db_base import DBConnection


def token_generator(length: int):
    return "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )


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
            query = """
                INSERT INTO user_fields(id)
                SELECT kack_users.id
                FROM kack_users
                WHERE kack_users.username = ?;
            """
            self._cursor.execute(query, (user,))
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
        return self._cursor.fetchone()[0] or ""

    def toggle_discord_alarm(self, userid: int, mapid: str, eventtype: int):
        # get currently set alarms
        query = "SELECT alarms FROM user_fields WHERE id = ?"
        self._cursor.execute(query, (userid,))
        alarms = self._cursor.fetchone()[0]

        # toggle alarm in list. For this, make alarms string a list, remove
        # or set the alarm and write it back to DB
        if alarms != "":
            alarms = dict.fromkeys(alarms.split(";"))
        else:
            alarms = {}
        try:
            # Remove alarm if exists
            del alarms[mapid]
        except KeyError:
            # Alarm not in list, add it
            alarms[mapid] = None

        # make alarms a string again
        alarmstr = ";".join(alarms.keys())

        query = "UPDATE user_fields SET alarms = ? WHERE id = ?;"
        self._cursor.execute(query, (alarmstr, userid))
        self._connection.commit()

    def get_discord_alarms(self, userid: int):
        query = "SELECT alarms from user_fields WHERE id = ?;"
        self._cursor.execute(query, (userid,))
        try:
            return self._cursor.fetchone()[0].split(";")
        except ValueError:
            return ""

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
        return self._cursor.fetchone()[0] or ""

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
        return self._cursor.fetchone()[0] or ""

    def get_spreadsheet_all(self, userid: Union[str, None]):
        default_line = {
            "map_diff": 0,
            "map_pb": 0,
            "map_rank": 0,
            "clip": "",
            "kacky_id": None,
            "author": "",
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
                    maps.kacky_id,
                    maps.author
                FROM spreadsheet
                LEFT JOIN maps ON spreadsheet.map_id = maps.id
                WHERE user_id = ?;
            """
            self._cursor.execute(query, (userid,))
            # get column names to build a dictionary as result
            columns = [col[0] for col in self._cursor.description]
            qres = self._cursor.fetchall()
            # make a dict from the result set
            sdict = [dict(zip(columns, row)) for row in qres]
            # make kacky_ids the key of a dict containing all the data (do this in
            # an extra step to use `kacky_id` key from the dict instead of some
            # hardcoded array position. Slightly more work, but should be fine
            sdict = {row["kacky_id"]: row for row in sdict}
        else:
            sdict = {
                m: {"kacky_id": m}
                for m in range(self._config["min_mapid"], self._config["max_mapid"] + 1)
            }
            # Add map authors
        authorquery = """
            SELECT maps.kacky_id, maps.author
            FROM maps
            WHERE maps.kacky_id BETWEEN ? AND ?
        """
        self._cursor.execute(
            authorquery, (self._config["min_mapid"], self._config["max_mapid"] + 1)
        )
        authors = self._cursor.fetchall()

        # STUPID CODE STARTS HERE
        # remove kacky_id from data, as it's the key now
        # also add missing keys with default values
        for map in sdict.values():
            # del map["kacky_id"]
            if len(map) < len(default_line):
                for key in default_line:
                    if key not in map:
                        map[key] = default_line[key]
        # add missing maps which do not have any data stored
        for missmap in range(self._config["min_mapid"], self._config["max_mapid"] + 1):
            if missmap not in sdict.keys():
                sdict.setdefault(missmap, default_line.copy())
                # sdict[missmap] = {}
                sdict[missmap]["kacky_id"] = missmap
        for m in authors:
            sdict[m[0]]["author"] = m[1]
        # Leave early, if not userid
        if not userid:
            return sdict
        discord_alarms = self.get_discord_alarms(userid)
        for alarm in discord_alarms:
            sdict[alarm]["alarm"] = True
        return sdict

    def get_spreadsheet_event(
        self, userid: Union[str, None], eventtype: str, edition: Union[int, str]
    ):
        if edition.isdigit():
            editions_where_clause = "AND events.edition = ?"
            if userid:
                query_params = (userid, eventtype, edition, eventtype, edition)
            else:
                query_params = (eventtype, edition)
        elif edition == "all":
            editions_where_clause = ""
            if userid:
                query_params = (userid, eventtype, eventtype)
            else:
                query_params = (eventtype,)
        else:
            raise ValueError("Bad value for edition!")
        if userid:
            query = f"""
                    SELECT
                        maps.kacky_id,
                        maps.author,
                        maps.difficulty as rating,
                        data.*,
                        wr.score AS wr_score,
                        wr.nickname AS wr_nick,
                        wr.login AS wr_login
                    FROM maps
                    LEFT JOIN (
                        SELECT
                            maps.id,
                            spreadsheet.map_diff,
                            spreadsheet.map_pb,
                            spreadsheet.map_rank,
                            spreadsheet.clip
                        FROM maps
                        LEFT JOIN spreadsheet ON spreadsheet.map_id = maps.id
                        INNER JOIN events ON maps.kackyevent = events.id
                        WHERE spreadsheet.user_id = ? AND events.type = ? {editions_where_clause}
                    ) AS data ON maps.id = data.id
                    LEFT JOIN events ON maps.kackyevent = events.id
                    INNER JOIN worldrecords AS wr ON maps.id = wr.map_id
                    WHERE events.type = ? {editions_where_clause}
                    ORDER BY CAST(maps.kacky_id AS INTEGER);
                    """
            self._cursor.execute(query, query_params)
            # get column names to build a dictionary as result
            columns = [col[0] for col in self._cursor.description]
        else:
            query = f"""
                    SELECT
                        maps.kacky_id,
                        maps.author,
                        maps.difficulty as rating,
                        wr.score AS wr_score,
                        wr.nickname AS wr_nick,
                        wr.login AS wr_login
                    FROM maps
                    LEFT JOIN events ON maps.kackyevent = events.id
                    INNER JOIN worldrecords AS wr ON maps.id = wr.map_id
                    WHERE events.type = ? {editions_where_clause}
                    ORDER BY CAST(maps.kacky_id AS INTEGER);
                    """
            self._cursor.execute(query, query_params)
            # get column names to build a dictionary as result
            columns = [col[0] for col in self._cursor.description]
        qres = self._cursor.fetchall()
        # make a dict from the result set
        sdict = [dict(zip(columns, row)) for row in qres]
        # only keep one element as wrholder. Value is either wr_login or wr_nick.
        # If wr_login is not empty string, use it. Else use wr_nick
        for mapinfo in sdict:
            if mapinfo["wr_login"] == "":
                mapinfo["wr_holder"] = mapinfo["wr_nick"]
            else:
                mapinfo["wr_holder"] = mapinfo["wr_login"]
            # delete both keys, they are unused now
            del mapinfo["wr_login"]
            del mapinfo["wr_nick"]

        for mapinfo in sdict:
            if mapinfo["wr_score"] == 1800000:
                mapinfo["wr_score"] = 0

        # make kacky_ids the key of a dict containing all the data (do this in
        # an extra step to use `kacky_id` key from the dict instead of some
        # hardcoded array position. Slightly more work, but should be fine
        sdict = {row["kacky_id"]: row for row in sdict}

        # Leave early, if not userid
        if not userid:
            return sdict
        # Add discord alarms to the mix
        discord_alarms = self.get_discord_alarms(userid)
        for alarm in discord_alarms:
            if alarm == "":
                continue
            try:
                sdict[alarm]["alarm"] = True
            except KeyError:
                # Do the dirty pass, but this most likely happens because user tries
                # to load an edition that has no discord alarms set.
                pass
        return sdict

    def get_spreadsheet_line(self, userid: int, mapid: str):
        query = "SELECT * FROM spreadsheet WHERE user_id = ? AND map_id = ?;"
        self._cursor.execute(query, (userid, mapid))
        return self._cursor.fetchall()

    def set_map_clip(self, userid: int, mapid: str, clip: str, eventtype: str):
        query = """
            INSERT INTO spreadsheet(user_id, map_id, clip)
            VALUES (
                        ?,
                        (
                            SELECT maps.id
                            FROM maps
                            INNER JOIN events on maps.kackyevent = events.id
                            WHERE events.type = ? AND maps.kacky_id = ?
                        ),
                        ?
                    )
            ON DUPLICATE KEY
            UPDATE spreadsheet.clip = ?;
        """
        self._cursor.execute(query, (userid, eventtype, mapid, clip, clip))
        self._connection.commit()

    def set_map_difficulty(self, userid: int, mapid: str, diff: int, eventtype: str):
        query = """
                    INSERT INTO spreadsheet(user_id, map_id, map_diff)
                    VALUES (
                                ?,
                                (
                                    SELECT maps.id
                                    FROM maps
                                    INNER JOIN events on maps.kackyevent = events.id
                                    WHERE events.type = ? AND maps.kacky_id = ?
                                ),
                                ?
                            )
                    ON DUPLICATE KEY
                    UPDATE spreadsheet.map_diff = ?;
                """
        self._cursor.execute(query, (userid, eventtype, mapid, diff, diff))
        self._connection.commit()

    def set_password(self, userid: int, newpwd: str):
        query = "UPDATE kack_users SET password = ? WHERE id = ?;"
        self._cursor.execute(query, (newpwd, userid))
        self._connection.commit()

    def set_mail(self, userid: int, newmail: str):
        query = "UPDATE kack_users SET mail = ? WHERE id = ?;"
        self._cursor.execute(query, (newmail, userid))
        self._connection.commit()

    def set_reset_token(self, user: str, cryptmail: str):
        # do opportunistic clean-up first. remove tokens older than 2 hours
        cleanup_query = (
            "DELETE FROM reset_tokens WHERE timestamp < (NOW() - INTERVAL 2 HOUR);"
        )
        self._cursor.execute(cleanup_query, ())
        userid_query = "SELECT id FROM kack_users WHERE mail = ? and username = ?;"
        self._cursor.execute(userid_query, (cryptmail, user))
        userid = self._cursor.fetchall()
        if len(userid) == 0 or len(userid) > 1:
            return -1
        # if user has active tokens, remove them
        cleanup_query = "DELETE FROM reset_tokens WHERE user_id = ?;"
        self._cursor.execute(cleanup_query, (userid[0][0],))

        # generate token
        token_ok = False
        resettoken = token_generator(6)
        # if token already exists, generate a new one
        while not token_ok:
            check_query = "SELECT token FROM reset_tokens WHERE token = ?;"
            self._cursor.execute(check_query, (resettoken,))
            if self._cursor.fetchall() == []:
                # token unique
                token_ok = True
            resettoken = token_generator(6)

        store_query = (
            "INSERT INTO reset_tokens(timestamp, user_id, token) VALUES (?, ?, ?);"
        )
        self._cursor.execute(
            store_query,
            (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                userid[0][0],
                resettoken,
            ),
        )
        self._connection.commit()
        return resettoken

    def reset_password_with_token(self, token: str, cryptpw: str):
        # check if token exists
        token_check_query = "SELECT user_id FROM reset_tokens WHERE token = ?;"
        self._cursor.execute(token_check_query, (token,))
        userid = self._cursor.fetchall()
        if len(userid) == 0 or len(userid) > 1:
            return False
        self.set_password(userid[0][0], cryptpw)
        token_delete_query = "DELETE FROM reset_tokens WHERE token = ?;"
        self._cursor.execute(token_delete_query, (token,))
        self._connection.commit()
        return True

    def fetchone_and_only_one(self):
        qres = self._cursor.fetchall()
        if len(qres) > 1:
            raise AssertionError("Query returned more than one result set!")
        else:
            return qres
