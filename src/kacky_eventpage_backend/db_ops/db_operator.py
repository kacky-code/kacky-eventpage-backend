from kacky_eventpage_backend.db_ops.db_base import DBConnection


class MiscDBOperators(DBConnection):
    def get_map_author(self, kackyid: int):
        query = "SELECT author FROM maps WHERE kacky_id = ?"
        self._cursor.execute(query, (kackyid,))
        return self._cursor.fetchone()[0]

    def get_map_kackyIDs_for_event(self, eventtype: str, edition: int, raw: bool = False):
        query = """
                SELECT kacky_id 
                FROM maps 
                INNER JOIN events on maps.kackyevent = events.id 
                WHERE events.type = ? AND events.edition = ?
                """
        self._cursor.execute(query, (eventtype, edition))
        if raw:
            self._cursor.fetchall()
        return list(map(lambda e: int(e[0]), self._cursor.fetchall()))
