from pathlib import Path
from subprocess import run

from kacky_eventpage_backend import config, secrets

run(["mysql", "-u", secrets["dbuser"], f"-p{secrets['dbpwd']}", "-h", config["dbhost"], "-e", f"CREATE DATABASE IF NOT EXISTS `{config['dbname']}` COLLATE utf8_general_ci;"])
run(["mysql", "-u", secrets["dbuser"], f"-p{secrets['dbpwd']}", "-h", config["dbhost"], config['dbname'], "<", Path(__file__).parent / "init.sql"])