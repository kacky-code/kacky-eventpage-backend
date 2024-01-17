# kacky_schedule
Webtool for KK/KR/KX events - Check which maps are currently played and when a map will be played again. Also can calculate, at how long it will be until a map gets queued. Besides a web frontend, this project also features a Discord bot, which allows users to be notified when a specific map comes up.

# Setup
After cloning the project, run ``pip install .`` in the project directory.
This installs all dependencies and sets up two commands ``start_kacky_schedule`` and ``start_kacky_discord_alarm`` which start the backend server or discord bot respectively.
You'll also have to adjust `config.yaml` (general settings), `secrets.yaml` (Well.. secret stuff. Bot/API keys, etc) and `servers.yaml` (Information on servers for current event).

## Development Setup
For developing, please install ``pip install -e .[dev]`` and execute ``pre-commit install`` to set up all commit hooks. They enforce code styles, etc.

# Configuration `config.yaml`
## Required
| Config Key    | Value              | Description                                                                                  |
|---------------|--------------------|----------------------------------------------------------------------------------------------|
| `port`        | int                | Port for the flask server.                                                                   |
| `bind_host`   | int                | IP to bind on. 0.0.0.0 binds all (use with Docker).                                          |
| `workers`     | int                | Number of Gunicorn workers. Recommended: `(2 x $num_cores) + 1`.                             |
| `threads`     | int                | Number of threads within each worker. Assumes worker `gthread`.                              |
| `comstart`    | ISO8601 datetime   | Start-date of event. ISO8601.                                                                |
| `compend`     | ISO8601 datetime   | End-date of event. ISO8601.                                                                  |
| `eventtype`   | str                | Type of currently running event.                                                             |
| `edition`     | int                | Edition of currently running event.                                                          |
| `logtype`     | (`STDOUT`, `FILE`) | Where should logging be done to? To `FILE` or `STDOUT`.                                      |
| `loglevel`    | str                | Level for Python's `logging` module. Values `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `logger_name` | str                | Name to use with `logging` module.                                                           |
| `dbhost`      | str                | IP/address/service of MySQL/MariaDB database for the backend.                                |
| `dbport`      | int                | Port of MySQL/MariaDB database for the backend.                                              |


## Optional (May be required in combination with required a key)
| Config Key          | Value                | Description                                                                                                   |
|---------------------|----------------------|---------------------------------------------------------------------------------------------------------------|
| `playlist`          | (`linear`, `custom`) | `custom` uses `servers.yaml` for playlist and server info. `linear` may be broken, wasn't used in a long time |
| `timelimit`         | int                  | Required with `playlist` type `linear`. Sets the length of playtime on each server                            |
| `logfile`           | str                  | Path to file, if `logtype` is set to `FILE`. Do not use a relative path.                                      |
| `testing_mode`      | `(0, 1)`             | Enable/Disable testing mode. Enabling uses hardcoded example API responses.                                   |
| `testing_compstart` | datetime str         | Start-date for a simulated active event.                                                                      |
| `testing_compend`   | datetime str         | End-date for a simulated active event.                                                                        |
