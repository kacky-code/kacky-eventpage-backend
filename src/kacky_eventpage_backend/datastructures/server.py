import datetime
from pathlib import Path

import yaml

from kacky_eventpage_backend.datastructures.playlist import PlaylistHandler
from kacky_eventpage_backend.tm_string.tm_format_resolver import TMstr


class ServerInfo:
    def __init__(self, name: TMstr, config: dict):
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

    def update_info(self, new_info: dict):
        self.jukebox = new_info["jukebox"]
        self.cur_map_name = new_info["current_map"]
        self.cur_map = int(new_info["current_map"].split("#")[-1].split(" ")[0])
        self.recent = new_info["recently_played"]
        self.last_update = datetime.datetime.now()
        self.timeplayed_internal = int(new_info["time_played"])

        # if recent maps are empty, server must have restarted. Reset playlist order
        if not self.recent:
            self.playlist.reset()
        self.playlist.set_current_map(self.cur_map, self.timeplayed_internal)

    def find_next_play(self, searchid: int):
        return self.playlist.get_next_play(searchid, self.timelimit), self.servernum

    @property
    def timeplayed(self):
        return int(
            (datetime.datetime.now() - self.last_update).total_seconds()
            + self.timeplayed_internal
        )
