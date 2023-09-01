import datetime
import logging
from pathlib import Path

import yaml

# from kacky_eventpage_backend.tm_string.tm_format_resolver import TMstr
from tmformatresolver import TMString

from kacky_eventpage_backend.datastructures.playlist import PlaylistHandler


class ServerInfo:
    def __init__(self, name: TMString, config: dict):
        self.name = name
        self.config = config
        # assume server number is last part of the string
        self.id = self.name.string.split(" ")[-1]

        if self.config["playlist"] == "custom":
            with open(Path(__file__).parents[3] / "servers.yaml") as mf:
                server_conf = yaml.load(mf, Loader=yaml.FullLoader)
            self.playlist = PlaylistHandler(config, server_conf[name.string]["maps"])
            self.servernum = server_conf[name.string]["server_number"]
            self.difficulty = server_conf[name.string]["difficulty"]
            self.serverlogin = server_conf[name.string].get("serverlogin", None)
        else:
            self.playlist = PlaylistHandler(config)

        self.last_update = datetime.datetime.fromtimestamp(0)
        self.timelimit = server_conf[name.string]["timelimit"]
        self.logger = logging.getLogger(config["logger_name"])

    def update_info(self, new_info: dict):
        self.jukebox = new_info["jukebox"]
        self.cur_map_name = new_info["current_map"].replace("\u2013", "-")
        self.cur_map = int(
            new_info["current_map"].split("#")[-1].split(" ")[0].replace("\u2013", "-")
        )
        self.recent = new_info["recently_played"]
        self.last_update = datetime.datetime.now()
        try:
            self.timeplayed_internal = int(new_info["time_played"])
        except ValueError:
            self.timeplayed_internal = 0

        # if recent maps are empty, server must have restarted. Reset playlist order
        if not self.recent:
            self.playlist.reset()
        self.playlist.set_current_map(self.cur_map, self.timeplayed_internal)

    def find_next_play(self, searchid: int):
        self.logger.debug(f"find_next_play, {searchid}")
        self.logger.debug(
            (self.playlist.get_next_play(searchid, self.timelimit), self.servernum)
        )
        return self.playlist.get_next_play(searchid, self.timelimit), self.servernum

    @property
    def timeplayed(self):
        return int(
            (datetime.datetime.now() - self.last_update).total_seconds()
            + self.timeplayed_internal
        )
