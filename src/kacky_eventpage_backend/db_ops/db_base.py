import logging
import queue
from typing import Tuple

import mariadb


class DBConnection:
    class __DBConnection:
        def __init__(self, config, secrets):
            """
            Sets up obj, creates a database connection.
            """
            self._config = config
            self._logger = logging.getLogger(self._config["logger_name"])

            # set up database connection to manage projects
            try:
                self.connection = mariadb.connect(
                    host=self._config["dbhost"],
                    port=self._config["dbport"],
                    user=secrets["dbuser"],
                    passwd=secrets["dbpwd"],
                    database=self._config["dbname"],
                )
            except mariadb.Error as e:
                self._logger.error(f"Connecting to database failed! {e}")
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

        def __enter__(self):
            """
            Required for "with" instantiation to work correctly
            """
            return self

    connections = None

    def __init__(self, config, secrets):
        if not DBConnection.connections:
            DBConnection.connections = queue.Queue(config["num_db_connections"])
            for i in range(config["num_db_connections"]):
                DBConnection.connections.put(
                    DBConnection.__DBConnection(config, secrets)
                )

        self._config = config
        self._logger = logging.getLogger(self._config["logger_name"])

    def _get_execute(
        self, query: str, args: Tuple, fetch: str = None, columns: bool = False
    ):
        # Get a connection from the pool. Times out after 2 seconds
        con = DBConnection.connections.get(block=True, timeout=2)
        con.cursor.execute(query, args)
        print(f"using connection {con}")
        result = None
        colnames = []
        if columns:
            colnames = [col[0] for col in con.cursor.description]

        if fetch == "all":
            result = con.cursor.fetchall()
        elif fetch == "one":
            result = con.cursor.fetchone()
        con.connection.commit()
        DBConnection.connections.put(con)
        return (result, colnames) if columns else result

    def fetchall(self, query: str, args: Tuple, columns: bool = False):
        a = self._get_execute(query, args, fetch="all", columns=columns)
        print(1)
        return a

    def fetchone(self, query: str, args: Tuple, columns: bool = False):
        return self._get_execute(query, args, fetch="one", columns=columns)

    def execute(self, query: str, args: Tuple):
        return self._get_execute(query, args)
