import datetime
import logging
from typing import Dict, List, Union

# from kacky_eventpage_backend.db_ops.db_operator import MiscDBOperators


class PlaylistHandler:
    playlist = []
    original_list = []

    def __init__(
        self, config: Dict[str, Union[str, list, int]], playlist: List[int] = None
    ):
        if playlist is None:
            # mapids = MiscDBOperators(config, secrets).get_map_kackyIDs_for_event(
            #     config["eventtype"], config["edition"]
            # )
            mapids = [-151, -200]
            self.playlist = list(range(min(mapids), max(mapids) + 1))
            # make a copy
            self.original_list = self.playlist[:]
        else:
            self.playlist = playlist
            # make a copy
            self.original_list = self.playlist[:]
        self.curmap = self.playlist[0]
        self.last_update = datetime.datetime.now()
        self.playtime_curmap = 0
        self.logger = logging.getLogger(config["logger_name"])

    def reset(self):
        self.playlist = self.original_list

    def set_current_map(self, mid: int, playtime: int):
        self.curmap = mid
        self.playtime_curmap = playtime
        self.last_update = datetime.datetime.now()

    def get_next_play(self, search_id: int, timelimit: int):
        if search_id not in self.playlist:
            return None
        # how many map changes are needed until map is juked?
        pos_in_list_current_map = self.playlist.index(self.curmap)
        pos_in_list_search_map = self.playlist.index(search_id)
        changes_needed = (pos_in_list_search_map - pos_in_list_current_map) % len(
            self.playlist
        )
        # if changes_needed < 0:
        #     changes_needed += self.original_list[-1] - self.original_list[0] + 1
        minutes_time_to_juke = int(changes_needed * timelimit)
        already_played_time = self.playtime_curmap + int(
            (datetime.datetime.now() - self.last_update).seconds
        )
        # self.logger.info(f"search {search_id}, changes {changes_needed}. in {minutes_time_to_juke}, played
        # {already_played_time} => {minutes_time_to_juke - int(already_played_time / 60)}")
        minutes_time_to_juke -= int(already_played_time / 60)
        # date and time, when map is juked next (without compensation of minutes)
        # play_time = datetime.datetime.now() + datetime.timedelta(
        #     minutes=minutes_time_to_juke
        # )
        return self._minutes_to_hourmin_str(
            minutes_time_to_juke if minutes_time_to_juke >= 0 else 0
        )

    def _minutes_to_hourmin_str(self, minutes):
        minutes = int(minutes)
        # return Tuple[str, str] # (hours, minutes)
        return f"{int(minutes / 60):0>2d}", f"{minutes % 60:0>2d}"

    def get_playlist_from_now(self):
        current_pos = self.playlist.index(self.curmap)
        # This only needs 4 maps, current one and three for preview
        return (self.playlist[current_pos:] + self.playlist[: current_pos + 4])[:4]
