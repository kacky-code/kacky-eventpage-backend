from sys import stderr

import mariadb
import yaml

with open("config.yaml", "r") as conffile:
    config = yaml.load(conffile, Loader=yaml.FullLoader)

with open("secrets.yaml", "w") as secfile:
    secrets = yaml.load(secfile, Loader=yaml.FullLoader)

# Establish the connection
connection = mariadb.connect(
    user=secrets["dbuser"],
    password=secrets["dbuser"],
    host=config["dbhost"],
    port=config["dbport"],
    database=config["dbname"],
)
cursor = connection.cursor()

tables = [
    """
    CREATE TABLE `events` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `name` text NOT NULL,
        `shortname` text NOT NULL,
        `type` text NOT NULL,
        `edition` int(11) NOT NULL,
        `startdate` date NOT NULL,
        `enddate` date NOT NULL,
        `visible` tinyint(1) NOT NULL DEFAULT 0,
        PRIMARY KEY (`id`)
    );
    """,
    """
    CREATE TABLE `kack_users` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `username` text NOT NULL,
        `password` text NOT NULL,
        `mail` text NOT NULL,
        `is_admin` tinyint(1) NOT NULL DEFAULT 0,
        PRIMARY KEY (`id`),
        UNIQUE KEY `username` (`username`) USING HASH
    );
    """,
    """
    CREATE TABLE `leaderboard` (
        `rank` int(11) NOT NULL,
        `playername` text NOT NULL,
        `last_update` datetime NOT NULL,
        PRIMARY KEY (`rank`)
    );
    """,
    """
    CREATE TABLE `login_relations_discord` (
        `discord_id` bigint(20) NOT NULL,
        `discord_username` varchar(32) NOT NULL,
        `tmnf` varchar(25) DEFAULT '',
        `tm20` varchar(15) DEFAULT '',
        `tmx` varchar(25) DEFAULT '',
        PRIMARY KEY (`discord_id`)
    );
    """,
    """
    CREATE TABLE `maps` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `kackyevent` int(11) NOT NULL,
        `name` text NOT NULL,
        `kacky_id` text NOT NULL,
        `kacky_id_int` int(11) NOT NULL,
        `map_version` varchar(10) DEFAULT NULL,
        `author` text NOT NULL,
        `tmx_id` text DEFAULT '',
        `tm_uid` text DEFAULT '',
        `difficulty` int(11) DEFAULT 0,
        PRIMARY KEY (`id`),
        KEY `fk_maps_event` (`kackyevent`),
        CONSTRAINT `fk_maps_event` FOREIGN KEY (`kackyevent`) REFERENCES `events` (`id`)
    );
    """,
    """
    CREATE TABLE `reset_tokens` (
        `user_id` int(11) NOT NULL,
        `timestamp` timestamp NOT NULL DEFAULT current_timestamp(),
        `token` varchar(6) NOT NULL,
        KEY `user_id` (`user_id`),
        CONSTRAINT `reset_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `kack_users` (`id`)
    );
    """,
    """
    CREATE TABLE `spreadsheet` (
        `user_id` int(11) NOT NULL,
        `map_id` int(11) NOT NULL,
        `map_diff` int(11) DEFAULT 0,
        `map_pb` int(11) DEFAULT 0,
        `map_rank` int(11) DEFAULT 0,
        `clip` text DEFAULT '',
        PRIMARY KEY (`user_id`,`map_id`),
        KEY `fk_Spreadsheet_mapid` (`map_id`),
        CONSTRAINT `fk_Spreadsheet_id` FOREIGN KEY (`user_id`) REFERENCES `kack_users` (`id`),
        CONSTRAINT `fk_Spreadsheet_mapid` FOREIGN KEY (`map_id`) REFERENCES `maps` (`id`)
    );
    """,
    """
    CREATE TABLE `tmx_tmlogin_mapping` (
        `tmx_login` varchar(30) DEFAULT NULL,
        `tmf_login` varchar(30) DEFAULT NULL,
        `tm20_login` varchar(30) DEFAULT NULL
    );
    """,
    """
    CREATE TABLE `token_blacklist` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `jti` text NOT NULL,
        `date` datetime NOT NULL,
        PRIMARY KEY (`id`)
    );
    """,
    """
    CREATE TABLE `user_fields` (
        `id` int(11) NOT NULL,
        `discord_handle` text DEFAULT '',
        `tm20_login` text DEFAULT '',
        `tmnf_login` text DEFAULT '',
        `alarms` text DEFAULT '',
        PRIMARY KEY (`id`),
        CONSTRAINT `fk_UserFields_id` FOREIGN KEY (`id`) REFERENCES `kack_users` (`id`)
    );
    """,
    """
    CREATE TABLE `worldrecords` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `map_id` int(11) NOT NULL,
        `nickname` text NOT NULL,
        `login` text NOT NULL,
        `score` int(11) NOT NULL,
        `date` datetime NOT NULL,
        `source` text NOT NULL,
        PRIMARY KEY (`id`),
        KEY `fk_Workdrecords_mapid` (`map_id`),
        CONSTRAINT `fk_Workdrecords_mapid` FOREIGN KEY (`map_id`) REFERENCES `maps` (`id`)
    );
    """,
    """
    CREATE TABLE `worldrecords_discord_notify` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `notified` tinyint(1) DEFAULT 1,
        `time_diff` int(11) DEFAULT 0,
        PRIMARY KEY (`id`),
        CONSTRAINT `fk_Worldrecords_nootify_id` FOREIGN KEY (`id`) REFERENCES `worldrecords` (`id`)
    );
    """,
]

try:
    for table in tables:
        cursor.execute(table)
except mariadb.Error as e:
    print(f"Error: {e}", file=stderr)
    connection.rollback()

connection.commit()
