from typing import List


class PlaylistHandler:
    playlist = []
    original_list = []

    def __init__(self, config, playlist: List[int] = None):
        if playlist is None:
            self.playlist = list(range(config["min_mapid"], config["max_mapid"] + 1))
            # make a copy
            self.original_list = self.playlist[:]
        else:
            self.playlist = playlist
            # make a copy
            self.original_list = self.playlist[:]

    def reset(self):
        self.playlist = self.original_list
