import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Tuple

import flask
import flask_restful
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
)
from tmformatresolver import TMString

from kacky_eventpage_backend import config, secrets
from kacky_eventpage_backend.db_ops.admin_operations import AdminOperators
from kacky_eventpage_backend.db_ops.db_operator import MiscDBOperators
from kacky_eventpage_backend.kacky_api.kacky_api_handler import KackyAPIHandler
from kacky_eventpage_backend.mailsender import MailSender
from kacky_eventpage_backend.routes.records_api_proxy import records_api_proxy_blueprint
from kacky_eventpage_backend.usermanagement.token_blacklist import TokenBlacklist
from kacky_eventpage_backend.usermanagement.user_operations import UserDataMngr
from kacky_eventpage_backend.usermanagement.user_session_handler import User

app = flask.Flask(__name__)
jwt = JWTManager(app)
CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

app.register_blueprint(records_api_proxy_blueprint)


def get_pagedata(login: str = ""):
    """Collects all information needed for the dashboard page.

    Behaviour changes depending on if a login is passed or not.
    Passing a login will return information about the user's finishes on the event.
    Else, general information about the event is returned.

    Args:
        login (str, optional): A Trackmania login (either TMNF or TM20, depending on value of `config['eventtype']`).
            Defaults to "".

    Returns:
        dict: A dictionary containing all information needed for the dashboard page for the given login.

    Example:
        >>> get_pagedata("nixion4")
        {
            "servers": [
                {
                    "serverNumber": 1,
                    "serverDifficulty": 1,
                    "maps": [
                        {
                            "number": 1,
                            "author": "nixion4",
                            "finished": true,
                            "difficulty": 1
                        },
                        {
                            "number": 2,
                            "author": "nixion4",
                            "finished": false,
                            "difficulty": 18
                        }
                    ],
                    "timeLimit": 10,
                    "timeLeft": 600
                }
            ],
            "comptimeLeft": 600
        }
    """
    # use "$" as default login, because that char is not a legal login (at least in tmnf)
    curtime = datetime.datetime.now()
    if config["testing_mode"]:
        ttl = datetime.datetime.fromisoformat(config["testing_compend"]) - curtime
    else:
        ttl = datetime.datetime.fromisoformat(config["compend"]) - curtime
    timeleft = ttl.seconds

    response = {"servers": [], "comptimeLeft": timeleft}

    mdb = MiscDBOperators(config, secrets)
    fins = {}
    difficulties = {}
    if login != "":
        r = requests.get(
            f"https://api.kacky.gg/records/pb/{login}/{config['eventtype']}/{config['edition']}"
        )
        if r.ok:
            fins = r.json()
        with UserDataMngr(config, secrets) as um:
            difficulties = um.get_user_map_difficulties(
                current_user.get_id(), config["eventtype"]
            )

    for name, val in api.serverinfo.items():
        tmpdict = {}
        tmpdict["serverNumber"] = val.servernum
        tmpdict["serverDifficulty"] = val.difficulty
        tmpdict["maps"] = []
        for m in val.playlist.get_playlist_from_now():
            diff = difficulties.get(m, 0)
            mapdict = {
                "number": m,
                "author": mdb.get_map_author(
                    m, config["eventtype"], int(config["edition"])
                ),
                "finished": str(m) in fins,
                "difficulty": diff["map_diff"] if diff else 0,
            }
            tmpdict["maps"].append(mapdict)
        tmpdict["timeLimit"] = val.timelimit
        timeleft = val.timelimit * 60 - val.timeplayed
        tmpdict["timeLeft"] = timeleft if timeleft > 0 else 0
        response["servers"].append(tmpdict)
    return response


def add_playtimes_to_sheet(sheet):
    """Find the next time a map is played between all servers and add it to the sheet.

    For each map in the sheet, the next time it is played is found and added to the sheet.

    Args:
        sheet (dict): Dictionary containing `map_id`s as keys and a dictionary containing map information as values.

    Returns:
        dict: `sheet` with the `upcomingIn` and `server` keys added to each map.
    """
    serverinfo = api.serverinfo.values()
    for mapid, dataset in sheet.items():
        if config["testing_mode"]:
            dataset["upcomingIn"] = 1 * 60 + 1
            dataset["server"] = "TestServer XYZ"
        else:
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
    return sheet


@app.route("/register", methods=["POST"])
def register_user():
    """Endpoint for registering a new user.

    Expects POST fields `user`, `pwd` and `mail` to be passed as JSON.
    Logs IP and whether user is logged in.

    Returns:
        flask.Response:
            HTTP response with status code 201 if user was created successfully,
            409 if user already exists.

    Example Request:
        >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        >>> r = requests.post(
                    "http://localhost:5000/login",
                    headers=headers,
                    data={"user": "newuser", "pwd": "hunter2", "mail": "user@domain.tld"}
                )
        >>> r.status_code
            201
        >>> r.json()
            '"Created"'
    """
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
    """Endpoint to log a user in.

    Expect POST fields `user` and `pwd` to be passed as JSON.
    Password is expected to be cleartext and is hashed before being compared to the database.
    TODO: change to hash before sending to server.
    Logs IP and whether user is logged in.

    Example request:
    >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
    >>> r = requests.post(
                "http://localhost:5000/login",
                headers=headers,
                data={"user": "corkscrew", "pwd": "hunter2"}
            )
    >>> r.json()
        {"access_token": "part1.part2.part3", "expires": "1234567890.0"}
    >>> r.status_code
        200
    >>> r = requests.post(
                "http://localhost:5000/login",
                headers=headers,
                data={"user": "corkscrew", "pwd": "password123"}
            )
    >>> r.json()
        {"Unauthorized": "Wrong username or password"}
    >>> r.status_code
        401

    Returns:
        flask.Response:
            HTTP response with status code 200 and a token and expiration timestamp if login was successful,
            401 if login failed.
    """
    log_access("/login - POST", bool(current_user))
    assert not is_invalid(flask.request.json["user"], str, length=80)
    assert not is_invalid(flask.request.json["pwd"], str, length=80)
    user = User(flask.request.json["user"], config, secrets).exists()

    if not user:
        return flask.jsonify("Wrong username or password"), 401

    # user wants to login
    cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
    login_success = user.login(cryptpw)

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
    """Endpoint to change user data.

    Authentication is required via JWT.
    Expects POST fields `tmnf`, `tm20`, `discord`, `pwd` OR `mail` to be passed as JSON.
    Multiple fields can be passed at once.
    Password is expected to be cleartext and is hashed before being stored to the database.

    Example request:
        >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        >>> requests.post("http://localhost:5000/usermgnt", headers=headers, data={"tmnf": "simo_900"}).status_code
        200

    Returns:
        flask.Response: HTTP response with status code 200 if user data was changed successfully,
            500 if a given value for a field could not be processed (and raised an exception along the way).
            Bogus values are "ignored", all request return 200, if no exception was raised.
    """
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
    """Endpoint to get the JWT holder's account data.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.

    Returns:
        dict: A dictionary containing the user's account data.

    Example request:
        >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
        >>> requests.get("http://localhost:5000/usermgnt", headers=headers).json()
        {"tmnf": "asd", "tm20": "asd", "discord": "asd"}
        >>> requests.get("http://localhost:5000/usermgnt", headers=headers).status_code
        200
    """
    log_access("/usermgnt - GET", bool(current_user))
    um = UserDataMngr(config, secrets)
    userid = current_user.get_id()
    tmnf = um.get_tmnf_login(userid)
    tm20 = um.get_tm20_login(userid)
    discord = um.get_discord_id(userid)
    return flask.jsonify({"tmnf": tmnf, "tm20": tm20, "discord": discord}), 200


@app.route("/usermgnt/delete", methods=["POST"])
@jwt_required()
def delete_user():
    """Endpoint to delete the JWT holder's account.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.

    Returns:
        flask.Response: HTTP response with status code 200 if user was deleted successfully,
            500 if an error occured. Error could either be a database error when blacklisting token
            or `userid` was not found.

    Example request:
        >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
        >>> r = requests.post("http://localhost:5000/usermgnt/delete", headers=headers)
        >>> r.json()
            '"OK"'
        >>> r.status_code
            200
    """
    log_access("/usermgnt/delete - POST", bool(current_user))
    um = UserDataMngr(config, secrets)
    userid = current_user.get_id()
    try:
        um.delete_user(userid)
        TokenBlacklist(config, secrets).blacklist_token(get_jwt()["jti"])
    except Exception:
        return flask.jsonify(flask_restful.http_status_message(500)), 500
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/pwdreset", methods=["POST"])
def reset_password():
    """Endpoint to reset a user's password.

    Logs IP and whether user is logged in.
    Expects POST fields `mail` and `user` OR a field `token` to be passed as JSON.
    Two step process:
    1. User requests a password reset by passing their mail and username.
        A token is generated and sent to the user's mail.
    2. User passes the token and their new password to this endpoint.

    Returns:
        flask.Response: HTTP response with status code 200 if step was successful,
            400 if no valid fields were passed,
            401 if token was invalid or writing to database failed,
            500 if an error occured token mail could not be sent.
    """
    log_access("/pwdreset - POST", bool(current_user))
    # ======= FLOW FOR PASSED TOKEN (SECOND STEP IN PWD RESET)
    if (
        flask.request.json.get("token", None) is not None
        and flask.request.json.get("pwd", None) is not None
    ):
        if not (
            isinstance(flask.request.json["token"], str)
            and len(flask.request.json["token"]) == 6
        ):
            return return_bad_value("token")
        um = UserDataMngr(config, secrets)
        cryptpw = hashlib.sha256(flask.request.json["pwd"].encode()).hexdigest()
        success = um.reset_password_with_token(flask.request.json["token"], cryptpw)
        if success:
            return flask.jsonify(flask_restful.http_status_message(200)), 200
        else:
            return flask.jsonify(flask_restful.http_status_message(401)), 401

    # ======= FLOW FOR PASSED MAIL AND USER (FIRST STEP IN PWD RESET)
    if (
        flask.request.json.get("mail", None) is not None
        and flask.request.json.get("user", None) is not None
    ):
        if is_invalid(flask.request.json["mail"], str, length=80) or is_invalid(
            flask.request.json["user"], str, length=80
        ):
            return return_bad_value("mail or user")
        cryptmail = hashlib.sha256(flask.request.json["mail"].encode()).hexdigest()
        um = UserDataMngr(config, secrets)
        resettoken = um.set_reset_token(flask.request.json["user"], cryptmail)
        if resettoken == -1:
            # no userid found, username/email combo does not exist. 200 for no information leaking
            return flask.jsonify(flask_restful.http_status_message(200)), 200
        mail = MailSender(config, secrets)
        sent = mail.send_pwd_reset_mail(flask.request.json["mail"], resettoken)
        if sent:
            return flask.jsonify(flask_restful.http_status_message(200)), 200
        else:
            return flask.jsonify(flask_restful.http_status_message(500)), 500

    return flask.jsonify(flask_restful.http_status_message(400)), 400


@app.route("/logout")
@jwt_required()
def logout_and_redirect_index():
    """Logs the user out and redirects to the index page.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    JWT token must be deleted on client, server blacklists token and does not accept it in future requests.
    Any token will be "accepted", since this merely blacklists a token on server side.

    Returns:
        flask.Response: HTTP response with status code 200.
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
    """Endpoint to provide data for the dashboard page.

    Authentication is optional via JWT. If a valid token is passed, user specific data is added to the response.
    Logs IP and whether user is logged in.

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing all information needed for the
            dashboard page.
    """
    log_access("/dashboard - GET", bool(current_user))
    um = UserDataMngr(config, secrets)
    if not current_user:  # User is not logged in
        tm_login = ""  # "$" is an illegal tmnf login (tm20 whould be fine)
    elif config["eventtype"] == "KK":
        tm_login = um.get_tmnf_login(current_user.get_id())
    elif config["eventtype"] == "KR":
        tm_login = um.get_tm20_login(current_user.get_id())
    serverinfo = get_pagedata(tm_login)
    return flask.jsonify(serverinfo), 200


@app.route("/fin")
@jwt_required(optional=True)
def build_fin_json():
    """Endpoint to provide data about the JWT holder's finishes.

    Authentication is optional via JWT.
    Logs IP and whether user is logged in.
    For not logged in users, an "empty" dictionary is returned, values contain no finishes.
    Else, a dictionary containing the number of finishes and a list of map ids is returned.
    Trackmania logins are retrieved from the database by the user's ID from provided JWT.
    HTTP response code is always 200, except when JWT is invalid or database error occured.

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing the number of finishes and a
            list of map ids.

    Example request:
        >>> headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
        >>> r = requests.get("http://localhost:5000/fin", headers=headers)
        >>> r.json()
            {"finishes": 1, "mapids": [-150]}
        >>> r.status_code
            200
    """
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
            fins = list(get_finished_maps_event(tm_login).keys())
            return flask.jsonify({"finishes": len(fins), "mapids": fins}), 200
        else:
            return flask.jsonify({"finishes": 0, "mapids": []}), 200
    except Exception:
        return return_bad_value("login")


@app.route("/spreadsheet/<eventtype>", methods=["POST"])
@jwt_required()
def spreadsheet_update(eventtype: str):
    """Endpoint to update the spreadsheet.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Expects POST fields `mapid`, `diff`, `clip` OR `alarm` to be passed as JSON.
    Early return if a value is invalid.
    `mapid` is required, represents main key for updating stuff.
    If `diff` is passed, the map's difficulty is updated.
    If `clip` is passed, the map's clip is updated.
    If `alarm` is passed, the the user changes discord notification settings for the map.

    Args:
        eventtype (str): Value must either be "kk" or "kr" (case insensitive).

    Returns:
        flask.Response: HTTP response with status code 200 if update was successful,
            404 if a passed field is invalid. Returns early if a value is invalid. Might lead
            to partial changes.

    """
    log_access(f"/spreadsheet/{eventtype} - POST", bool(current_user))
    # mapid is required, represents main key for updating stuff
    try:
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
        # if is_invalid(flask.request.json["alarm"], int, vrange=(int(MAPIDS[0]), int(MAPIDS[1]))):
        #     return return_bad_value("discord alarm toggle")
        if is_invalid(
            int(flask.request.json["mapid"]),
            int,
            vrange=(int(MAPIDS[0]), int(MAPIDS[1])),
        ):
            return return_bad_value("discord alarm toggle")
        um.toggle_discord_alarm(
            current_user.get_id(), flask.request.json["mapid"], eventtype
        )

    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/spreadsheet", methods=["GET"])
@jwt_required(optional=True)
def spreadsheet_current_event():
    """Endpoint to get the spreadsheet for the currently running event.

    Authentication is optional via JWT. With a valid token, user specific data is added to the spreadsheet.
    Logs IP and whether user is logged in.
    TODO: This may break if no event is currently running. Should return something like "offseason".

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing the spreadsheet for the
            currently running event.
            Only produces HTTP 500 id database error occured or configuration file is bad.
    """
    log_access("/spreadsheet - GET", bool(current_user))

    if not is_event_running():
        return flask.jsonify(flask_restful.http_status_message(423)), 423

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
    add_playtimes_to_sheet(sheet)
    sheet = dict(sorted(sheet.items()))
    return flask.jsonify(list(sheet.values())), 200


@app.route("/spreadsheet/<event>/<edition>", methods=["GET"])
@jwt_required(optional=True)
def spreadsheet_hunting(event, edition):
    """Endpoint to get the spreadsheet for a specific event.

    Authentication is optional via JWT. With a valid token, user specific data is added to the spreadsheet.
    Logs IP and whether user is logged in.

    Args:
        event (string): Must be either "kk" or "kr" (case insensitive).
        edition (str): Edition of the requested event. String representation of an integer.

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing the spreadsheet for the
            requested event. 404 if event or edition are invalid or their combination does not exist.
    """
    log_access(f"/spreadsheet/{event}/{edition} - GET", bool(current_user))
    try:
        if edition == "all":
            check_event_edition_legal(event, "1")
        else:
            check_event_edition_legal(event, edition)
    except AssertionError:
        return flask.jsonify("404 Error: bad path"), 404

    um = UserDataMngr(config, secrets)
    # Check if user is logged in.
    if not current_user:  # User not logged in
        # Only provide base data
        sheet = um.get_spreadsheet_event(
            None, event, edition, raw=bool(flask.request.args.get("rawnicks", False))
        )
    else:  # User logged in
        # Add user specific data to the spreadsheet
        userid = current_user.get_id()
        sheet = um.get_spreadsheet_event(
            userid, event, edition, raw=bool(flask.request.args.get("rawnicks", False))
        )
        # finned = build_fin_json()
        # for fin in finned["mapids"]:
        #    sheet[fin]["finished"] = True

    # sheet = dict(sorted(sheet.items()))
    return flask.jsonify(list(sheet.values())), 200


@app.route("/mapinfo/<eventtype>/<kackyid>", methods=["GET"])
@jwt_required(optional=True)
def get_single_map_info(eventtype, kackyid):
    """Endpoint to get information about a single map.

    Authentication is optional via JWT. With a valid token, user specific data is added to the spreadsheet.
    Logs IP and whether user is logged in.
    Returns information about a single map, identified by it's ID ()`kackyid`).

    Args:
        eventtype (str): Value must either be "kk" or "kr" (case insensitive).
        kackyid (str): ID of the map to get information about. String representation of an integer.

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing the information about the
            requested map. 404 if event or edition are invalid or their combination does not exist.
    """
    log_access(f"/mapinfo/{eventtype}/{kackyid} - GET", bool(current_user))
    if not check_event_edition_legal(eventtype, "1"):
        return flask.jsonify("404 Error: bad path"), 404
    try:
        int(kackyid)
    except ValueError:
        return flask.jsonify("404 Error: bad path"), 404
    um = UserDataMngr(config, secrets)
    # Check if user is logged in.
    if not current_user:  # User not logged in
        # Only provide base data
        sheet = um.get_spreadsheet_line(None, eventtype, kackyid)
    else:  # User logged in
        # Add user specific data to the spreadsheet
        userid = current_user.get_id()
        sheet = um.get_spreadsheet_line(userid, eventtype, kackyid)
        # finned = build_fin_json()
        # for fin in finned["mapids"]:
        #    sheet[fin]["finished"] = True

    # while there is no guarantee that there is only one element, the database would be wrong if there were multiple
    return flask.jsonify(list(sheet.values())[0]), 200


@app.route("/mapinfo/<eventtype>/<kacky_id>", methods=["POST"])
@jwt_required()
def edit_mapinfo(eventtype: str, kacky_id: str):
    """Endpoint to edit information about a single map.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Only available to admins.
    Expects POST fields `reset` to be passed as JSON, containing the map's ID,
    which worldrecord should be reset in database.

    Args:
        eventtype (str): Value must either be "kk" or "kr" (case insensitive).
        kacky_id (str): ID of the map which should be edited. String representation of an integer.

    Returns:
        flask.Response: HTTP response with status code 200 if reset was successful,
            401 if user is not an admin,
            404 if `eventtype` or `kacky_id` are invalid.
    """
    log_access(f"/mapinfo/{eventtype}/{kacky_id} - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return "Not authorized. Your actions will have consequences.", 401
    if not check_event_edition_legal(eventtype, "1"):
        return return_bad_value("path")
    try:
        int(kacky_id)
    except ValueError:
        return return_bad_value("path")

    if flask.request.json.get("reset", None) is not None:
        ao = AdminOperators(config, secrets)
        if not ao.reset_wr(eventtype, int(kacky_id)):
            return flask.jsonify(flask_restful.http_status_message(500)), 500
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/eventstatus")
def event_status():
    """Endpoint that returns the status of events.

    Logs IP and whether user is logged in.
    Can return be overwritten with a paramter for testing.
    States whether an event is currently running, coming up, recently ended or if it's offseason.

    Returns:
        flask.Response: : JSON Dict. `status` can have four values:
            - "active": Event is currently running.
            - "post": Event has recently ended (<30 days ago).
            - "pre": Event is coming up (<30 days to event start).
            - "offseason": Else.
            Response can contain additional keys providing information about the event.
            Additional (optional) keys are:
                - type ("kk", "kr")
                - edition (string representation of an integer)
                - start (ISO 8601 timestamp of event's start)
                - end (ISO 8601 timestamp of event's end)
    """
    log_access("/eventstatus - GET", None)
    if config["testing_mode"]:
        compend = datetime.datetime.fromisoformat(config["testing_compend"])
        compstart = datetime.datetime.fromisoformat(config["testing_compstart"])
        if flask.request.args.get("forcephase", None) == "active":
            return flask.jsonify(
                {
                    "status": "active",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                }
            )
        elif flask.request.args.get("forcephase", None) == "post":
            return flask.jsonify(
                {
                    "status": "post",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                }
            )
        elif flask.request.args.get("forcephase", None) == "pre":
            return flask.jsonify(
                {
                    "status": "pre",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                    "start": compstart.isoformat(),
                }
            )
        elif flask.request.args.get("forcephase", None) == "offseason":
            return flask.jsonify({"status": "offseason"})
    else:
        compstart = datetime.datetime.fromisoformat(config["compstart"])
        compend = datetime.datetime.fromisoformat(config["compend"])
    if compstart <= datetime.datetime.now() <= compend:
        return flask.jsonify(
            {
                "status": "active",
                "type": config["eventtype"],
                "edition": config["edition"],
            }
        )
    elif datetime.datetime.now() < compend + datetime.timedelta(days=30):
        return flask.jsonify(
            {
                "status": "post",
                "type": config["eventtype"],
                "edition": config["edition"],
            }
        )
    elif compstart - datetime.timedelta(days=30) < datetime.datetime.now() <= compstart:
        return flask.jsonify(
            {
                "status": "pre",
                "type": config["eventtype"],
                "edition": config["edition"],
                "start": compstart.isoformat(),
            }
        )
    return flask.jsonify({"status": "offseason"})


@app.route("/events", methods=["GET", "POST"])
@jwt_required(optional=True)
def get_events():
    """Endpoint to get information about available events.

    Authentication is optional via JWT. With a valid token, user specific data is added to the spreadsheet.
    Logs IP and whether user is logged in.
    If a user is logged in and is an admin, the `visibility` field can be passed as JSON to get the visibility of
    events. If `visibility` is passed and set to "true", the response will contain all events, including their IDs
    and visibility status.
    If a client is not an admin, only visible events are returned.

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing all visible events.
            If `visibility` is passed as `True` and the user is an admin, the response will contain all events,
            including their IDs and visibility status.
            If `visibility` is passed as `True` and the user is not an admin, the response be an error with HTTP 401.
    """
    log_access("/events - GET", bool(current_user))
    mdb = MiscDBOperators(config, secrets)
    if flask.request.method == "POST":
        if flask.request.json.get("visibility", None) == "true":
            if not current_user or not current_user.is_admin():
                # user is not an admin and can bugger off.
                log_access("unauthorized admin operation!")
                return "Not authorized. Your actions will have consequences.", 401
            return (
                flask.jsonify(
                    mdb.get_events(include_ids=True, include_visibility=True)
                ),
                200,
            )
    return flask.jsonify(mdb.get_events()), 200


@app.route("/pb/<event>")
@jwt_required()
def get_user_pbs(event: str):
    """Endpoint to retrieve a JWT holder's personal bests for an eventtype.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Proxy endpoint that build a request to the records API.
    TODO: make this response json and fix docstring return type
    Trackmania login is determined by the passed JWT.

    Args:
        event (str): Value must either be "kk" or "kr" (case insensitive).

    Returns:
        str: String representation of a dict containing a JWT holder's personal bests for the
            requested event type.
    """
    log_access(f"/pb/{event} - GET", bool(current_user))

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://api.kacky.gg/records/pb/{login}/{event}")
    if not r.ok:
        return return_bad_value("event")
    return r.text


@app.route("/performance/<event>")
@jwt_required()
def get_user_performance(event: str):
    """Endpoint to retrieve a JWT holder's personal bests for an eventtype.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Proxy endpoint that build a request to the records API.

    Args:
        event (str): Value must either be "kk" or "kr" (case insensitive).

    Returns:
        str: String representation of a dict containing a JWT holder's finish count per event.
    """
    log_access(f"/performance/{event} - GET", bool(current_user))

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://api.kacky.gg/records/performance/{login}/{event}")
    if not r.ok:
        return return_bad_value("event")
    return r.text


@app.route("/event/<login>/finned")
def get_finished_maps_event(login: str):
    """Endpoint to get a Trackmania login's finished maps for the currently running event.

    Logs IP and whether user is logged in.
    Designed for streamer use.
    Multiple formats are available by passing a query parameter:
    - `string=ids`: Returns a string of finished map IDs, separated by commas.
    - `string=ranks`: Returns a string of finished map IDs and the login's rank on the map.
    - `string=scores`: Returns a string of finished map IDs and the login's score/personal best in seconds.
    - `list=1`: Returns a (Python) list of map IDs (or string representation if accessed via web).

    Default returns a dict with map IDs as key, and rank and score as values.

    TODO: add bool `internal`, like in `get_unfinished_maps_event`?
    TODO: jsonify return values

    Args:
        login (str): Trackmania Login of the user to get finished maps for.

    Returns:
        Any: Dict, list or string, depending on query parameters and call origin.
    """
    log_access(f"/event/{login}/finned - GET", bool(current_user))

    if not is_event_running():
        return flask.jsonify(flask_restful.http_status_message(423)), 423

    assert isinstance(login, str)

    r = requests.get(
        f"https://api.kacky.gg/records/pb/{login}/{config['eventtype']}/{config['edition']}"
    )

    try:
        scores = {
            k: v
            for k, v in r.json().items()
            if int(MAPIDS[0]) <= int(k) <= int(MAPIDS[1])
        }
    except AttributeError:
        return return_bad_value(login)
    if flask.request.args.get("string", default=0, type=str) == "ids":
        return ", ".join(scores.keys())
    if flask.request.args.get("string", default=0, type=str) == "ranks":
        return ", ".join([f"{mid} ({s['kacky_rank']})" for mid, s in scores.items()])
    if flask.request.args.get("string", default=0, type=str) == "scores":
        return ", ".join([f"{mid} ({s['score'] / 1000}s)" for mid, s in scores.items()])
    if flask.request.args.get("list", default=0, type=int) == 1:
        return list(scores.keys())
    return scores


@app.route("/event/<login>/unfinned")
def get_unfinished_maps_event(login: str, internal: bool = False):
    """Endpoint to get a Trackmania login's unfinished maps for the currently running event.

    Logs IP and whether user is logged in.
    Designed for streamer use.
    Multiple formats are available by passing a query parameter:
    - `string=ids`: Returns a string of unfinished map IDs, separated by commas.
    - JSON list of map IDs if no query parameter is passed.

    `internal` returns Python list for use internal use.

    Args:
        login (str): Trackmania Login of the user to get unfinished maps for.
        internal (bool, optional): _description_. Defaults to False.

    Returns:
        Any: list, string or flask.Response, depending on query parameters and call origin.
    """
    log_access(f"/event/{login}/unfinned - GET", bool(current_user))

    if not is_event_running():
        return flask.jsonify(flask_restful.http_status_message(423)), 423

    assert isinstance(login, str)

    r = requests.get(
        f"https://api.kacky.gg/records/pb/{login}/{config['eventtype']}/{config['edition']}"
    )
    mapids = [
        m
        for m in range(int(MAPIDS[0]), int(MAPIDS[1]) + 1)
        if str(m) not in r.json().keys()
    ]
    logger.info(r.json())
    if internal:
        return mapids
    if flask.request.args.get("string", default=0, type=int):
        return ", ".join([f"{m}" for m in mapids]), 200
    return flask.jsonify(mapids), 200


@app.route("/event/<login>/nextunfinned")
def get_next_unfinned_event(login: str):
    """Endpoint to get an unfinished map of a TM login that is played next on any server in the current.

    Logs IP and whether user is logged in.
    Designed for streamer use.
    Multiple formats are available by passing a query parameter:
    - `simochat=1`: Returns a natural language string that lists the information.
    - JSON dict with map ID as key and a dict with server number and time until next play as value by default.

    Args:
        login (str): Trackmania Login which requests the next unfinished map.

    Returns:
        Any: flask.Response or string, depending on query parameters and call origin.
    """
    log_access(f"/event/{login}/nextunfinned - GET", bool(current_user))
    if not is_event_running():
        return flask.jsonify(flask_restful.http_status_message(423)), 423
    assert isinstance(login, str)

    unfinned = get_unfinished_maps_event(login, internal=True)
    result = {unf: {} for unf in unfinned}
    add_playtimes_to_sheet(result)
    # find shortest wait time
    mintime = min([v["upcomingIn"] for v in result.values()])
    up_maps = {k: v for k, v in result.items() if v["upcomingIn"] == mintime}
    if flask.request.args.get("simochat", default=0, type=int):
        msg = f"Next unfinished map{'s' if len(up_maps) > 1 else ''} in {mintime} minutes: "
        maplist = ", ".join([f"{k} (Server {v['server']})" for k, v in up_maps.items()])
        return msg + maplist, 200
    return flask.jsonify(up_maps), 200


@app.route("/wrleaderboard/<eventtype>")
def get_wr_leaderboard(eventtype: str):
    """Endpoint to get the world record leaderboard for an eventtype.

    Logs IP and whether user is logged in.
    Passing parameter `html=True` will return the leaderboard with nicknames as HTML representations.
    `html=False` will return the leaderboard with nicknames formatted as in Trackmania ($ formatters remain).

    Args:
        eventtype (str): Value must either be "kk" or "kr" (case insensitive).

    Returns:
        flask.Response: HTTP response with status code 200 and a dictionary containing the world record leaderboard
            for the requested eventtype.
            Dictionary contains the TM login, the corresponding nickname and the number of world records held.
    """
    log_access(f"/wrleaderboard/{eventtype} - GET", bool(current_user))
    check_event_edition_legal(eventtype, "1")
    mdb = MiscDBOperators(config, secrets)
    wrs = mdb.get_wr_leaderboard_by_etype(eventtype)
    nicknames = mdb.get_most_recent_nicknames(eventtype)
    # logger.info(wrs)
    if flask.request.args.get("html", "True") == "False":
        wrs_nicked = [
            {
                "nwrs": w["nwrs"],
                "login": w["login"],
                "nickname": nicknames.get(w["login"], w["login"]),
            }
            for w in wrs
        ]
    else:
        wrs_nicked = [
            {
                "nwrs": w["nwrs"],
                "login": w["login"],
                "nickname": TMString(nicknames.get(w["login"], w["login"])).html,
            }
            for w in wrs
        ]
    # logger.info(wrs_nicked)
    return flask.jsonify(wrs_nicked)


@app.route("/event/nextrun/<kacky_id>")
def get_next_map_run(kacky_id):
    """Endpoint to get the next time a map is played during a running event.

    TODO: Enable access logging?

    Args:
        kacky_id (str): ID of the map

    Returns:
        Any: Dict or string, depending on query parameters and call origin.
    """
    log_access(f"/event/nextrun/{kacky_id} - GET", bool(current_user))

    if not is_event_running():
        return flask.jsonify(flask_restful.http_status_message(423)), 423

    try:
        int(kacky_id)
    except ValueError:
        return return_bad_value("kacky_id")
    if not MAPIDS[0] <= int(kacky_id) <= MAPIDS[1]:
        return_bad_value("kacky_id")
    version = flask.request.args.get("version", "")
    sheet = {f"{kacky_id}{(f' [{version}]' if version else '')}": {}}
    add_playtimes_to_sheet(sheet)
    dashboard = get_pagedata()
    if dashboard["comptimeLeft"] <= 0:
        return "Competition Over", 200
    sheet["currentlyRunning"] = False
    for server in dashboard["servers"]:
        if server["maps"][0]["number"] == int(kacky_id):
            sheet["currentlyRunning"] = server["serverNumber"]
            sheet["timeLimit"] = server["serverNumber"]
            sheet["timeLeft"] = server["timeLeft"]
    return sheet, 200


def check_event_edition_legal(event: Any, edition: Any):
    # check if parameters are valid (this also is input sanitation)
    if isinstance(event, str) and edition.isdigit() and event.upper() in ["KK", "KR"]:
        # Allowed arguments
        return True
    raise AssertionError


@app.route("/manage/events", methods=["POST"])
@jwt_required()
def manage_events():
    """Administration Endpoint: Create and edit events.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Only available to admins.
    Expects POST field `create` containing a JSON dict to be passed when creating a new event.
    Expects POST field `visible` containing a JSON dict to be passed when changing the visibility of an event.

    `create` expects the following keys:
        - `name`: Name of the event. String, max length 80.
        - `type`: Type of the event. String, must be either "KK" or "KR" (case insensitive).
        - `edition`: Edition of the event. String representation of an integer.
        - `startDate`: Start date of the event. ISO 8601 timestamp.
        - `endDate`: End date of the event. ISO 8601 timestamp.
        - `minID`: Minimum map ID of the event. String representation of an integer.
        - `maxID`: Maximum map ID of the event. String representation of an integer.

    `visible` expects the following keys:
        - `id`: ID of the event to change visibility of. String representation of an integer.
        - `value`: New visibility value. Boolean, must be either `true` or `false`.


    Returns:
        flask.Response: JSON response. HTTP 200 if successful, 401 if user is not an admin, 400 if a passed value is
            invalid, 500 if database error occured.
    """
    log_access("/manage/events - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return (
            flask.jsonify("Not authorized. Your actions will have consequences."),
            401,
        )
    logger.info(flask.request.json.get("create", None))
    if flask.request.json.get("create", None) is not None:
        if (
            is_invalid(flask.request.json["create"].get("name", None), str, length=80)
            or not check_event_edition_legal(
                flask.request.json["create"].get("type", None),
                flask.request.json["create"].get("edition", None),
            )
            or is_invalid(
                flask.request.json["create"].get("startDate", None), str, length=16
            )
            or is_invalid(
                flask.request.json["create"].get("endDate", None), str, length=16
            )
            or is_invalid(
                flask.request.json["create"].get("minID", None),
                int,
                check_castable=True,
            )
            or is_invalid(
                flask.request.json["create"].get("maxID", None),
                int,
                check_castable=True,
            )
        ):
            return flask.jsonify(flask_restful.http_status_message(400)), 400
        try:
            startDate = datetime.datetime.fromisoformat(
                flask.request.json["create"]["startDate"]
            )
            endDate = datetime.datetime.fromisoformat(
                flask.request.json["create"]["endDate"]
            )
        except ValueError:
            return flask.jsonify("Invalid date format!"), 400
        ao = AdminOperators(config, secrets)
        ret_code = ao.add_event(
            flask.request.json["create"]["name"],
            flask.request.json["create"]["type"],
            int(flask.request.json["create"]["edition"]),
            startDate,
            endDate,
            int(flask.request.json["create"]["minID"]),
            int(flask.request.json["create"]["maxID"]),
        )
        if ret_code < 1:
            if ret_code == -1:
                return (
                    flask.jsonify(
                        f"{flask.request.json['create']['name']}{flask.request.json['create']['edition']}"
                        " already exists!"
                    ),
                    400,
                )
            elif ret_code == -2:
                return (
                    flask.jsonify(
                        f"{flask.request.json['create']['edition']} already exists!"
                    ),
                    400,
                )
            elif ret_code == -3:
                return (
                    flask.jsonify(
                        "There already are maps in the pool with the Kacky IDs you provided!"
                    ),
                    400,
                )
            return flask.jsonify(flask_restful.http_status_message(500)), 500
    if flask.request.json.get("visible", None):
        if is_invalid(
            flask.request.json["visible"].get("id", None), int, check_castable=True
        ) or is_invalid(
            flask.request.json["visible"].get("value", None), bool, check_castable=True
        ):
            return flask.jsonify(flask_restful.http_status_message(400)), 400
        ao = AdminOperators(config, secrets)
        ao.change_event_visible(
            int(flask.request.json["visible"]["id"]),
            bool(flask.request.json["visible"]["value"]),
        )
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/manage/maps", methods=["POST"])
@jwt_required()
def manage_maps():
    """Administration Endpoint: Add new and update existing maps in database.

    Authentication is required via JWT.
    Logs IP and whether user is logged in.
    Only available to admins.
    Expects a CSV file in field `file` containing a CSV file to be passed when adding new maps.
    CSV is processed and stored in database.
    Overwrite protection can be disabled by passing a field `overwrite` with value `1`.

    Returns:
        flask.Response: JSON response. HTTP 200 if successful, 401 if user is not an admin, 400 if a passed value is
            invalid, 422 if the CSV file is invalid, 409 if the CSV file would overwrite existing data, 500 if database
            error occured.
    """
    log_access("/manage/maps - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return (
            flask.jsonify("Not authorized. Your actions will have consequences."),
            401,
        )
    from kacky_eventpage_backend.process_maps_file import process_maps

    logger.debug("processing file")
    logger.debug(flask.request.files.keys())
    if flask.request.files["file"]:
        processing_res = process_maps(flask.request.files["file"])
        logger.debug(f"processing_res: {processing_res}")
        if processing_res == -1:
            # missing required columns
            return flask.jsonify("Missing required columns"), 422
        if processing_res == -2:
            # not all values for required columns are set
            return (
                flask.jsonify("Values for required columns must be set at all times!"),
                422,
            )
        if processing_res == -3:
            # unknown columns were provided
            return flask.jsonify("Unknown columns"), 422

        # processing_res contains a list of lists that can be written to db.
        # this could overwrite data that already exists. in that case we return a HTTP 409 so that overwriting can be
        # forced with a dedicated `overwrite` flag
        ao = AdminOperators(config, secrets)
        logger.debug("processed file, storing in db")
        # logger.debug(f"Overwriting? {flask.request.files.get('overwrite', False).read() == b'1'}")
        # logger.debug(flask.request.files.get("overwrite").read())
        # logger.debug(type(flask.request.files.get("overwrite")))
        update_res = ao.update_maps(
            processing_res,
            flask.request.files.get("overwrite").read() == b"1"
            if flask.request.files.get("overwrite", False)
            else False,
        )

        if update_res == 409:
            # notify user to
            logger.debug("need confirmation to overwrite data")
            return (
                flask.jsonify(
                    "Your action would overwrite already existing maps! You may set 'overwrite' to 1"
                ),
                409,
            )
        if update_res == 200:
            # success
            logger.debug("success")
            return flask.jsonify("Updated maps."), 200
        return flask.jsonify(flask_restful.http_status_message(update_res)), update_res
    else:
        logger.debug("missing file")
        return flask.jsonify("Missing file"), 400


@app.route("/")
def ind():
    """Dummy index

    Returns:
        str: Some string
    """
    return "nothing to see here, go awaiii"


##################
# Endpoints for streamer trolling
# TODO: keep these? This was hacked together a day before April 1st, mainly so it works.
#       Could be prettyfied, or removed entirely
##################
message = ""
target = ""


@app.route("/stream")
@jwt_required()
def stream():
    logger.info(f"-------- {current_user.username}")
    with open(Path(__file__).parents[2] / "streamdata.txt", "r") as f:
        lines = f.readlines()
    target = lines[0]
    message = lines[1]
    logger.info(lines)
    logger.info(f"message: {message}")
    if current_user.username != target.rstrip():
        flask.jsonify(flask_restful.http_status_message(200)), 200
    return json.dumps({"data": message.rstrip()})


@app.route("/post", methods=["POST"])
def post():
    log_access("/post - POST", bool(current_user))
    if (
        "pwd" not in flask.request.json
        or flask.request.json["pwd"] != secrets["msg_send_pwd"]
    ):
        log_access("/post - POST - BAD PWD", bool(current_user))
        return flask.jsonify(flask_restful.http_status_message(403)), 403
    global message
    if "message" not in flask.request.json:
        log_access("/post - POST - BAD PARAMS", bool(current_user))
        return flask.jsonify(flask_restful.http_status_message(400)), 400
    message = flask.request.json["message"]
    with open(Path(__file__).parents[2] / "streamdata.txt", "r+") as f:
        lines = f.readlines()
        logger.info(lines)
    with open(Path(__file__).parents[2] / "streamdata.txt", "w") as f:
        lines = f.write(f"{lines[0].rstrip()}\n{message.rstrip()}\n")

    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/target", methods=["POST"])
def set_target():
    log_access("/target - POST", bool(current_user))

    if (
        "pwd" not in flask.request.json
        or flask.request.json["pwd"] != secrets["msg_send_pwd"]
    ):
        log_access("/target - POST - BAD PWD", bool(current_user))
        return flask.jsonify(flask_restful.http_status_message(403)), 403
    global target
    if "target" not in flask.request.json:
        log_access("/target - POST - BAD PARAMS", bool(current_user))
        return flask.jsonify(flask_restful.http_status_message(400)), 400
    target = flask.request.json["target"]
    logger.info(flask.request.json)
    with open(Path(__file__).parents[2] / "streamdata.txt", "w") as f:
        f.write("{target.rstrip()}\n\n")
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    """Checks if a token is revoked.

    Args:
        jwt_header (dict): JWT Header
        jwt_payload (dict): JWT Payload

    Returns:
        bool: True if token is revoked in database, False if not.
    """
    jti = jwt_payload["jti"]
    return TokenBlacklist(config, secrets).check_token(jti)


@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.username


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    username = jwt_data["sub"]
    return User(username, config, secrets).exists()


@jwt.additional_claims_loader
def add_claims_to_access_token(identity):
    """Helper function to add claims to JWT.

    Args:
        identity (Callable): Identity that was used when creating a JWT.

    Returns:
        dict: Dictionary containing the claims.
    """
    return {"isAdmin": identity.is_admin()}


@jwt_required()
def return_bad_value(error_param: str):
    """Helper function to return a bad value error.

    Args:
        error_param (str): Name of the parameter that is bad.

    Returns:
        flask.Response: HTTP response with status code 400 and a dictionary containing the error message.
    """
    if (
        flask.request.headers.get("X-Forwarded-For", "unknown-forward")
        == "213.109.163.46"
    ):
        return
    logger.error(
        f"Bad value for {error_param} - userid {current_user.get_id()} "
        f"- payload {flask.request.json}"
    )
    return flask.jsonify(flask_restful.http_status_message(400)), 400


def is_invalid(
    value: Any,
    dtype: Any,
    vrange: Tuple[int, int] = None,
    length: int = None,
    check_castable=False,
):
    """Checks if value is valid by type and value.

    Args:
        value (Any): Value to check.
        dtype (Any): Type `value` should have to be valid.
        vrange (Tuple[int, int], optional): Range in which `value` is valid (e.g. numerical range). Defaults to None.
        length (int, optional): Valid length of `value` (e.g. for strings). Defaults to None.
        check_castable (bool, optional): If `type(value) != dtype`, check if casting is possible. Defaults to False.

    Returns:
        bool: True if value is invalid, False if value is valid.
    """
    if not isinstance(value, dtype):
        if check_castable:
            try:  # try if it is possible to cast (BEAUTIFUL, does not at all need explanation how it works :3)
                dtype(value)  # casts value to the type of dtype
            except ValueError:
                return True
        else:
            return True
    if length and dtype is str:
        if len(value) > length:
            return True

    if vrange and not (min(vrange) <= value <= max(vrange)):
        return True

    return False


def log_access(route: str, logged_in: bool = False):
    """Helper function to log access to endpoints.

    Logs IP and whether user is logged in.

    Args:
        route (str): Accessed route.
        logged_in (bool, optional): Is client a logged in user? Defaults to False.
    """
    logger.info(
        f"{route} accessed by "
        f"{flask.request.headers.get('X-Forwarded-For', 'unknown-forward')}. "
        f"User status: {logged_in}"
    )


def is_event_running():
    if config["testing_mode"]:
        return (
            datetime.datetime.fromisoformat(config["testing_compstart"])
            <= datetime.datetime.now()
            <= datetime.datetime.fromisoformat(config["testing_compend"])
        )
    logger.info(f'{type(config["compstart"])}  {config["compstart"]}')
    return (
        datetime.datetime.fromisoformat(config["compstart"])
        <= datetime.datetime.now()
        <= datetime.datetime.fromisoformat(config["compend"])
    )


#                    _
#                   (_)
#    _ __ ___   __ _ _ _ __
#   | '_ ` _ \ / _` | | '_ \
#   | | | | | | (_| | | | | |
#   |_| |_| |_|\__,_|_|_| |_|
#


MAPIDS = MiscDBOperators(config, secrets).get_map_kackyIDs_for_event(
    config["eventtype"], config["edition"]
)
# build numbers, ignoring potential '[vX]'s
MAPIDS = (min(MAPIDS), max(MAPIDS))

api = KackyAPIHandler(config, secrets)

# Set up logging
logger = logging.getLogger(config["logger_name"])
logger.setLevel(eval("logging." + config["loglevel"]))

# Set up flask secrets
app.secret_key = secrets["flask_secret"]
app.config["JWT_SECRET_KEY"] = secrets["jwt_secret"]
# Set up JWT
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(
    days=100
)  # Why 100? idk, looks cool
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

if datetime.datetime.now() < datetime.datetime.fromisoformat(config["compend"]):
    # Update data from kacky API every minute
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=api._update_server_info,
        trigger="interval",
        seconds=60,
        max_instances=1,
    )
    # start scheduler
    api._update_server_info()
    scheduler.start()

logger.info("Starting application.")
if "gunicorn" not in os.environ.get("SERVER_SOFTWARE", ""):
    app.run(host=config["bind_hosts"], port=config["port"])
