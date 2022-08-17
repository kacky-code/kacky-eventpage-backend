import argparse
import datetime
import logging
import pathlib
import sys

import mariadb
import pandas as pandas
import yaml


class ScheduleAdm:
    def __init__(self):
        self.logger = logging.getLogger("KackyEventAdm")
        logging.basicConfig(format="%(levelname)s: %(message)s")

        with open(pathlib.Path(__file__).parents[3] / "config.yaml", "r") as conff:
            self.config = yaml.load(conff, Loader=yaml.FullLoader)

        with open(pathlib.Path(__file__).parents[3] / "secrets.yaml", "r") as secf:
            self.secrets = yaml.load(secf, Loader=yaml.FullLoader)

        # Test connection to database
        self.cursor = self.connect_db()

        # Argparse setup
        self.parser = argparse.ArgumentParser(
            description="Admin tool for the Kacky Event Schedule Dingens"
        )

        self.parser.add_argument(
            "command", help="Subcommand to run", choices=["event", "maps"]
        )

        args = self.parser.parse_args(sys.argv[1:2])

        if not args.command:
            self.logger.error("Invalid command!")
            self.parser.print_help()
            exit(1)

        getattr(self, args.command)()

    def connect_db(self):
        # set up database connection to manage projects
        try:
            connection = mariadb.connect(
                host=self.config["dbhost"],
                port=self.config["dbport"],
                user=self.secrets["dbuser"],
                passwd=self.secrets["dbpwd"],
                database=self.config["dbname"],
            )
        except mariadb.Error as e:
            self.logger.error(f"Connecting to database failed! {e}")
            raise e
        return connection.cursor()

    def event(self):
        eventparser = argparse.ArgumentParser(
            description="Manage Events in Event Page Dingens"
        )
        eventparser.add_argument(
            "eventcommand",
            help="Select what to do for event management",
            choices=["add", "remove", "change"],
        )

        eventargs = eventparser.parse_args(sys.argv[2:])

        if eventargs.eventcommand == "add":
            print("Name of Event: ")
            name = str(input())
            print("Type (KK/KR/KX/...): ")
            etype = str(input())
            try:
                print("Start date (DD.MM.YYYY HH:MM): ")
                startd = datetime.datetime.strptime(input(), "%d.%m.%Y %H:%M")
                print("End date (DD.MM.YYYY HH:MM): ")
                endd = datetime.datetime.strptime(input(), "%d.%m.%Y %H:%M")
            except ValueError:
                logging.error(
                    "Looks like you entered a date in bad format! Please use format "
                    "'DD.MM.YYYY HH:MM' with 24 hour format for time!"
                )
                exit(-1)
            print(
                "CSV file containing map info for this event. Should have columns "
                "'mapname', 'kackyid', 'author':"
            )
            csvfile = pathlib.Path(str(input()))
            print(csvfile)

            if not csvfile.is_file():
                self.logger.error(f"Path '{csvfile}' does not exist!")
                exit(-1)

            # Use python engine for auto separator detection
            csvdata = pandas.read_csv(csvfile, header=0, sep=None, engine="python")
            if not sorted(["mapname", "kackyid", "author"]) == sorted(csvdata.columns):
                self.logger.error("Your columns are different from what's expected!")
                exit(-1)

            if csvdata.isnull().values.any():
                self.logger.error("Your CSV file has missing values!")
                exit(-1)

            print(f"{name} {etype} {startd} {endd}")


if __name__ == "__main__":
    ScheduleAdm()
