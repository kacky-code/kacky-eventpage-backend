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


class APIHandler:
    servers = {}

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])

    def get_mapinfo(self):
        # Update self.servers every minute
        if self.servers != {}:
            if datetime.datetime.now() - list(self.self.servers.values())[0]["update"] < datetime.timedelta(
                    seconds=self.config["cachetime"]):
                # Return if data is not old enough yet
                self.logger.info("No update for self.servers needed!")
                return
        self.logger.info("Updating self.servers.")
        try:
            krdata = requests.get(
                "https://kacky.koyaanis.com/api/").json()
        except ConnectionError:
            self.logger.error("Could not connect to KR API!")
            #flask.render_template('../kk_schedule/templates/error.html',
            #                      error="Could not contact KR server. RIP!")
        except json.decoder.JSONDecodeError:
            self.logger.error("Using TEST_API_RESPONSE")
            krdata = TEST_API_RESPONSE
        tmpdict = {}
        res = []
        for server in krdata.keys():
            d = krdata[server]
            serverinfo = ServerInfo(TMstr(server), self.config, d.get("color", ""))
            serverinfo.update_info(d)

            mapid = int(TMstr(d["current_map"]).string.split("#")[1])
            servername_tmstr = TMstr(server)
            serverid = int(servername_tmstr.string[-1:])
            servname = servername_tmstr.html
            tmpdict[serverid] = {
                "name": servname,
                "mapid": mapid,
                "update": datetime.datetime.now()
            }
            res.append(serverinfo)
        #self.servers = tmpdict.copy()
        self.servers = res
