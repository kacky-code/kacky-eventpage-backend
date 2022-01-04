import datetime
import logging
import os

import flask
import yaml

from kacky_api_handler import KackyAPIHandler

app = flask.Flask(__name__)
config = {}


def get_pagedata():
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
    servernames = list(map(lambda s: s.name.html, api.servers.values()))
    timeplayed = list(map(lambda s: s.timeplayed, api.servers.values()))
    return servernames, curtimestr, curmaps, timeleft, timeplayed


def minutes_to_hourmin_str(minutes):
    minutes = int(minutes)
    return f"{int(minutes / 60):0>2d}", f"{minutes % 60:0>2d}"


def which_time_is_map_played(timestamp: datetime.datetime, findmapid: int):
    # Get page data
    servernames, curtimestr, curmaps, timeleft = get_pagedata()
    deltas = []
    timelimit = 10

    for idx, serv in enumerate(curmaps):
        # how many map changes are needed until map is juked?
        changes_needed = findmapid - serv
        if changes_needed < 0:
            changes_needed += MAPIDS[1] - MAPIDS[0] + 1
        minutes_time_to_juke = int(changes_needed * (timelimit + config["mapchangetime_s"] / 60))
        # date and time, when map is juked next (without compensation of minutes)
        play_time = timestamp + datetime.timedelta(minutes=minutes_time_to_juke)
        deltas.append((minutes_to_hourmin_str(minutes_time_to_juke), servernames[idx]))
    return deltas


@app.route('/')
def index():  # put application's code here
    global config
    # Log visit (only for counting, no further info). Quite GDPR conform, right?
    with open(config["visits_logfile"], "a") as vf:
        vf.write(datetime.datetime.now().strftime("%d/%m/%y %H:%M"))
        vf.write("\n")

    # Get page data
    servernames, curtimestr, curmaps, timeleft,timeplayed = get_pagedata()
    serverinfo = list(zip(servernames, curmaps, timeplayed))
    return flask.render_template('index.html',
                                 servs=serverinfo,
                                 curtime=curtimestr,
                                 timeleft=timeleft)


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed
    :return:
    """
    # Get page data
    servernames, curtimestr, curmaps, timeleft = get_pagedata()
    search_map_id = flask.request.form['map']
    serverinfo = list(zip(servernames, curmaps))
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
    # input seems ok, try to find next time map is played
    deltas = which_time_is_map_played(datetime.datetime.now(), search_map_id)

    return flask.render_template('index.html',
                                 servs=serverinfo,
                                 curtime=curtimestr,
                                 searched=True, searchtext=search_map_id,
                                 timeleft=timeleft,
                                 deltas=deltas)


@app.route('/stats')
def stats():
    global config
    if config["enable_stats_page"]:
        return flask.Flask.render_template('stats.html')
    else:
        return flask.Flask.render_template("error.html", error="Stats page disabled")

#                    _
#                   (_)
#    _ __ ___   __ _ _ _ __
#   | '_ ` _ \ / _` | | '_ \
#   | | | | | | (_| | | | | |
#   |_| |_| |_|\__,_|_|_| |_|
#
# Reading config file
with open(os.path.join(os.path.dirname(__file__), "config.yaml"),
          "r") as conffile:
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
    f = open(config["logfile"], "w+")
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
    f = open(config["visits_logfile"], "a+")
    f.close()

logger.info("Starting application.")
app.run(debug=True, host=config["bind_hosts"], port=config["port"])
