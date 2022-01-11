import datetime
import json
import logging

import flask
import requests as requests

from datastructures.server import ServerInfo
from tm_format_resolver import TMstr


TEST_API_RESPONSE = {
    "$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 4":
        {
            "jukebox":
                {
                    "flT49y2Z9zxZ9gQBcoVDMOG2k4i":
                        {
                            "map_name": "TryhardMania C13",
                            "juker_login": "amgreborn",
                            "juker_nickname": "$f00$f3b\u05d3\u05d5\u05d6\u03c2 $ga$nmgrebor$wn L\u0192s"}},
            "recently_played":
                [
                    "paE_uuyNdNVghxpvlVI7AqJefWh",
                    "iS0dXnuXbI5oHgXfTzdzGTGD427",
                    "F0gGGv7mzA8JCf5Ub7le1PKPcWd",
                    "aHkQ__XJk6lwq9Ne6JnopjsyPo3",
                    "F0gGGv7mzA8JCf5Ub7le1PKPcWd"
                ],
            "current_map": "$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y #242"
        },
    "$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 5":
        {
            "jukebox":
                {
                    "xN56ZHwvBr4Xn8KYhis4UPA7B59":
                        {
                            "map_name": "TryhardMania C05",
                            "juker_login": "amgreborn",
                            "juker_nickname": "$f00$f3b\u05d3\u05d5\u05d6\u03c2 $ga$nmgrebor$wn L\u0192s"
                        },
                    "paE_uuyNdNVghxpvlVI7AqJefWh":
                        {
                            "map_name": "TryhardMania C03",
                            "juker_login": "amgreborn",
                            "juker_nickname": "$f00$f3b\u05d3\u05d5\u05d6\u03c2 $ga$nmgrebor$wn L\u0192s"
                        },
                    "vSDCIt3koUcs_sJG38RLxkrcWl7":
                        {
                            "map_name": "$o$i$a0aK$a06a$a30ck$a60iest Kack$a00$a0ay $f40#\u20132",
                            "juker_login": "amgreborn",
                            "juker_nickname": "$f00$f3b\u05d3\u05d5\u05d6\u03c2 $ga$nmgrebor$wn L\u0192s"
                        }
                },
            "recently_played":
                [
                    "DdChQtqpFa402Vs1CDO4cMFfzpc",
                    "9se0uI8xlYe2BUGEcZezz7pGJO4",
                    "flT49y2Z9zxZ9gQBcoVDMOG2k4i",
                    "P1xEuva9BW3bsRAhKt7qTbOBpZe",
                    "vSDCIt3koUcs_sJG38RLxkrcWl7"
                ],
            "current_map": "$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y #247"
        }
}


class KackyAPIHandler:
    # dict managing servers
    servers = {}

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])

    def get_mapinfo(self):
        self.logger.info("Updating self.servers.")
        try:
            krdata = requests.get("https://kk.kackiestkacky.com/api/").json()
        except ConnectionError:
            self.logger.error("Could not connect to KK API!")
            flask.render_template('error.html',
                                  error="Could not contact KK server. RIP!")
            return
        except json.decoder.JSONDecodeError:
            #self.logger.error("Using TEST_API_RESPONSE")
            # flask.render_template('error.html',
            #                      error="KK API returned strange data. RIP!")
            #krdata = TEST_API_RESPONSE
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

    def get_fin_info(self, tmlogin):
        try:
            findata = requests.post("https://kk.kackiestkacky.com/api/", data={"login": tmlogin}).json()
        except ConnectionError:
            self.logger.error("Could not connect to KK API!")
            flask.render_template('error.html',
                                  error="Could not contact KK server. RIP!")
        return findata

if __name__ == "__main__":
    k = KackyAPIHandler({"logger_name": "bnl"})
    print(k.get_fin_info("amgreborn"))