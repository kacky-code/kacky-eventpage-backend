import datetime
import hashlib
import json
import logging
import os
from pathlib import Path

import flask
import flask_restful
import yaml
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
)

from kacky_eventpage_backend.kacky_api.kacky_api_handler import KackyAPIHandler
from kacky_eventpage_backend.usermanagement.token_blacklist import TokenBlacklist
from kacky_eventpage_backend.usermanagement.user_operations import UserDataMngr
from kacky_eventpage_backend.usermanagement.user_session_handler import User

app = flask.Flask(__name__)
jwt = JWTManager(app)
config = {}


def get_pagedata(rawservernum=False):
    """
    Loads and prepares data shown on index page

    # Get page data
    serverinfo, curtimestr, timeleft = get_pagedata()

    Parameters
    ----------
    rawservernum:
        Toggle on server ID format

    Returns
    -------
    Tuple[list, list, list]
        Information for the index page.
    """
    curtime = datetime.datetime.now()
    curtimestr = f"{curtime.hour:0>2d}:{curtime.minute:0>2d}"
    curmaps = list(map(lambda s: s.cur_map, api.serverinfo.values()))
    if config["testing_mode"]:
        ttl = (
            datetime.datetime.strptime(config["testing_compend"], "%d.%m.%Y %H:%M")
            - curtime
        )
    else:
        ttl = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M") - curtime
    if ttl.days < 0 or ttl.seconds < 0:
        timeleft = (
            abs(ttl.days),
            abs(int(ttl.seconds // 3600)),
            abs(int(ttl.seconds // 60) % 60),
            -1,
        )
    else:
        timeleft = (
            abs(ttl.days),
            abs(int(ttl.seconds // 3600)),
            abs(int(ttl.seconds // 60) % 60),
            1,
        )
    if rawservernum:
        servernames = list(
            map(lambda s: s.name.string.split(" - ")[1], api.serverinfo.values())
        )
    else:
        servernames = list(map(lambda s: s.name.html, api.serverinfo.values()))
    timeplayed = list(map(lambda s: s.timeplayed, api.serverinfo.values()))
    jukebox = list(
        map(lambda s: s.playlist.get_playlist_from_now(), api.serverinfo.values())
    )
    timelimits = list(map(lambda s: s.timelimit, api.serverinfo.values()))
    serverinfo = list(zip(servernames, curmaps, timeplayed, jukebox, timelimits))
    return serverinfo, curtimestr, timeleft

    """
    api.get_mapinfo()
    # input seems ok, try to find next time map is played
    deltas = list(map(lambda s: s.find_next_play(search_map_id),
                      api.serverinfo.values()))
    # remove all None from servers which do not have map
    deltas = [i for i in deltas if i[0]]

    """


@app.route("/register", methods=["POST"])
def register_user():
    # curl -d "reg_usr=peter&reg_mail=peter&reg_pwd=peter"
    # -X POST http://localhost:5000/register
    udm = UserDataMngr(config, secrets)
    cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
    cryptmail = hashlib.sha256(flask.request.json["mail"].encode()).hexdigest()
    res = udm.add_user(flask.request.json["user"], cryptpw, cryptmail)
    if res:
        return flask_restful.http_status_message(201)
    else:
        return flask_restful.http_status_message(409)


@app.route("/login", methods=["POST"])
def login_user_api():
    # curl -d '{"login_usr":"asd", "login_pwd":"asd"}'
    # -H "Content-Type: application/json" -X POST http://localhost:5000/login
    assert flask.request.json["user"]
    assert flask.request.json["pwd"]
    user = User(flask.request.json["user"], config, secrets).exists()

    if not user or not user.login(flask.request.json["pwd"]):
        return flask.jsonify("Wrong username or password"), 401

    # user wants to login
    # cryptpw = hashlib.sha256(flask.request.json["login_pwd"].encode()).hexdigest()
    # login_success = user.login(cryptpw)
    login_success = user.login(flask.request.json["pwd"])

    if login_success:
        access_token = create_access_token(identity=user)
        return flask.jsonify(access_token=access_token), 200

    return flask_restful.http_status_message(401)


@app.route("/logout")
@jwt_required()
def logout_and_redirect_index():
    """
    Logs out the user

    Returns
    -------
    flask.Response
        Redirect to the index page after logging out
    """
    TokenBlacklist(config, secrets).blacklist_token(get_jwt()["jti"])
    return flask_restful.http_status_message(200)


@app.route("/data.json")
def json_serverdata_provider():
    """
    "API" used by front end JS. Provides updated server information in JSON format.

    Returns
    -------
    str
        Data in JSON format as a string
    """
    serverinfo, curtimestr, timeleft = get_pagedata(rawservernum=True)
    jsonifythis = {}
    for elem in serverinfo:
        if "serverinfo" in jsonifythis:
            jsonifythis["serverinfo"].append({elem[0]: elem[1:]})
        else:
            jsonifythis["serverinfo"] = [{elem[0]: elem[1:]}]
    jsonifythis["timeleft"] = timeleft
    jsonifythis["curtimestr"] = curtimestr
    return json.dumps(jsonifythis)


@app.route("/fin.json", methods=["POST"])
@jwt_required()
def build_fin_json():
    # XOR only one parameter is set
    assert (flask.request.json["tm_login"] and not flask.request.json["username"]) or (
        flask.request.json["username"] and not flask.request.json["tm_login"]
    )
    if flask.request.json["username"]:
        um = UserDataMngr(config, secrets)
        tm_login = um.get_tm20_login(flask.request.json["username"])
    try:
        if tm_login != "":
            fins = api.get_fin_info(tm_login)["finishes"]
            mapids = list(map(lambda m: int(m), api.get_fin_info(tm_login)["mapids"]))
            return {"finishes": fins, "mapids": mapids}
        else:
            return {"finishes": 0, "mapids": []}
    except Exception:
        return {"finishes": 0, "mapids": []}


@app.route("/who_am_i", methods=["GET"])
@jwt_required()
def protected():
    return flask.jsonify(name=current_user.username, id=current_user.get_id())


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    return TokenBlacklist(config, secrets).check_token(jti)


@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.username


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    username = jwt_data["sub"]
    return User(username, config, secrets).exists()


#                    _
#                   (_)
#    _ __ ___   __ _ _ _ __
#   | '_ ` _ \ / _` | | '_ \
#   | | | | | | (_| | | | | |
#   |_| |_| |_|\__,_|_|_| |_|
#
# Reading config file
with open(Path(__file__).parents[2] / "config.yaml", "r") as conffile:
    config = yaml.load(conffile, Loader=yaml.FullLoader)

# Read flask secret (required for flask.flash and flask_login)
with open(Path(__file__).parents[2] / "secrets.yaml", "r") as secfile:
    secrets = yaml.load(secfile, Loader=yaml.FullLoader)
    app.secret_key = secrets["flask_secret"]
    app.config["JWT_SECRET_KEY"] = secrets["jwt_secret"]

MAPIDS = (config["min_mapid"], config["max_mapid"])

if config["logtype"] == "STDOUT":
    pass
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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

api = KackyAPIHandler(config, secrets)

# Set up logging
logger = logging.getLogger(config["logger_name"])
logger.setLevel(eval("logging." + config["loglevel"]))

if config["log_visits"]:
    # Enable logging of visitors to dedicated file. More comfortable than using system
    # log to count visitors.
    # Counting with "cat visits.log | wc -l"
    f = open(os.path.join(os.path.dirname(__file__), config["visits_logfile"]), "a+")
    f.close()

# Set up JWT
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(
    days=100
)  # Why 100? idk, looks cool

logger.info("Starting application.")
# app.run(debug=True, host=config["bind_hosts"], port=config["port"])
app.run(host=config["bind_hosts"], port=config["port"])
