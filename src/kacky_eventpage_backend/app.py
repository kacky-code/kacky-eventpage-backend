import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Tuple

import flask
import flask_restful
import yaml
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
)

from kacky_eventpage_backend.db_ops.db_operator import MiscDBOperators
from kacky_eventpage_backend.kacky_api.kacky_api_handler import KackyAPIHandler
from kacky_eventpage_backend.usermanagement.token_blacklist import TokenBlacklist
from kacky_eventpage_backend.usermanagement.user_operations import UserDataMngr
from kacky_eventpage_backend.usermanagement.user_session_handler import User

app = flask.Flask(__name__)
jwt = JWTManager(app)
config = {}
CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"


def get_pagedata():
    curtime = datetime.datetime.now()
    if config["testing_mode"]:
        ttl = (
            datetime.datetime.strptime(config["testing_compend"], "%d.%m.%Y %H:%M")
            - curtime
        )
    else:
        ttl = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M") - curtime
    timeleft = ttl.seconds

    response = {"servers": [], "comptimeLeft": timeleft}

    mdb = MiscDBOperators(config, secrets)
    fins = build_fin_json()

    for name, val in api.serverinfo.items():
        tmpdict = {}
        tmpdict["serverNumber"] = val.servernum
        tmpdict["serverDifficulty"] = val.difficulty
        tmpdict["maps"] = []
        for m in val.playlist.get_playlist_from_now():
            mapdict = {
                "number": m,
                "author": mdb.get_map_author(m),
                "finished": (m in fins["mapids"]),
            }
            tmpdict["maps"].append(mapdict)
        tmpdict["timeLimit"] = val.timelimit
        timeleft = val.timelimit * 60 - val.timeplayed
        tmpdict["timeLeft"] = timeleft if timeleft > 0 else 0
        response["servers"].append(tmpdict)
    return response


@app.route("/register", methods=["POST"])
def register_user():
    # curl -d "user=peter&mail=peter&pwd=peter"
    # -X POST http://localhost:5000/register
    log_access("/register - POST", bool(current_user))
    assert not is_invalid(flask.request.json["user"], str, length=80)
    assert not is_invalid(flask.request.json["pwd"], str, length=80)
    assert not is_invalid(flask.request.json["mail"], str, length=80)

    udm = UserDataMngr(config, secrets)
    cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
    cryptmail = hashlib.sha256(flask.request.json["mail"].encode()).hexdigest()
    res = udm.add_user(flask.request.json["user"], cryptpw, cryptmail)
    if res:
        return flask.jsonify(flask_restful.http_status_message(201)), 201
    else:
        return flask.jsonify(flask_restful.http_status_message(409)), 409


@app.route("/login", methods=["POST"])
def login_user_api():
    # curl -d '{"user":"asd",
    # "pwd":"688787d8ff144c502c7f5cffaafe2cc588d86079f9de88304c26b0cb99ce91c6"}'
    # -H "Content-Type: application/json" -X POST http://localhost:5000/login
    log_access("/login - POST", bool(current_user))
    assert not is_invalid(flask.request.json["user"], str, length=80)
    assert not is_invalid(flask.request.json["pwd"], str, length=80)
    user = User(flask.request.json["user"], config, secrets).exists()

    if not user:
        return flask.jsonify("Wrong username or password"), 401

    # user wants to login
    cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
    login_success = user.login(cryptpw)
    # login_success = user.login(flask.request.json["pwd"])

    if login_success:
        access_token = create_access_token(identity=user)
        expires = datetime.datetime.now() + datetime.timedelta(days=100)
        return (
            flask.jsonify(access_token=access_token, expires=expires.timestamp()),
            200,
        )

    return flask.jsonify(flask_restful.http_status_message(401)), 401


@app.route("/usermgnt", methods=["POST"])
@jwt_required()
def usermanagement():
    log_access("/usermgnt - POST", bool(current_user))
    um = UserDataMngr(config, secrets)
    if flask.request.json.get("tmnf", None) is not None:
        if is_invalid(flask.request.json["tmnf"], str, length=50):
            return return_bad_value("tmnf login")
        um.set_tmnf_login(current_user.get_id(), flask.request.json["tmnf"])
    if flask.request.json.get("tm20", None) is not None:
        if is_invalid(flask.request.json["tm20"], str, length=50):
            return return_bad_value("tm20 login")
        um.set_tm20_login(current_user.get_id(), flask.request.json["tm20"])
    if flask.request.json.get("discord", None) is not None:
        if is_invalid(flask.request.json["discord"], str, length=80):
            return return_bad_value("discord handle")
        um.set_discord_id(current_user.get_id(), flask.request.json["discord"])
    if flask.request.json.get("pwd", None) is not None:
        if is_invalid(flask.request.json["pwd"], str, length=80):
            return return_bad_value("pwd")
        cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
        um.set_password(current_user.get_id(), cryptpw)
    if flask.request.json.get("mail", None) is not None:
        if is_invalid(flask.request.json["mail"], str, length=80):
            return return_bad_value("mail")
        cryptmail = hashlib.sha256(flask.request.json["mail"].encode()).hexdigest()
        um.set_mail(current_user.get_id(), cryptmail)
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/usermgnt", methods=["GET"])
@jwt_required()
def get_user_data():
    log_access("/usermgnt - GET", bool(current_user))
    um = UserDataMngr(config, secrets)
    userid = current_user.get_id()
    tmnf = um.get_tmnf_login(userid)
    tm20 = um.get_tm20_login(userid)
    discord = um.get_discord_id(userid)
    return flask.jsonify({"tmnf": tmnf, "tm20": tm20, "discord": discord}), 200


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
    #    assert not is_invalid(get_jwt()["jti"], str, length=36)
    #    pattern = re.compile(r"[0-9a-z]{8}-(?:[0-9a-z]{4}-){3}[0-9a-z]{12}")
    #    assert pattern.match(get_jwt()["jti"])
    log_access("/logout", bool(current_user))
    TokenBlacklist(config, secrets).blacklist_token(get_jwt()["jti"])
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/dashboard")
@jwt_required(optional=True)
def json_serverdata_provider():
    """
    "API" used by front end JS. Provides updated server information in JSON format.

    Returns
    -------
    str
        Data in JSON format as a string
    """
    log_access("/dashboard", bool(current_user))
    serverinfo = get_pagedata()
    return json.dumps(serverinfo), 200


@app.route("/fin")
@jwt_required(optional=True)
def build_fin_json():
    log_access("/fin - GET", bool(current_user))
    if not current_user:  # User is not logged in
        return {"finishes": 0, "mapids": []}
    um = UserDataMngr(config, secrets)
    if config["eventtype"] == "KK":
        tm_login = um.get_tmnf_login(current_user.get_id())
    elif config["eventtype"] == "KR":
        tm_login = um.get_tm20_login(current_user.get_id())
    try:
        if tm_login != "":
            fins = api.get_fin_info(tm_login)["finishes"]
            mapids = list(map(lambda m: int(m), api.get_fin_info(tm_login)["mapids"]))
            return {"finishes": fins, "mapids": mapids}
        else:
            return {"finishes": 0, "mapids": []}
    except Exception:
        return {"finishes": 0, "mapids": []}


@app.route("/spreadsheet/<eventtype>", methods=["POST"])
@jwt_required()
def spreadsheet_update(eventtype: str):
    log_access(f"/spreadsheet/{eventtype} - POST", bool(current_user))
    # mapid is required, represents main key for updating stuff
    try:
        logger.info(flask.request.json)
        assert isinstance(flask.request.json["mapid"], str)
        # assert MAPIDS[0] <= int(flask.request.json["mapid"].split(" ")[0]) <= MAPIDS[1]
        check_event_edition_legal(eventtype, "1")
    except AssertionError:
        return "Error: bad path", 404

    um = UserDataMngr(config, secrets)

    if flask.request.json.get("diff", None) is not None:
        # lazy eval should make sure this is an int in or case
        if is_invalid(flask.request.json["diff"], int, vrange=(0, 6)):
            return return_bad_value("map difficulty")
        um.set_map_difficulty(
            current_user.get_id(),
            flask.request.json["mapid"],
            flask.request.json["diff"],
            eventtype,
        )
    if flask.request.json.get("clip", None) is not None:
        if is_invalid(flask.request.json["clip"], str, length=150):
            return return_bad_value("clip")
        um.set_map_clip(
            current_user.get_id(),
            flask.request.json["mapid"],
            flask.request.json["clip"],
            eventtype,
        )
    if flask.request.json.get("alarm", None) is not None:
        # lazy eval should make sure this is an int in or case
        if is_invalid(flask.request.json["alarm"], int, vrange=MAPIDS):
            return return_bad_value("discord alarm toggle")
        um.toggle_discord_alarm(
            current_user.get_id(), flask.request.json["mapid"], eventtype
        )

    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/spreadsheet", methods=["GET"])
@jwt_required(optional=True)
def spreadsheet_current_event():
    log_access("/spreadsheet - GET", bool(current_user))
    # curl -H 'Accept: application/json' -H "Authorization: Bearer JWTKEYHERE"
    # http://localhost:5005/spreadsheet
    um = UserDataMngr(config, secrets)
    # Check if user is logged in.
    if not current_user:  # User not logged in
        # Only provide base data
        sheet = um.get_spreadsheet_event(None, config["eventtype"], config["edition"])
    else:  # User logged in
        # Add user specific data to the spreadsheet
        userid = current_user.get_id()
        sheet = um.get_spreadsheet_event(userid, config["eventtype"], config["edition"])
        # finned = build_fin_json()
        # for fin in finned["mapids"]:
        #    sheet[fin]["finished"] = True

    # add next play times for each map, regardless of login state
    serverinfo = api.serverinfo.values()
    for mapid, dataset in sheet.items():
        if config["testing_mode"]:
            dataset["upcomingIn"] = 1 * 60 + 1
            dataset["server"] = "TestServer XYZ"
        else:
            # api.get_mapinfo()
            # input seems ok, try to find next time map is played
            deltas = list(map(lambda s: s.find_next_play(int(mapid)), serverinfo))
            # remove all None from servers which do not have map
            deltas = [i for i in deltas if i[0]]
            # check if we need to find the earliest play, if map is on multiple servers
            earliest = deltas[0]
            # check if we need to find the earliest play, if map is on multiple servers
            if len(deltas) > 1:
                for d in deltas[1:]:
                    if int(earliest[0][0]) * 60 + int(earliest[0][1]) >= int(
                        d[0][0]
                    ) * 60 + int(d[0][1]):
                        earliest = d
            dataset["upcomingIn"] = int(earliest[0][0]) * 60 + int(earliest[0][1])
            dataset["server"] = earliest[1]
    sheet = dict(sorted(sheet.items()))
    return json.dumps(list(sheet.values())), 200


@app.route("/spreadsheet/<event>/<edition>", methods=["GET"])
@jwt_required(optional=True)
def spreadsheet_hunting(event, edition):
    log_access(f"/spreadsheet/{event}/{edition} - GET", bool(current_user))
    try:
        check_event_edition_legal(event, edition)
    except AssertionError:
        return "Error: bad path", 404

    # curl -H 'Accept: application/json' -H "Authorization: Bearer JWTKEYHERE"
    # http://localhost:5005/spreadsheet
    um = UserDataMngr(config, secrets)
    # Check if user is logged in.
    if not current_user:  # User not logged in
        # Only provide base data
        sheet = um.get_spreadsheet_event(None, event, edition)
    else:  # User logged in
        # Add user specific data to the spreadsheet
        userid = current_user.get_id()
        sheet = um.get_spreadsheet_event(userid, event, edition)
        # finned = build_fin_json()
        # for fin in finned["mapids"]:
        #    sheet[fin]["finished"] = True

    # sheet = dict(sorted(sheet.items()))
    return json.dumps(list(sheet.values())), 200


@app.route("/eventstatus")
def event_status():
    log_access("/eventstatus - GET", None)
    if config["testing_mode"]:
        compend = datetime.datetime.strptime(
            config["testing_compend"], "%d.%m.%Y %H:%M"
        )
    else:
        compend = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M")
    if datetime.datetime.now() < compend:
        return json.dumps(
            {
                "status": "active",
                "type": config["eventtype"],
                "edition": config["edition"],
            }
        )
    elif datetime.datetime.now() < compend + datetime.timedelta(days=30):
        return json.dumps(
            {
                "status": "post",
                "type": config["eventtype"],
                "edition": config["edition"],
            }
        )
    return json.dumps({"status": "over"})


@app.route("/pb/<event>")
@jwt_required()
def get_user_pbs(event: str):
    log_access(f"/pb/{event} - GET", bool(current_user))
    import requests

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://records.kacky.info/pb/{login}/{event}")
    if not r.ok:
        flask.jsonify("An Error occured"), 400
    return r.text


@app.route("/performance/<event>")
@jwt_required()
def get_user_performance(event: str):
    log_access(f"/performance/{event} - GET", bool(current_user))
    import requests

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://records.kacky.info/performance/{login}/{event}")
    if not r.ok:
        flask.jsonify("An Error occured"), 400
    return r.text


def check_event_edition_legal(event: Any, edition: Any):
    # check if parameters are valid (this also is input sanitation)
    if isinstance(event, str) and edition.isdigit() and event in ["kk", "kr"]:
        if event.upper() == "KK" and edition == 8:
            raise AssertionError
        # Allowed arguments
        return True
    raise AssertionError


@app.route("/")
def ind():
    return "nothing to see here, go awaiii"


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


@jwt_required()
def return_bad_value(error_param: str):
    logger.error(
        f"Bad value for {error_param} - userid {current_user.get_id()} "
        f"- payload {flask.request.json}"
    )
    return flask.jsonify(flask_restful.http_status_message(400)), 400


def is_invalid(
    value: Any, dtype: Any, vrange: Tuple[int, int] = None, length: int = None
):
    """
    Checks if value is valid by type and value.

    Parameters
    ----------
    value: Any
        Value to check
    dtype: Any
        Type value shall have
    vrange: Tuple[int, int]
        Range in which value is valid (e.g. numerical range)
    length: int
        Valid length of value (e.g. for strings)

    Returns
    -------
    bool
        True if value is invalid according to parameters
    """
    if not isinstance(value, dtype):
        return True

    if length and dtype is str:
        if len(value) >= length:
            return True

    if vrange and not (vrange[0] <= value <= vrange[1]):
        return True

    return False


def log_access(route: str, logged_in: bool = False):
    logger.info(
        f"{route} accessed by "
        f"{flask.request.headers.get('X-Forwarded-For', 'unknown-forward')}. "
        f"User status: {logged_in}"
    )


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

MAPIDS = MiscDBOperators(config, secrets).get_map_kackyIDs_for_event(
    config["eventtype"], config["edition"]
)
MAPIDS = (min(MAPIDS), max(MAPIDS))

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

api = KackyAPIHandler(config, secrets)

# Set up logging
logger = logging.getLogger(config["logger_name"])
logger.setLevel(eval("logging." + config["loglevel"]))

if config["log_visits"]:
    # Enable logging of visitors to dedicated file. More comfortable than using system
    # log to count visitors.
    # Counting with "cat visits.log | wc -l"
    f = open(config["visits_logfile"], "a+")
    f.close()

# Set up JWT
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(
    days=100
)  # Why 100? idk, looks cool

logger.info("Starting application.")
if "gunicorn" not in os.environ.get("SERVER_SOFTWARE", ""):
    app.run(host=config["bind_hosts"], port=config["port"])
