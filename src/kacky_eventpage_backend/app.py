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
import yaml
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
config = {}
CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

app.register_blueprint(records_api_proxy_blueprint)


def get_pagedata(login: str = ""):
    # use "$" as default login, because that char is not a legal login (at least in tmnf)
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
    """
    Calculate upcoming playtimes and server information for each map in the sheet.
    Modification of sheet is inplace, adding new keys.
    Parameters
    ----------
    sheet : dict
        A dictionary containing `kacky_id`s as keys and dictionaries as values.
    Example
    -------
    sheet = {
        201: {
            'kacky_id': 201,
            'kacky_id_int': 201,
            'version': '',
            'author': 'nixion4',
            'rating': 8,
            'wr_score': 17580,
            'wr_holder': 'nixion4'
        },
    }
    get_next_playtimes(sheet)
    print(sheet)
    # {
    #     201: {
    #         'kacky_id': 201,
    #         'kacky_id_int': 201,
    #         'version': '',
    #         'author': 'nixion4',
    #         'rating': 8,
    #         'wr_score': 17580,
    #         'wr_holder': 'nixion4'
    #         'upcomingIn': 61,
    #         'server': 'TestServer XYZ'
    #     },
    # }
    """
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
    return sheet


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


@app.route("/usermgnt/delete", methods=["POST"])
@jwt_required()
def delete_user():
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
    log_access("/dashboard - GET", bool(current_user))
    um = UserDataMngr(config, secrets)
    if not current_user:  # User is not logged in
        tm_login = ""  # "$" is an illegal tmnf login (tm20 whould be fine)
    elif config["eventtype"] == "KK":
        tm_login = um.get_tmnf_login(current_user.get_id())
    elif config["eventtype"] == "KR":
        tm_login = um.get_tm20_login(current_user.get_id())
    serverinfo = get_pagedata(tm_login)
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
            fins = list(get_finished_maps_event(tm_login).keys())
            return {"finishes": len(fins), "mapids": fins}, 200
        else:
            return {"finishes": 0, "mapids": []}, 200
    except Exception:
        return {"finishes": 0, "mapids": []}


@app.route("/spreadsheet/<eventtype>", methods=["POST"])
@jwt_required()
def spreadsheet_update(eventtype: str):
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
    add_playtimes_to_sheet(sheet)
    sheet = dict(sorted(sheet.items()))
    return json.dumps(list(sheet.values())), 200


@app.route("/spreadsheet/<event>/<edition>", methods=["GET"])
@jwt_required(optional=True)
def spreadsheet_hunting(event, edition):
    log_access(f"/spreadsheet/{event}/{edition} - GET", bool(current_user))
    try:
        if edition == "all":
            check_event_edition_legal(event, "1")
        else:
            check_event_edition_legal(event, edition)
    except AssertionError:
        return "Error: bad path", 404

    # curl -H 'Accept: application/json' -H "Authorization: Bearer JWTKEYHERE"
    # http://localhost:5005/spreadsheet
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
    return json.dumps(list(sheet.values())), 200


@app.route("/mapinfo/<eventtype>/<kackyid>", methods=["GET"])
@jwt_required(optional=True)
def get_single_map_info(eventtype, kackyid):
    log_access(f"/mapinfo/{eventtype}/{kackyid} - GET", bool(current_user))
    if not check_event_edition_legal(eventtype, "1"):
        return "Error: bad path", 404
    try:
        int(kackyid)
    except ValueError:
        return "Error: bad path", 404
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
    return json.dumps(list(sheet.values())[0]), 200


@app.route("/mapinfo/<eventtype>/<kacky_id>", methods=["POST"])
@jwt_required()
def edit_mapinfo(eventtype: str, kacky_id: str):
    log_access(f"/mapinfo/{eventtype}/{kacky_id} - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return "Not authorized. Your actions will have consequences.", 401
    if not check_event_edition_legal(eventtype, "1"):
        return "Error: bad path", 400
    try:
        int(kacky_id)
    except ValueError:
        return "Error: bad path", 400

    if flask.request.json.get("reset", None) is not None:
        ao = AdminOperators(config, secrets)
        if not ao.reset_wr(eventtype, int(kacky_id)):
            return flask.jsonify(flask_restful.http_status_message(500)), 500
    return flask.jsonify(flask_restful.http_status_message(200)), 200


@app.route("/eventstatus")
def event_status():
    log_access("/eventstatus - GET", None)
    if config["testing_mode"]:
        compend = datetime.datetime.strptime(
            config["testing_compend"], "%d.%m.%Y %H:%M"
        )
        compstart = datetime.datetime.strptime(
            config["testing_compstart"], "%d.%m.%Y %H:%M"
        )
        if flask.request.args.get("forcephase", None) == "active":
            return json.dumps(
                {
                    "status": "active",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                }
            )
        elif flask.request.args.get("forcephase", None) == "post":
            return json.dumps(
                {
                    "status": "post",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                }
            )
        elif flask.request.args.get("forcephase", None) == "pre":
            return json.dumps(
                {
                    "status": "pre",
                    "type": config["eventtype"],
                    "edition": config["edition"],
                    "start": compstart.isoformat(),
                }
            )
        elif flask.request.args.get("forcephase", None) == "offseason":
            return json.dumps({"status": "offseason"})
    else:
        compstart = datetime.datetime.strptime(config["compstart"], "%d.%m.%Y %H:%M")
        compend = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M")
    if compstart <= datetime.datetime.now() <= compend:
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
    elif compstart - datetime.timedelta(days=30) < datetime.datetime.now() <= compstart:
        return json.dumps(
            {
                "status": "pre",
                "type": config["eventtype"],
                "edition": config["edition"],
                "start": compstart.isoformat(),
            }
        )
    return json.dumps({"status": "offseason"})


@app.route("/events", methods=["GET", "POST"])
@jwt_required(optional=True)
def get_events():
    log_access("/events - GET", bool(current_user))
    mdb = MiscDBOperators(config, secrets)
    if flask.request.method == "POST":
        if flask.request.json.get("visibility", None) == "true":
            if not current_user or not current_user.is_admin():
                # user is not an admin and can bugger off.
                log_access("unauthorized admin operation!")
                return "Not authorized. Your actions will have consequences.", 401
            return (
                json.dumps(mdb.get_events(include_ids=True, include_visibility=True)),
                200,
            )
    return json.dumps(mdb.get_events()), 200


@app.route("/pb/<event>")
@jwt_required()
def get_user_pbs(event: str):
    log_access(f"/pb/{event} - GET", bool(current_user))

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://api.kacky.gg/records/pb/{login}/{event}")
    if not r.ok:
        flask.jsonify("An Error occured"), 400
    return r.text


@app.route("/performance/<event>")
@jwt_required()
def get_user_performance(event: str):
    log_access(f"/performance/{event} - GET", bool(current_user))

    check_event_edition_legal(event, "1")
    um = UserDataMngr(config, secrets)
    if event == "kk":
        login = um.get_tmnf_login(current_user.get_id())
    else:
        login = um.get_tm20_login(current_user.get_id())
    r = requests.get(f"https://api.kacky.gg/records/performance/{login}/{event}")
    if not r.ok:
        flask.jsonify("An Error occured"), 400
    return r.text


@app.route("/event/<login>/finned")
def get_finished_maps_event(login: str):
    assert isinstance(login, str)
    log_access(f"/event/{login}/finned - GET", bool(current_user))

    r = requests.get(
        f"https://api.kacky.gg/records/pb/{login}/{config['eventtype']}/{config['edition']}"
    )
    scores = {
        k: v for k, v in r.json().items() if int(MAPIDS[0]) <= int(k) <= int(MAPIDS[1])
    }
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
    assert isinstance(login, str)
    log_access(f"/event/{login}/unfinned - GET", bool(current_user))

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
    assert isinstance(login, str)
    logger.info("get_next_unfinned_event - GET")
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
    return json.dumps(wrs_nicked)


@app.route("/event/nextrun/<kacky_id>")
def get_next_map_run(kacky_id):
    try:
        int(kacky_id)
    except ValueError:
        return "Bad Kacky ID", 400
    if not MAPIDS[0] <= int(kacky_id) <= MAPIDS[1]:
        return "Bad Kacky ID", 400
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
    log_access("/manage/events - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return "Not authorized. Your actions will have consequences.", 401
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
            return "Invalid date format!", 400
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
                    f"{flask.request.json['create']['name']}{flask.request.json['create']['edition']} already exists!",
                    400,
                )
            elif ret_code == -2:
                return f"{flask.request.json['create']['edition']} already exists!", 400
            elif ret_code == -3:
                return (
                    "There already are maps in the pool with the Kacky IDs you provided!",
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
    log_access("/manage/maps - POST", bool(current_user))
    if not current_user.is_admin():
        # user is not an admin and can bugger off.
        log_access("unauthorized admin operation!")
        return "Not authorized. Your actions will have consequences.", 401
    from kacky_eventpage_backend.process_maps_file import process_maps

    logger.debug("processing file")
    logger.debug(flask.request.files.keys())
    if flask.request.files["file"]:
        processing_res = process_maps(flask.request.files["file"])
        logger.debug(f"processing_res: {processing_res}")
        if processing_res == -1:
            # missing required columns
            return "Missing required columns", 422
        if processing_res == -2:
            # not all values for required columns are set
            return "Values for required columns must be set at all times!", 422
        if processing_res == -3:
            # unknown columns were provided
            return "Unknown columns", 422

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
                "Your action would overwrite already existing maps! You may set 'overwrite' to 1",
                409,
            )
        if update_res == 200:
            # success
            logger.debug("sucess")
            return "Updated maps.", 200
        return flask.jsonify(flask_restful.http_status_message(update_res)), update_res
    else:
        logger.debug("missing file")
        return "Missing file", 400


@app.route("/")
def ind():
    return "nothing to see here, go awaiii"


@app.route("/who_am_i", methods=["GET"])
@jwt_required()
def protected():
    return flask.jsonify(name=current_user.username, id=current_user.get_id())


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
    return {"isAdmin": identity.is_admin()}


@jwt_required()
def return_bad_value(error_param: str):
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
    check_castable: bool
        If value is not of type dtype, check if casting is possible
    Returns
    -------
    bool
        True if value is invalid according to parameters
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
# build numbers, ignoring potential '[vX]'s
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
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

if datetime.datetime.now() < datetime.datetime.strptime(
    config["compend"], "%d.%m.%Y %H:%M"
):
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
