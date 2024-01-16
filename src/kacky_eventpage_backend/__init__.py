import logging
import os
import sys

import yaml

if sys.version_info[:2] >= (3, 8):
    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

config_file = os.environ['CONFIG_FILE'] if os.environ.get('CONFIG_FILE') else "config.yaml"
secrets_file = os.environ['SECRETS_FILE'] if os.environ.get('SECRETS_FILE') else "secrets.yaml"
servers_file = os.environ['SERVERS_FILE'] if os.environ.get('SERVERS_FILE') else "servers.yaml"

# Reading config file
with open(config_file, "r") as conffile:
    config = yaml.load(conffile, Loader=yaml.FullLoader)

# Read flask secret (required for flask.flash and flask_login)
with open(secrets_file, "r") as secfile:
    secrets = yaml.load(secfile, Loader=yaml.FullLoader)

if config["logtype"] == "STDOUT":
    pass
    logging.basicConfig(format="%(name)s - %(levelname)s - %(message)s")
# YES, this totally ignores threadsafety. On the other hand, it is quite safe to assume
# that it only will occur very rarely that things get logged at the same time in this
# usecase. Furthermore, logging is absolutely not critical in this case and mostly used
# for debugging. As long as the
# SQLite DB doesn't break, we're safe!
elif config["logtype"] == "FILE":
    config["logfile"] = config["logfile"].replace("~", os.getenv("HOME"))
    if not os.path.dirname(config["logfile"]) == "" and not os.path.exists(
        os.path.dirname(config["logfile"])
    ):
        os.mkdir(os.path.dirname(config["logfile"]))
    f = open(os.path.join(os.path.dirname(__file__), config["logfile"]), "w+")
    f.close()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=config["logfile"],
    )
else:
    print("ERROR: Logging not correctly configured!")
    exit(1)