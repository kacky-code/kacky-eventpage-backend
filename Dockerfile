FROM python:3.12.1-bookworm
LABEL authors="corkscrew"
LABEL name="eventpage_backend"

WORKDIR /eventpage_backend
COPY . .
RUN python -m venv venv
# Install required dependencies so updating code can reuse this layer
RUN python3 -c "import configparser; c = configparser.ConfigParser(); c.read('setup.cfg'); print(c['options']['install_requires'])" | xargs pip install
RUN /eventpage_backend/venv/bin/pip install .

CMD ["/eventpage_backend/venv/bin/gunicorn", "-c", "/eventpage_backend/gunicorn.conf.py"]
EXPOSE 5005