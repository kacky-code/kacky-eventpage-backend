import datetime
import json
import logging
from pathlib import Path

import flask
import requests as requests
import yaml

from datastructures.server import ServerInfo
from tm_format_resolver import TMstr

TEST_API_RESPONSE = {"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 1":{"jukebox":[],"recently_played":["sbQZsoFMQ0yi7I4zrZn6wn06_d1","eDjkDjgh2dOMzmSilAH6nWzWBv","Vb1uh9lRARwGVSdbx1g6LC4UKdi","o2Vneej0ouvNTav5LJTuygXaXz1","kprNTNffW1tnZsojh69vFAqxeqg"],"current_map":"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $0f4#223","time_played":"854"},"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 2":{"jukebox":[],"recently_played":["oPTugNFan8Q22EFeRt710HnclZm","yJ3V2YlglO7vusSGI5nVeCP8aFf","7tjAh6BpWj6eSPZehsutTwELAfk","nEOGfQ8W1iYS6PiFVqB8Eda_4bc","7ykxjr_DvbWBtZKDlsm9wTnzji2"],"current_map":"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $0f4#251","time_played":"702"},"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 3":{"jukebox":[],"recently_played":["gY_wuO4bY12OuT1WqIOWTZ2P4Da","4e8NjxQQrC3Hy_7cBBOmGhbYuyi","kwuHbknIiJGl6JT0bIQOixCXzYc","ESXoxCHq2nzWaTPSrFm5xbrNzld","f86RbkuB7YLcTj0uFAPfNuECsQi"],"current_map":"$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $0f4#234","time_played":"412"}}
# simo_900
TEST_LOGIN_RESPONSE_SIMO = {'finishes': 75, 'mapids': ['201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '215', '216', '217', '218', '219', '220', '221', '222', '223', '224', '225', '226', '227', '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243', '244', '245', '246', '247', '248', '249', '250', '251', '252', '253', '254', '255', '256', '257', '258', '259', '260', '261', '262', '263', '264', '265', '266', '267', '268', '269', '270', '271', '272', '273', '274', '275']}
# amgreborn
TEST_LOGIN_RESPONSE_AMG = {'finishes': 20, 'mapids': ['201', '202', '204', '211', '215', '219', '223', '225', '230', '236', '243', '245', '247', '252', '259', '262', '269', '272', '274', '275']}

class KackyAPIHandler:
    # dict managing servers
    servers = {}

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])
        self.last_update = datetime.datetime.fromtimestamp(0)
        try:
            with open(Path(__file__).parent / "secrets.yaml") as b:
                self.api_pwd = yaml.load(b, yaml.FullLoader)["api_pwd"]
        except FileNotFoundError:
            raise FileNotFoundError("Bot needs a bot.py with 'token' and 'guild' keys, containing the token for the bot and the ID of the guild to connect to!")

    def update_server_info(self):
        #if not self.last_update < datetime.datetime.now() - datetime.timedelta(minutes=1):
        #    # if last update is not older than one minute, use cached data
        #    self.logger.info("Use cached self.servers.")
        #    return

        self.logger.info("Updating self.servers.")
        try:
            if self.config["testing_mode"]:
                self.logger.error("Using TEST_API_RESPONSE")
                krdata = TEST_API_RESPONSE
            else:
                krdata = requests.get("https://kk.kackiestkacky.com/api/", params={"password": self.api_pwd}).json()
        except ConnectionError:
            self.logger.error("Could not connect to KK API!")
            flask.render_template('error.html',
                                  error="Could not contact KK server. RIP!")
            return
        except json.decoder.JSONDecodeError:
            # flask.render_template('error.html',
            #                      error="KK API returned strange data. RIP!")
            self.logger.error("Could not connect to KK API!")
            flask.render_template('error.html',
                                  error="Could not contact KK server. RIP!")
            return

        for server in krdata.keys():
            self.logger.debug(f"updating server '{server}'")
            d = krdata[server]
            self.logger.debug(f"new data: {d}")
            # check for first run
            if server not in self.servers:
                # this is the first run, need to build objects
                self.servers[server] = ServerInfo(TMstr(server), self.config)

            # update existing ServerInfo object
            self.servers[server].update_info(d)

        self.last_update = datetime.datetime.now()

    def get_fin_info(self, tmlogin):
        try:
            findata = requests.post("https://kk.kackiestkacky.com/api/", data={"login": tmlogin, "password": self.api_pwd}).json()
        except ConnectionError:
            self.logger.error("Could not connect to KK API!")
            flask.render_template('error.html',
                                  error="Could not contact KK server. RIP!")
        return findata

    def get_mapinfo(self):
        if any(map(lambda s: s.timeplayed < 0, self.servers.values())) or self.servers == {}:
            self.update_server_info()
