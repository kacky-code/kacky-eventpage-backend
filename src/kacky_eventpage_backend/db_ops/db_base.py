import logging

import mariadb


class DBConnection:
    def __init__(self, config, secrets):
        """
        Sets up obj, creates a database connection.
        """
        self._config = config
        self._logger = logging.getLogger(self._config["logger_name"])

        # set up database connection to manage projects
        try:
            self._connection = mariadb.connect(
                host=self._config["dbhost"],
                port=self._config["dbport"],
                user=secrets["dbuser"],
                passwd=secrets["dbpwd"],
                database=self._config["dbname"],
            )
        except mariadb.Error as e:
            self._logger.error(f"Connecting to database failed! {e}")
            raise e
        self._cursor = self._connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit hook, closes DB connection if object is destroyed

        Parameters
        ----------
        exc_type
        exc_val
        exc_tb
        """
        self._connection.close()

    def __enter__(self):
        """
        Required for "with" instantiation to work correctly
        """
        return self
