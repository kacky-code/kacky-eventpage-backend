import datetime
import hashlib
import json
import logging
import os
from pathlib import Path

import flask
import flask_login
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
import yaml

from db_ops.alarm_checker import AlarmChecker
from kacky_api_handler import KackyAPIHandler
from usermanagement.user_operations import UserDataMngr
from usermanagement.user_session_handler import User

app = flask.Flask(__name__)
# Create LoginManager for user stuff
login_manager = LoginManager()
login_manager.init_app(app)
config = {}


def get_pagedata(rawservernum=False):
    """
    Loads and prepares data shown on index page

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


@app.route('/')
def index():  # put application's code here
    """
    Handler for the index page route

    Returns
    -------

    """
    global config

    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    # Log visit (only for counting, no further info). Quite GDPR conform, right?
    with open(Path(__file__).parent / config["visits_logfile"], "a") as vf:
        vf.write(datetime.datetime.now().strftime("%d/%m/%y %H:%M"))
        vf.write("\n")

    # check if user is logged in
    res = check_user_logged_in()

    # Get page data
    serverinfo, curtimestr, timeleft = get_pagedata()

    if res:
        # user logged in
        loginname = current_user.get_id()
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     timeleft=timeleft,
                                     loginname=loginname,
                                     finlist=build_fin_json()
                                     )
    else:
        # user not logged in
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     timeleft=timeleft
                                     )


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed

    Returns
    -------

    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    # check if user is logged in
    res = check_user_logged_in()
    if res and res != "bad_cookie":
        # user logged in
        loginname = current_user.get_id()
    else:
        loginname = None

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
                                     timeleft=timeleft,
                                     loginname=loginname,
                                     finlist=build_fin_json()
                                     )
    # check if input is in current map pool
    if search_map_id < MAPIDS[0] or search_map_id > MAPIDS[1]:
        # not in current map pool
        return flask.render_template('index.html',
                                     servs=serverinfo,
                                     curtime=curtimestr,
                                     searched=True, badinput=True,
                                     timeleft=timeleft,
                                     loginname=loginname,
                                     finlist=build_fin_json()
                                     )

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
                                 deltas=deltas,
                                 loginname=loginname,
                                 finlist=build_fin_json()
                                 )


@app.route('/login', methods=['POST'])
@app.route('/register', methods=['POST'])
def show_login_page_on_button():
    """
    Handle data submitted in the login & register forms

    Returns
    -------
    Union[str, flask.Response]
        Either a page itself or forward to some page

    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    udm = UserDataMngr(config)
    user = User(flask.request.form["login_usr"], config)
    if flask.request.path == "/login":
        # user wants to login
        cryptpw = hashlib.sha256(flask.request.form["login_pwd"].encode()).hexdigest()
        res = user.login(flask.request.form["login_usr"], cryptpw)
        if res:
            if "forward" in flask.request.args:
                # user tried to access a page but was not logged in. Change redirect target
                response = flask.redirect(flask.request.args["forward"])
            else:
                response = flask.redirect("/")
            login_user(user)
            return response
        else:
            return "Login failed! Check username and pwd!"
    else:
        # user wants to register
        if flask.request.form["reg_pwd"] != flask.request.form["reg_pwd_confirm"]:
            return flask.render_template("error.html", error="Try again with matching passwords ;)\n\n\n\n\n"
                                                             "Ignore the next line.")
        cryptpw = hashlib.sha256(flask.request.form["reg_pwd"].encode()).hexdigest()
        cryptmail = hashlib.sha256(flask.request.form["reg_mail"].encode()).hexdigest()
        res = udm.add_user(flask.request.form["reg_usr"], cryptpw, cryptmail)
        if res:
            flask.flash("Account created! Please log in now!")
            return flask.redirect(flask.url_for("_login"))
        else:
            return flask.render_template("error.html", error="Registration failed! Username already exists!")


@app.route('/login', endpoint="_login")
@app.route('/register', endpoint="_register")
def show_login_page():
    """
    Provides the login & register page

    Returns
    -------
    Union[str, flask.Response]
        Either some page or a redirect

    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    res = check_user_logged_in()
    # user is not logged in
    if not check_user_logged_in():
        if flask.request.path == "/login":
            if "forward" in flask.request.args:
                # user tried accessing a blocked page. let them log in and forward them
                return flask.render_template('login.html', mode="l", forward=flask.request.args["forward"])
            # user wants to login
            return flask.render_template('login.html', mode="l")
        else:
            # user wants to register
            return flask.render_template('login.html', mode="r")
    # user is already logged in
    elif res:
        return flask.render_template('login.html', mode="l", state=True,
                                     loginname=current_user.get_id())
    else:
        # should never happen, but for good measure, log out user and show login page
        return flask.redirect(flask.url_for("logout"))


@app.route('/user')
@login_required
def show_user_page():
    """
    Shows the user page

    Returns
    -------
    str
        The user page
    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    res = check_user_logged_in()
    if not res:  # if bad cookie or bad login in cookie
        return flask.render_template("error.html", error="What are you doing here? You are not logged in!")
    elif res:
        udm = UserDataMngr(config)
        username = current_user.get_id()
        discord_id = udm.get_discord_id(username)
        udm = UserDataMngr(config)
        tm_login = udm.get_tm_login(username)
        ac = AlarmChecker(config)
        alarms = ac.get_alarms_for_user(username)
        maplist = list(map(lambda m: str(m), range(MAPIDS[0], MAPIDS[1] + 1)))
        return flask.render_template('user.html',
                                     username=username,
                                     maplist=maplist,
                                     useralarms=alarms,
                                     discord_id=discord_id,
                                     tm_login=tm_login,
                                     alarm_enabled=True if discord_id != "" else False,
                                     loginname=username,
                                     finlist=build_fin_json()
                                     )
    else:
        # TODO: Delete cookie here
        return flask.render_template("error.html", error="Something went wrong on the user page, idk. Do :prayge:")


@app.route('/user', methods=['POST'])
@login_required
def show_user_page_on_button():
    """
    Updates the user page and stores new data in the DB

    Returns
    -------
    Union[str, flask.Response]
        The user page

    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    res = check_user_logged_in()
    maplist = list(map(lambda m: str(m), range(MAPIDS[0], MAPIDS[1] + 1)))
    if not res:  # if not logged in
        return flask.render_template("error.html", error="Not logged in!")
    elif res:
        um = UserDataMngr(config)
        username = current_user.get_id()
        if flask.request.form["user_save"] == "discord_id":
            # user clicked button to save discord ID
            um.set_discord_id(username, flask.request.form["discord_id"])
            # return flask.redirect('user')
        elif flask.request.form["user_save"] == "tm_id":
            # user clicked button to save tm login
            um.set_tm_login(username, flask.request.form["tm_id"])
        elif flask.request.form["user_save"] == "alarms":
            # user clicked button to save alarms
            selected_maps = flask.request.form.getlist("alarm_selector")
            ac = AlarmChecker(config)
            ac.set_alarms_for_user(username, selected_maps)
            # return flask.redirect("user")
        ac = AlarmChecker(config)
        alarms = ac.get_alarms_for_user(username)
        discord_id = um.get_discord_id(username)
        tm_login = um.get_tm_login(username)
        response = flask.make_response(flask.render_template('user.html',
                                                             username=username,
                                                             maplist=maplist,
                                                             useralarms=alarms,
                                                             discord_id=discord_id,
                                                             tm_login=tm_login,
                                                             alarm_enabled=True if discord_id != "" else False,
                                                             loginname=username,
                                                             finlist=build_fin_json()
                                                             )
                                       )
        return response
    else:
        # logout to be safe, idk how we got here
        logout_user()
        return flask.render_template("error.html", error="Something went wrong on the user page, idk. Do :prayge:")


@app.route('/logout')
@login_required
def logout_and_redirect_index():
    """
    Logs out the user

    Returns
    -------
    flask.Response
        Redirect to the index page after logging out
    """
    logout_user()
    return flask.redirect("/")


@login_manager.unauthorized_handler
def unauthorized_callback():
    """
    HTTP 401 page

    Returns
    -------
    flask.Response
        Forward to login form
    """
    flask.flash("You are not logged in!")
    # return flask.render_template("login.html", mode="l")
    return flask.redirect(flask.url_for("_login", forward=flask.request.path))


@app.route('/stats')
def stats():
    """
    Can show basic visitor stats, when enabled in config.yaml

    Returns
    -------
    str
        Stats page
    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    global config
    if config["enable_stats_page"]:
        return flask.Flask.render_template('stats.html')
    else:
        return flask.Flask.render_template("error.html", error="Stats page disabled")


@app.route('/data.json')
def json_serverdata_provider():
    """
    "API" used by front end JS. Provides updated server information in JSON format.

    Returns
    -------
    str
        Data in JSON format as a string
    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

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


@app.route('/fin.json')
def json_fin_provider():
    """
    Provides the finished maps for a given TM login in JSON format. Data is built in build_fin_json, this
    is a wrapper to provide data in a dedicated route.

    Returns
    -------
    str
        list of fins in JSON string
    """
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        userip = flask.request.environ['REMOTE_ADDR']
    else:
        userip = flask.request.environ['HTTP_X_FORWARDED_FOR']  # if behind a proxy

    logger.info(f"Connection from {userip}")

    if not isinstance(current_user.get_id(), flask_login.AnonymousUserMixin):
        return build_fin_json()


def build_fin_json():
    """
    Provides the finished maps for a given TM login as Python dict.

    Returns
    -------
        Dict[str, Union[int, List[str]]]
    """
    try:
        um = UserDataMngr(config)
        tm_login = um.get_tm_login(current_user.get_id())
        if tm_login != "":
            fins = api.get_fin_info(tm_login)["finishes"]
            mapids = list(map(lambda m: int(m), api.get_fin_info(tm_login)["mapids"]))
            return {"finishes": fins, "mapids": mapids}
        else:
            return {"finishes": 0, "mapids": []}
    except Exception:
        return {"finishes": 0, "mapids": []}


@login_manager.user_loader
def load_user(username):
    """
    user_loader as required for flask_login

    Parameters
    ----------
    username: str
        Parameter to generate the UID in the user object

    Returns
    -------
    User
        User object, inheriting from flask_login.UserMixin
    """
    return User(username, config)


def check_user_logged_in():
    """
    Returns whether the user is logged in

    Returns
    -------
    bool
        True when user is logged in, False else
    """
    if isinstance(current_user, flask_login.AnonymousUserMixin):
        # no user currently logged in
        return False
    return User(current_user, config).is_authenticated()


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

# Read flask secret (required for flask.flash and flask_login)
with open(Path(__file__).parent / "secrets.yaml", "r") as secfile:
    secrets = yaml.load(secfile, Loader=yaml.FullLoader)
    app.secret_key = secrets["flask_secret"]
    del secrets

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

api = KackyAPIHandler(config)

# Set up logging
logger = logging.getLogger(config["logger_name"])
logger.setLevel(eval("logging." + config["loglevel"]))

if config["log_visits"]:
    # Enable logging of visitors to dedicated file. More comfortable than using system log to count visitors.
    # Counting with "cat visits.log | wc -l"
    f = open(os.path.join(os.path.dirname(__file__), config["visits_logfile"]), "a+")
    f.close()

logger.info("Starting application.")
# app.run(debug=True, host=config["bind_hosts"], port=config["port"])
app.run(host=config["bind_hosts"], port=config["port"])
