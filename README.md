# kacky_schedule
Webtool for KK/KR/KX events - Check which maps are currently played and when a map will be played again. Also can calculate, at how long it will be until a map gets queued. Besides a web frontend, this project also features a Discord bot, which allows users to be notified when a specific map comes up.

# Setup
After cloning the project, run ``pip install .`` in the project directory.
This installs all dependencies and sets up two commands ``start_kacky_schedule`` and ``start_kacky_discord_alarm`` which start the backend server or discord bot respectively.
You'll also have to adjust `config.yaml` (general settings), `secrets.yaml` (Well.. secret stuff. Bot/API keys, etc) and `servers.yaml` (Information on servers for current event).

## Development Setup
For developing, please install ``pip install -e .[dev]`` and execute ``pre-commit install`` to set up all commit hooks. They enforce code styles, etc.

# Configuration `config.yaml`
| Config Key | Value          | Description |
|---|----------------|---|
| `port` | int            | Port for the flask server to bind to |
| `bind_host` | int            | IP to bind on. 0.0.0.0 just binds to all |
| `install_dir` | str            | Directory to the cloned repo (relative paths sometimes do not work for some reason..) |
| `cachetime` | int            | How long between querying the KR server for current maps. No need to update on every page load. |
| `mapchangetime_s` | int            | Servers take some time to load the next map. Basically, have to guess this parameter, as load times are quite random... Time in seconds |
| `log_visits` | [0, 1]         | Write a time stamp for every visit of index.html. This does not count searches. |
| `visits_logfile` | str            | Path to a file, where to store the logged visits. Might require an absolute path. |
| `enable_stats_page` | [True, False]  | Enables a simple visitor graph from the data captured if `log_visits` is `True`. Accessible at /stats. This produces extra load on the server, so use wisely |
| `enable_discord_bot` | [True, False]  | Enable/Disable Discord bot |
| `compend` | datetime str   | End-date of KR. German date format (dd/mm/yyyy hh:mm) |
| `min_mapid` | int            | Lowest map id |
| `max_mapid` | int            | Highest map id |
| `logtype` | [STDOUT, FILE] | Where should logging be done to? To `FILE` or `STDOUT` |
| `logfile` | str            | Path to file, if `logtype` is set to `FILE`. Might require absolute path. |
| `loglevel` | str            | Level for Python's `logging` module. Values `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logger_name` | str            | Name to use with `logging` module |
| `testing_mode` | [0, 1]         | Enable/Disable testing mode. Enabling uses hardcoded example API responses. |
| `testing_compend` | datetime str   | Just some date far in the future, so that testing mode always shows data in the frontend |

## Unused keys
These were used once - might be obsolete at this point, not even sure if they are still used - better save (sic!) than sorry.
| Config Key | Description |
|---|---|
| playlist | "linear" for [min_mapid, ... max_mapid] on every server. "custom" for different maps per server (e. g. colors/difficulties) |
| timelimit | int value. Timelimit when `playlist` is set to linear
| jukebox | `True/False`. Jukebox is enabled on servers
| extends | `True/False`. Extends are enabled on servers
| num_extends | int value. Number of possible extends
| `phase1timelimit` | Time limit for every map in first phase of KR. Time in minutes. |
| `phase2start` | Date when second phase starts. German date format (dd/mm/yyyy hh:mm) |
| `phase1timelimit` | Time limit for every map in second phase of KR. Time in minutes. |
