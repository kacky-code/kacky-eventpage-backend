import yaml

with open("config.yaml", "r") as c:
    conffile = yaml.load(c, yaml.FullLoader)

workers = conffile["workers"]
bind = f"{conffile['bind_hosts']}:{conffile['port']}"
wsgi_app = "kacky_eventpage_backend.app:app"
