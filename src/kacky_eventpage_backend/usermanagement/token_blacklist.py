import datetime

import mariadb


class TokenBlacklist:
    def __init__(self, config, secrets):
        try:
            self.connection = mariadb.connect(
                host=config["dbhost"],
                port=config["dbport"],
                user=secrets["dbuser"],
                passwd=secrets["dbpwd"],
                database=config["dbname"],
            )
        except mariadb.Error as e:
            self.logger.error(f"Connecting to database failed! {e}")
            raise e
        self.cursor = self.connection.cursor()

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

    def blacklist_token(self, jti):
        query = "INSERT INTO token_blacklist(jti, date) VALUES (?, ?)"
        self.cursor.execute(
            query, (jti, datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        )
        self.connection.commit()

    def check_token(self, jti):
        query = "SELECT COUNT(1) FROM token_blacklist WHERE jti = ?"
        self.cursor.execute(query, (jti,))
        # return True if revoked
        return self.cursor.fetchone()[0] != 0
