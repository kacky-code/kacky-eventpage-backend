# rename import as gunicorn das internal `config` module
from src.kacky_eventpage_backend import config as conf

workers = conf["workers"]
threads = conf["threads"]
bind = f"{conf['bind_hosts']}:{conf['port']}"
wsgi_app = "kacky_eventpage_backend.app:app"
