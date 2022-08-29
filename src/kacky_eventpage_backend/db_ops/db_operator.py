from kacky_eventpage_backend.db_ops.db_base import DBConnection


class MiscDBOperators(DBConnection):
    def get_map_author(self, kackyid: int):
        query = "SELECT author FROM maps WHERE kacky_id = ?"
        self._cursor.execute(query, (kackyid,))
        return self._cursor.fetchone()[0]
