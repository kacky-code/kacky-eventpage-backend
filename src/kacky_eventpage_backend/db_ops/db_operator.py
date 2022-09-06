from kacky_eventpage_backend.db_ops.db_base import DBConnection


class MiscDBOperators(DBConnection):
    def get_map_author(self, kackyid: int):
        query = "SELECT author FROM maps WHERE kacky_id = ?"
        try:
            return self.fetchone(query, (kackyid,))[0]
        except TypeError:
            return None
