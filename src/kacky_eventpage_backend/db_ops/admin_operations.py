import datetime

from kacky_eventpage_backend.db_ops.db_base import DBConnection


class AdminOperators(DBConnection):
    def reset_wr(self, eventtype: str, kacky_id: int):
        query = """
            UPDATE worldrecords
            INNER JOIN maps ON worldrecords.map_id = maps.id
            INNER JOIN events ON events.id = maps.kackyevent
            SET
                worldrecords.score = 1,
                worldrecords.nickname = "reset_by_admin",
                worldrecords.login = "reset_by_admin"
            WHERE events.type = ? AND kacky_id_int = ?
        """
        self._cursor.execute(query, (eventtype, kacky_id))
        self._connection.commit()
        return True

    def add_event(
        self,
        name: str,
        etype: str,
        edition: int,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        min_ID: int,
        max_ID: int,
    ):
        # check if event+edition already exists
        checkquery = "SELECT type, edition FROM events WHERE type=? AND edition=?;"
        self._cursor.execute(checkquery, (etype, edition))
        if len(self._cursor.fetchall()) > 0:
            return -1
        checkquery = "SELECT name FROM events WHERE name=?;"
        self._cursor.execute(checkquery, (name,))
        if len(self._cursor.fetchall()) > 0:
            return -2
        # check if kacky IDs already exist for an edition.
        # Just check if min_ID or max_ID maps exist in maps table for the event
        checkquery = """
            SELECT kacky_id_int FROM maps
            INNER JOIN events ON maps.kackyevent = events.id
            WHERE events.type = ? AND kacky_id_int BETWEEN ? AND ?;
        """
        self._cursor.execute(checkquery, (etype, min_ID, max_ID))
        if len(self._cursor.fetchall()) > 0:
            return -3

        # i just notices i dont even use map ids in this table ^^
        # TODO fix or ignore
        insertquery = """
            INSERT INTO events(name, shortname, type, edition, startdate, enddate)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        self._cursor.execute(
            insertquery,
            (name, f"{etype.upper()}{edition}", etype, edition, start_date, end_date),
        )
        self._connection.commit()
        return 1

    def update_maps(self, map_data, overwrite=False):
        # quick check if we overwrite anything by checking events. most of the time this function should be called when
        # a new event is added anyways. event is second value per dataset
        import logging

        logger = logging.getLogger(self._config["logger_name"])
        upd_events = {e[3] for e in map_data}
        self._cursor.execute("SELECT id, shortname FROM events;", ())
        db_events = self._cursor.fetchall()
        db_shortnames = {e[1]: e[0] for e in db_events}
        overwrite_candidates = [e for e in upd_events if e in db_shortnames.keys()]
        # if we would overwrite something and do not overwrite, return 419
        logger.debug(overwrite_candidates)
        logger.debug(overwrite)
        if overwrite_candidates and not overwrite:
            logger.debug("Will not overwrite")
            return 409
        # in theory we should check all kacky_ids for overwrites - but in this case it's safe to assume
        # that admins are not malicious
        # if `overwrite` is false, we only have insert operations. if it's true, we may have an update.
        if not overwrite:
            query_insert_map = """
                INSERT INTO
                    maps(kackyevent, name, kacky_id, kacky_id_int, map_version, author, tmx_id, tm_uid, difficulty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            query_insert_at = """
                INSERT INTO
                    worldrecords(map_id, nickname, login, score, source, date)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            query_insert_wr_discord = """
                INSERT INTO
                    worldrecords_discord_notify(id, notified, time_diff)
                VALUES (?, 1, 0);
            """
            try:
                for data in map_data:
                    self._cursor.execute(
                        query_insert_map,
                        (
                            db_shortnames[data[3]],
                            f"{data[0]}{data[1]}",
                            data[1],
                            data[1]
                            if isinstance(data[1], int)
                            else int(data[1].split(" ")[0]),
                            ""
                            if isinstance(data[1], int)
                            else int(data[1].split(" ")[1]),
                            data[2],
                            data[6],
                            data[7],
                            data[5],
                        ),
                    )
                    # get id of map we just inserted. I dislike this, but in reality it'll work fine in this case
                    self._cursor.execute("SELECT LAST_INSERT_ID();", ())
                    last_id = self._cursor.fetchone()[0]
                    self._cursor.execute(
                        query_insert_at,
                        (
                            last_id,
                            "",
                            data[2],
                            data[4],
                            "AT",
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    # get id of wr we just inserted. I dislike this, but in reality it'll work fine in this case
                    self._cursor.execute("SELECT LAST_INSERT_ID();", ())
                    last_id = self._cursor.fetchone()[0]
                    self._cursor.execute(query_insert_wr_discord, (last_id,))
            except Exception as e:
                self._logger.error(f"Failed to update maps from CSV! {e}")
                self._connection.rollback()
                return 500
            self._connection.commit()
        else:
            return 501
        return 200

    def change_event_visible(self, eventid: int, newValue: bool):
        query = "UPDATE events SET visible = ? WHERE id = ?;"
        self._cursor.execute(query, (newValue, eventid))
        self._connection.commit()
