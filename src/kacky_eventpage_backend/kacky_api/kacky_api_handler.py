import json
import logging
from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any, Dict

import requests as requests

from kacky_eventpage_backend.datastructures.server import ServerInfo
from kacky_eventpage_backend.kacky_api.testing_data import TESTING_DATA
from kacky_eventpage_backend.tm_string.tm_format_resolver import TMstr


class KackyAPIHandler:
    # dict managing servers
    _serverinfo = {}
    _leaderboard = []
    _last_update = {}

    def __init__(self, config: dict, secrets: dict):
        """
        Set up interface to Kacky's API.

        Parameters
        ----------
        config: dict
            dict containing information from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger(self.config["logger_name"])
        self.api_pwd = secrets["api_pwd"]

    def __getattr__(self, item):
        if item == "serverinfo":
            if self._cache_update_required("serverinfo", 60):
                self._update_server_info()
            return self._serverinfo
        if item == "leaderboard":
            if self._cache_update_required("leaderboard", 600):
                self._update_leaderboard()
            return self._leaderboard

    def _cache_update_required(self, field: str, cachetime: int):
        try:
            # check if last update of `field` is less than `cachetime` seconds old
            if self._last_update[field] > dt.now() - td(seconds=cachetime):
                self.logger.debug(f"'{field}' still valid in cache")
                return 0
            else:
                self.logger.debug(f"'{field}' needs updating")
                return 1
        except KeyError:
            # `field` was never accessed before, set up entry in dict
            self.logger.debug(
                f"Setting up caching for '{field}' and preparing to update"
            )
            self._last_update[field] = dt.fromtimestamp(0)
            return 1

    def _update_server_info(self):
        krdata = self._do_api_request("serverinfo")

        for sid, serverdata in krdata.items():
            self.logger.debug(f"updating server '{sid}'")
            # sanity checking
            if "error" in serverdata:
                self.logger.error(
                    f"updating server '{sid}' - ERROR: {serverdata['error']}"
                )
                continue

            if (
                serverdata["name"] is False
                or serverdata["current_map"] is False
                or serverdata["time_played"] is False
            ):
                self.logger.error(
                    f"updating server '{sid}' - ERROR: a field contained a bad value"
                )
                continue

            self.logger.debug(f"new data: {serverdata}")
            # check for first run
            if serverdata["name"] not in self._serverinfo:
                # this is the first run, need to build objects
                self._serverinfo[serverdata["name"]] = ServerInfo(
                    TMstr(serverdata["name"]), self.config
                )

            # update existing ServerInfo object
            self._serverinfo[serverdata["name"]].update_info(serverdata)

        self._last_update["serverinfo"] = dt.now()

    def get_fin_info(self, tmlogin):
        findata = self._do_api_request(
            "userfins", request_params={"login": tmlogin, "password": self.api_pwd}
        )
        return findata

    def _update_leaderboard(self):
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
            return
        except json.decoder.JSONDecodeError:
            # self.logger.error("Using TEST_API_RESPONSE")
            # krdata = TEST_LEADERBOARD_RESPONSE
            self.logger.error("Could not connect to KK API!")
            return

        for idx, _ in enumerate(krdata):
            krdata[idx][1] = TMstr(krdata[idx][1]).html

        self._leaderboard = krdata
        self._last_update["leaderboard"] = dt.now()

    def _do_api_request(self, value, request_params: Dict[str, Any] = None):
        # check for testing mode
        if request_params is None:
            request_params = {}
        if self.config["testing_mode"]:
            return TESTING_DATA[value]
        self.logger.info(f"Updating {value} from Kacky API.")

        # add password to request
        request_params["password"] = self.api_pwd

        qres = None
        try:
            if value == "serverinfo":
                qres = requests.get(
                    "https://kackiestkacky.com/api/",
                    params=request_params,
                )
            elif value == "userfins":
                qres = requests.post(
                    "https://kackiestkacky.com/api/",
                    data=request_params,
                )
            elif value == "leaderboard":
                qres = ""
                raise NotImplementedError
            else:
                qres = ""
                raise NotImplementedError(
                    f"API does not support an endpoint for '{value}'"
                )
        except ConnectionError as e:
            self.logger.critical(f"Could not connect to Kacky API! {e}")
        except json.decoder.JSONDecodeError as e:
            self.logger.critical(
                f"Response from Kacky API is malformed! {qres.text} - {e}"
            )

        # update cache age
        self._last_update[value] = dt.now()
        return qres.json()
