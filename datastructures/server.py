import yaml

from datastructures.playlist import PlaylistHandler
from tm_format_resolver import TMstr


class ServerInfo:
    def __init__(self, name: TMstr, config: dict, color: str = ""):
        self.name = name
        self.color = color
        self.config = config
        # assume server number is last part of the string
        self.id = self.name.string.split(" ")[-1]

        if self.config["playlist"] == "custom":
            with open("maps.yaml") as mf:
                maplist = yaml.load(mf, Loader=yaml.FullLoader)
            self.playlist = PlaylistHandler(config, maplist[name.string])
        else:
            self.playlist = PlaylistHandler(config)

    def update_info(self, new_info: dict):
        self.jukebox = new_info["jukebox"]
        self.cur_map_name = new_info["current_map"]
        self.cur_map = int(new_info["current_map"].split("#")[-1])
        self.recent = new_info["recently_played"]

        # if recent maps are empty, server must have restarted. Reset playlist order
        if not self.recent:
            self.playlist.reset()
