import datetime

from kacky_eventpage_backend.db_ops.db_base import DBConnection


class TokenBlacklist(DBConnection):
    def blacklist_token(self, jti):
        query = "INSERT INTO token_blacklist(jti, date) VALUES (?, ?)"
        self._cursor.execute(
            query, (jti, datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        )
        self._connection.commit()

    def check_token(self, jti):
        query = "SELECT COUNT(1) FROM token_blacklist WHERE jti = ?"
        self._cursor.execute(query, (jti,))
        # return True if revoked
        return self._cursor.fetchone()[0] != 0
