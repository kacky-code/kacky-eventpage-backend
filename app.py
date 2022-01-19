import datetime
import hashlib
import json
import logging
import os
from pathlib import Path

import flask
import yaml

from db_ops.alarm_checker import AlarmChecker
from kacky_api_handler import KackyAPIHandler
from usermanagement.usermanager import UserMngr

app = flask.Flask(__name__)
config = {}


def get_pagedata(rawservernum=False):
    curtime = datetime.datetime.now()
    curtimestr = f"{curtime.hour:0>2d}:{curtime.minute:0>2d}"
    api = KackyAPIHandler(config)
    api.get_mapinfo()
    curmaps = list(map(lambda s: s.cur_map, api.servers.values()))
    ttl = datetime.datetime.strptime(config["compend"],
                                     "%d.%m.%Y %H:%M") - curtime
    if ttl.days < 0 or ttl.seconds < 0:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),
                    abs(int(ttl.seconds // 60) % 60), -1)
    else:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),
                    abs(int(ttl.seconds // 60) % 60), 1)
    if rawservernum:
        servernames = list(map(lambda s: s.name.string.split(" - ")[1], api.servers.values()))
    else:
        servernames = list(map(lambda s: s.name.html, api.servers.values()))
    timeplayed = list(map(lambda s: s.timeplayed, api.servers.values()))
    jukebox = list(map(lambda s: s.playlist.get_playlist_from_now(), api.servers.values()))
    timelimits = list(map(lambda s: s.timelimit, api.servers.values()))
    serverinfo = list(zip(servernames, curmaps, timeplayed, jukebox, timelimits))
    return serverinfo, curtimestr, timeleft


def check_login(cookie: str):
    """

    Parameters
    ----------
    cookie : str
        Cookie with login info, as read by Flask

    Returns
    -------
    Union(str, bool)
        "bad_cookie", if cookie cannot be processed
        True/False, depending on login info validity when cookie can be processed
    """
    try:
        cookie_usercreds = json.loads(cookie)
    except (json.JSONDecodeError, TypeError):
        # cookie cannot be read
        return "bad_cookie"
    um = UserMngr(config)
    # True/False, if login is legit
    return um.login(cookie_usercreds["user"], cookie_usercreds["h"])


@app.route('/')
def index():  # put application's code here
    global config
    # Log visit (only for counting, no further info). Quite GDPR conform, right?
    with open(Path(__file__).parent / config["visits_logfile"], "a") as vf:
        vf.write(datetime.datetime.now().strftime("%d/%m/%y %H:%M"))
        vf.write("\n")

    # check if user is logged in
    res = check_login(flask.request.cookies.get("kkkeks"))

    # Get page data
    serverinfo, curtimestr, timeleft = get_pagedata()

    if res and res != "bad_cookie":
        # user logged in
        loginname = json.loads(flask.request.cookies.get("kkkeks"))["user"]
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     timeleft=timeleft,
                                     loginname=loginname
                                     )
    else:
        # user not logged in
        response = flask.make_response(flask.render_template('index.html',
                                                             servs=serverinfo,
                                                             curtime=curtimestr,
                                                             timeleft=timeleft
                                                             )
                                       )
        if res == "bad_cookie":
            response.set_cookie("kkkeks", '', expires=0)
        return response


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed
    :return:
    """
    # Get page data
    serverinfo, curtimestr, timeleft = get_pagedata()
    search_map_id = flask.request.form['map']
    # check if input is integer
    try:
        search_map_id = int(search_map_id)
    except ValueError:
        # input is not a integer, return error message
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     searched=True, badinput=True,
                                     timeleft=timeleft)
    # check if input is in current map pool
    if search_map_id < MAPIDS[0] or search_map_id > MAPIDS[1]:
        # not in current map pool
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     searched=True, badinput=True,
                                     timeleft=timeleft)

    api = KackyAPIHandler(config)
    api.get_mapinfo()
    # input seems ok, try to find next time map is played
    deltas = list(map(lambda s: s.find_next_play(search_map_id), api.servers.values()))
    # remove all None from servers which do not have map
    deltas = [i for i in deltas if i[0]]

    return flask.render_template('index.html',
                                 servs=serverinfo,
                                 curtime=curtimestr,
                                 searched=True, searchtext=search_map_id,
                                 timeleft=timeleft,
                                 deltas=deltas)


@app.route('/login', methods=['POST'])
@app.route('/register', methods=['POST'])
def show_login_page_on_button():
    um = UserMngr(config)
    if flask.request.path == "/login":
        # user wants to login
        cryptpw = hashlib.sha256(flask.request.form["login_pwd"].encode()).hexdigest()
        res = um.login(flask.request.form["login_usr"], cryptpw)
        if res:
            tm_login = um.get_tm_login(flask.request.form["login_usr"])
            #response = flask.make_response(flask.render_template('login.html', mode="l", state=True, loginname=flask.request.form["login_usr"]))
            response = flask.redirect("/")
            response.set_cookie("kkkeks", json.dumps({"user": flask.request.form["login_usr"],
                                                      "h": cryptpw, "tm_login": tm_login}))
            return response
        else:
            return "Login failed! Check username and pwd!"
    else:
        # user wants to register
        cryptpw = hashlib.sha256(flask.request.form["reg_pwd"].encode()).hexdigest()
        cryptmail = hashlib.sha256(flask.request.form["reg_mail"].encode()).hexdigest()
        res = um.add_user(flask.request.form["reg_usr"], cryptpw, cryptmail)
        if res:
            from flask import url_for
            return flask.render_template("login.html", mode="tmp")
        else:
            return "Registration failed! Username already exists!"


@app.route('/login')
@app.route('/register')
def show_login_page():
    res = check_login(flask.request.cookies.get("kkkeks"))
    if res == "bad_cookie":
        if flask.request.path == "/login":
            # user wants to login
            return flask.render_template('login.html', mode="l")
        else:
            # user wants to register
            return flask.render_template('login.html', mode="r")
    elif res:
        return flask.render_template('login.html', mode="l", state=True, loginname=json.loads(flask.request.cookies.get("kkkeks"))["user"])
    else:
        response = flask.make_response(flask.render_template('login.html', mode="l", state=False))
        response.set_cookie("kkkeks", json.dumps({"user": "", "h": ""}), expires=0)
        return response


@app.route('/user')
def show_user_page():
    res = check_login(flask.request.cookies.get("kkkeks"))
    if res == "bad_cookie" or not res:      # if bad cookie or bad login in cookie
        return flask.render_template("error.html", error="What are you doing here? You are not logged in!")
    elif res:
        um = UserMngr(config)
        username = json.loads(flask.request.cookies.get("kkkeks"))["user"]
        discord_id = um.get_discord_id(username)
        tm_login = um.get_tm_login(username)
        ac = AlarmChecker(config)
        alarms = ac.get_alarms_for_user(username)
        maplist = list(map(lambda m: str(m), range(MAPIDS[0], MAPIDS[1])))
        return flask.render_template('user.html',
                                     username=username,
                                     maplist=maplist,
                                     useralarms=alarms,
                                     discord_id=discord_id,
                                     tm_login=tm_login,
                                     alarm_enabled=True if discord_id != "" else False,
                                     loginname=username
                                     )
    else:
        # TODO: Delete cookie here
        return flask.render_template("error.html", error="Something went wrong on the user page, idk. Do :prayge:")


@app.route('/user', methods=['POST'])
def show_user_page_on_button():
    res = check_login(flask.request.cookies.get("kkkeks"))
    maplist = list(map(lambda m: str(m), range(MAPIDS[0], MAPIDS[1])))
    if res == "bad_cookie" or not res:      # if bad cookie or bad login in cookie
        return flask.render_template("error.html", error="You Login-Info in cookies is bad. "
                                                         "Please clear cookies for this page!")
        # TODO: Delete cookie here
    elif res:
        um = UserMngr(config)
        username = json.loads(flask.request.cookies.get("kkkeks"))["user"]
        if flask.request.form["user_save"] == "discord_id":
            # user clicked button to save discord ID
            um.set_discord_id(username, flask.request.form["discord_id"])
            return flask.redirect('/user')
        elif flask.request.form["user_save"] == "tm_id":
            # user clicked button to save tm login
            um.set_tm_login(username, flask.request.form["tm_id"])
            response = flask.make_response(flask.redirect('/user'))
            response.set_cookie("kkkeks", json.dumps({"user": username,
                                                      "h": json.loads(flask.request.cookies.get("kkkeks"))["h"],
                                                      "tm_login": flask.request.form["tm_id"]}))
            return response
        elif flask.request.form["user_save"] == "alarms":
            # user clicked button to save alarms
            selected_maps = flask.request.form.getlist("alarm_selector")
            ac = AlarmChecker(config)
            ac.set_alarms_for_user(username, selected_maps)
            return flask.redirect('/user')
    else:
        return flask.render_template("error.html", error="Something went wrong on the user page, idk. Do :prayge:")
        # TODO: Delete cookie here


@app.route('/stats')
def stats():
    global config
    if config["enable_stats_page"]:
        return flask.Flask.render_template('stats.html')
    else:
        return flask.Flask.render_template("error.html", error="Stats page disabled")


@app.route('/data.json')
def json_data_provider():
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


#                    _
#                   (_)
#    _ __ ___   __ _ _ _ __
#   | '_ ` _ \ / _` | | '_ \
#   | | | | | | (_| | | | | |
#   |_| |_| |_|\__,_|_|_| |_|
#
# Reading config file
with open(Path(__file__).parent / "config.yaml", "r") as conffile:
    config = yaml.load(conffile, Loader=yaml.FullLoader)

MAPIDS = (config["min_mapid"], config["max_mapid"])

if config["logtype"] == "STDOUT":
    pass
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# YES, this totally ignores threadsafety. On the other hand, it is quite safe to assume that it only will
# occur very rarely that things get logged at the same time in this usecase.
# Furthermore, logging is absolutely not critical in this case and mostly used for debugging. As long as the
# SQLite DB doesn't break, we're safe!
elif config["logtype"] == "FILE":
    config["logfile"] = config["logfile"].replace("~", os.getenv("HOME"))
    if not os.path.dirname(config["logfile"]) == "" and not os.path.exists(
            os.path.dirname(config["logfile"])):
        os.mkdir(os.path.dirname(config["logfile"]))
    f = open(os.path.join(os.path.dirname(__file__), config["logfile"]), "w+")
    f.close()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=config["logfile"])
else:
    print("ERROR: Logging not correctly configured!")
    exit(1)

# Set up logging
logger = logging.getLogger(config["logger_name"])
logger.setLevel(eval("logging." + config["loglevel"]))

if config["log_visits"]:
    # Enable logging of visitors to dedicated file. More comfortable than using system log to count visitors.
    # Counting with "cat visits.log | wc -l"
    f = open(os.path.join(os.path.dirname(__file__), config["visits_logfile"]), "a+")
    f.close()

logger.info("Starting application.")
app.run(debug=True, host=config["bind_hosts"], port=config["port"])
