from kacky_eventpage_backend.db_ops.db_base import DBConnection


class MiscDBOperators(DBConnection):
    def get_map_author(self, kackyid: int):
        query = "SELECT author FROM maps WHERE kacky_id = ?"
        self._cursor.execute(query, (kackyid,))
        return self._cursor.fetchone()[0]

    def get_map_kackyIDs_for_event(
        self, eventtype: str, edition: int, raw: bool = False
    ):
        query = """
                SELECT kacky_id
                FROM maps
                INNER JOIN events on maps.kackyevent = events.id
                WHERE events.type = ? AND events.edition = ?
                """
        self._cursor.execute(query, (eventtype, edition))
        if raw:
            self._cursor.fetchall()
        # cannot map to int because "[v2]" in KR maps breaks it
        # return list(map(lambda e: int(e[0]), self._cursor.fetchall()))
        return [m[0] for m in self._cursor.fetchall()]

    def get_wr_leaderboard_by_etype(self, eventtype: str, raw: bool = False):
        query = """
                SELECT
                    COUNT(COALESCE(NULLIF(w.login, ''), tmx.tmf_login)) cnt,
                    COALESCE(NULLIF(w.login, ''), tmx.tmf_login) login
                FROM worldrecords w
                LEFT JOIN tmx_tmlogin_mapping tmx ON w.nickname = tmx.tmx_login
                INNER JOIN maps m ON m.id = w.map_id
                INNER JOIN events e ON e.id = m.kackyevent
                WHERE e.type = ?
                GROUP BY COALESCE(NULLIF(w.login, ''), tmx.tmf_login)
                ORDER BY cnt DESC;
                """
        self._cursor.execute(query, (eventtype,))
        if raw:
            self._cursor.fetchall()
        return [
            {"nwrs": d[0], "login": d[1]}
            for d in self._cursor.fetchall()
            if d[1] is not None
        ]

    def get_most_recent_nicknames(self, eventtype: str, raw: bool = False):
        query = """
                SELECT
                    COALESCE(NULLIF(w.login, ''), tmx.tmf_login) login,
                    COALESCE(NULLIF(w.nickname, ''), tmx.tmf_login) nickname,
                    MAX(date)
                FROM worldrecords AS w
                LEFT JOIN tmx_tmlogin_mapping tmx ON w.nickname = tmx.tmx_login
                INNER JOIN maps m ON m.id = w.map_id
                INNER JOIN events e ON e.id = m.kackyevent
                WHERE e.type = ?
                GROUP BY COALESCE(NULLIF(w.login, ''), tmx.tmf_login);
                """
        query = """
                SELECT
                    login,
                    nickname,
                    MAX(date)
                FROM worldrecords AS w
                INNER JOIN maps m ON m.id = w.map_id
                INNER JOIN events e ON e.id = m.kackyevent
                WHERE e.type = ?
                GROUP BY login;
                """
        self._cursor.execute(query, (eventtype,))
        if raw:
            self._cursor.fetchall()
        return {d[0]: d[1] for d in self._cursor.fetchall()}
