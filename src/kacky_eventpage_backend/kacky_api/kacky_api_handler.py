import json
import logging
from datetime import datetime as dt
from datetime import timedelta as td
from pathlib import Path

import flask
import requests as requests
import yaml

from kacky_eventpage_backend.datastructures.server import ServerInfo
from kacky_eventpage_backend.kacky_api.testing_data import TESTING_DATA
from kacky_eventpage_backend.tm_string.tm_format_resolver import TMstr


class KackyAPIHandler:
    # dict managing servers
    servers = {}
    leaderboard = []
    last_update = {}

    def __init__(self, config: dict):
        """
        Set up interface to Kacky's API.

        Parameters
        ----------
        config: dict
            dict containing information from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])
        try:
            with open(Path(__file__).parents[2] / "secrets.yaml") as b:
                self.api_pwd = yaml.load(b, yaml.FullLoader)["api_pwd"]
        except FileNotFoundError:
            raise FileNotFoundError("Missing secrets.yaml!")

    def _cache_update_required(self, field: str, cachetime: int):
        try:
            # check if last update of `field` is less than `cachetime` seconds old
            if dt.fromtimestamp(self.last_update[field]) < dt.now() + td(seconds=60):
                self.logger.debug(f"'{field}' still valid in cache")
                return 0
        except KeyError:
            # `field` was never accessed before, set up entry in dict
            self.logger.debug(f"Setting up caching for '{field}'")
            self.last_update[field] = dt.now().timestamp()
        finally:
            # catch-all when cache needs update
            self.logger.debug(f"'{field}' needs updating")
            return 1

    def update_server_info(self):
        if self._cache_update_required("serverinfo", 60):
            # update cache
            krdata = self.do_api_request("serverinfo")
        else:
            self.logger.info("Using cached serverinfo")
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

        self.last_server_update = dt.now()

    def get_fin_info(self, tmlogin):
        findata = self.do_api_request({"login": tmlogin, "password": self.api_pwd})
        return findata

    def get_mapinfo(self):
        if (
            any(map(lambda s: s.timeplayed < 0, self.servers.values()))
            or self.servers == {}
        ):
            self.update_server_info()

    def update_leaderboard(self):
        if (
            not self.last_leader_update < dt.now() - td(minutes=10)
            and not self.leaderboard == []
        ):
            # if last update is not older than one minute, use cached data
            self.logger.info("Use cached self.leaderboard.")
            return

        self.logger.info("Updating self.leaderboard.")
        try:
            # TODO: change to actual api
            # krdata = requests.get(
            #                       "https://kk.kackiestkacky.com/api/",
            #                       params={"password": self.api_pwd}
            #          ).json()
            krdata = TESTING_DATA["leaderboard"]
        except ConnectionError:
            self.logger.error("Could not connect to KK API!")
            flask.render_template(
                "error.html", error="Could not contact KK server. RIP!"
            )
            return
        except json.decoder.JSONDecodeError:
            # self.logger.error("Using TEST_API_RESPONSE")
            # krdata = TEST_LEADERBOARD_RESPONSE
            self.logger.error("Could not connect to KK API!")
            flask.render_template(
                "error.html", error="Could not contact KK server. RIP!"
            )
            return

        for idx, _ in enumerate(krdata):
            krdata[idx][1] = TMstr(krdata[idx][1]).html

        self.leaderboard = krdata
        self.last_leader_update = dt.now()

    def get_leaderboard(self):
        self.update_leaderboard()

    def do_api_request(self, value, request_params={}):
        # check for testing mode
        if self.config["testing_mode"]:
            return TESTING_DATA[value]
        self.logger.info("Updating self.servers.")

        # add password to request
        request_params["password"] = self.api_pwd

        try:
            if value == "serverinfo":
                qres = requests.get(
                    "https://kk.kackiestkacky.com/api/",
                    params=request_params,
                ).json()
            elif value == "userfins":
                qres = requests.post(
                    "https://kk.kackiestkacky.com/api/",
                    data=request_params,
                ).json()
            elif value == "leaderboard":
                qres = ""
                raise NotImplementedError
            else:
                raise NotImplementedError(
                    f"API does not support an endpoint for '{value}'"
                )
        except ConnectionError:
            flask.render_template(
                "error.html", error="Could not contact KK server. RIP!"
            )
            return
        except json.decoder.JSONDecodeError:
            flask.render_template("error.html", error="Invalid output from Kacky API!")
            return

        # update cache age
        self.last_update[value] = dt.now().timestamp
        return qres
