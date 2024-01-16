import logging

import flask
import requests
from flask import Blueprint

from kacky_eventpage_backend import secrets

records_api_proxy_blueprint = Blueprint("records_api_proxy", __name__)
headers = {"X-ApiKey": secrets["records_api_key"]}
logger = logging.getLogger("KKmaptimes")


# @records_api_proxy_blueprint.route("/wrs/<event>/<edition>")
# @records_api_proxy_blueprint.route("/pb/<user>/<eventtype>")
# @records_api_proxy_blueprint.route("/pb/<user>/<eventtype>/<edition>")
# @records_api_proxy_blueprint.route("/performance/<login>/<eventtype>")
# @records_api_proxy_blueprint.route("/event/leaderboard/<eventtype>/<edition>")
# @records_api_proxy_blueprint.route("/event/leaderboard/<eventtype>/<edition>/<login>")
# @records_api_proxy_blueprint.route("/leaderboard/<eventtype>/<kacky_id>")
# def wrs_event_edition(event="", edition=-1, user="", eventtype="", login="", kacky_id=-9999):


@records_api_proxy_blueprint.route("/records", defaults={"path": ""})
@records_api_proxy_blueprint.route("/records/<string:path>")
@records_api_proxy_blueprint.route("/records/<path:path>")
def proxy(path=""):
    log_access(flask.request.full_path)
    r = requests.get(
        f"https://records.kacky.gg{flask.request.full_path[8:]}", headers=headers
    )
    try:
        return flask.jsonify(r.json()), r.status_code
    except Exception:
        return flask.jsonify(r.text), r.status_code


def log_access(route: str, logged_in: bool = False):
    logger.info(
        f"{route} accessed by "
        f"{flask.request.headers.get('X-Forwarded-For', 'unknown-forward')}. "
        f"User status: {logged_in}"
    )
