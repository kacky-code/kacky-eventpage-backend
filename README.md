# Hunting Event - Website Backend
Backend for [Hunting Event - Website Frontend](https://github.com/kacky-code/kacky-eventpage-frontend).

# Setup
The project has three user configurable files. `config.yaml` for general application parameters, `secrets.yaml` for secrets and passwords and `servers.yaml` to configure servers running in the event.
Either place them in the repository's root directory or set them with the following environment variables:

| Variable     | Value                 |
|--------------|-----------------------|
| CONFIG_FILE  | /path/to/config.yaml  |
| SECRETS_FILE | /path/to/secrets.yaml |
| SERVERS_FILE | /path/to/servers.yaml |

The project uses Gunicorn as it's WSGI HTTP Server.

Minimum required setup is creating a `secrets.yaml` (refer to `secrets.yaml.template`) and filling its fields.
Setting `compstart` and `compend` in `config.yaml` so currently no event is running allows only setting `db*` fields in `config.yaml` and `secrets.yaml`, and produces a working environment with some minor features not working.

## Development Setup
For developing, please install the development modules (e.g. ``pip install -e .[dev]``) and execute ``pre-commit install`` to set up all commit hooks. They enforce code styles, etc. on committing.
`docker compose up` in the repo's root will set up a database with Kacky Events KK1-9 and KR1-4.

# General Configuration `config.yaml`
## Required
| Config Key    | Value              | Description                                                                                  |
|---------------|--------------------|----------------------------------------------------------------------------------------------|
| `port`        | int                | Port for the flask server.                                                                   |
| `bind_host`   | int                | IP to bind on. 0.0.0.0 binds all (use with Docker).                                          |
| `workers`     | int                | Number of Gunicorn workers. Recommended: `(2 x $num_cores) + 1`.                             |
| `threads`     | int                | Number of threads within each worker. Assumes worker `gthread`.                              |
| `compstart`   | ISO8601 datetime   | Start-date of event. ISO8601.                                                                |
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

# Secrets file `secrets.yaml`
## Required
| Key                | Value | Description                                                                        |
|--------------------|-------|------------------------------------------------------------------------------------|
| `api_pwd`          | str   | Password to get state information from the game servers.                           |
| `flask_secret`     | str   | Salted secret for Flask. May not be used anymore, since flask-flash is not in use. |
| `jwt_secret`       | str   | Secret for JWT                                                                     |
| `sendgrid_api_key` | str   | API key for Sendgrid. Required to reset user passwords.                            |
| `dbuser`           | str   | Username for the MySQL/MariaDB instance used with the backend.                     |
| `dbpwd`            | str   | Password for the MySQL/MariaDB instance used with the backend.                     |
| `records_api_key`  | str   | API key for records.api.gg. Valid key allows unlimited requests.                   |

## Optional
| Key            | Value | Description                                                                          |
|----------------|-------|--------------------------------------------------------------------------------------|
| `msg_send_pwd` | str   | Password to send messages to streamer dashboard (/post, /target, /stream endpoints). |

# Server Information `servers.yaml` (Used with `playlist: custom`)
Each server must be defined as follows:
```yaml
Full Server Name:
  server_number: int      # Identifier if multiple servers have the same difficulty (e.g. 1 or 2 with servers "White *1*" and "White *2*")
  difficulty: (str, int)  # Difficulty identifier [("white", "blue", ...), ("easy", "medium", ...), ...]. Must match frontend.
  timelimit: int          # Playtime for each map on the server.
  server_login: str       # Trackmania login of the account. Only relevant for TMNF.
  maps: list[int]         # Ordered list of maps played in the server
```
Multiple servers can be defined in the file on root level.
`Full Server Name` must match the name as returned from Gameserver API (Readable text only without TM formatting syntax) since it's used as a key for mapping between its response and servers.yaml

## Example:
````yaml
Kacky Reloaded 4 - White 1:
  server_number: 1
  difficulty: white
  timelimit: 15
  server_login: ""
  maps:
    - 228
    - 238
    - 240
    - 241
    - 242
    - 245
    - 246
    - 256
    - 258
````
