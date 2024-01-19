FROM python:3.12.1-bookworm as builder
LABEL authors="corkscrew"
LABEL name="eventpage_backend_builder_image"
WORKDIR /eventpage_backend
COPY setup.cfg .
RUN python -m venv venv
# Install required dependencies so updating code can reuse this layer
RUN /eventpage_backend/venv/bin/python3 -c "import configparser; c = configparser.ConfigParser(); c.read('setup.cfg'); print(c['options']['install_requires'])" | xargs pip install

FROM builder
LABEL authors="corkscrew"
LABEL name="eventpage_backend"
# Copies current setup.cfg into image
COPY . .
# Missing dependencies from builder image will get installed
RUN /eventpage_backend/venv/bin/pip install .

CMD ["/eventpage_backend/venv/bin/gunicorn", "-c", "/eventpage_backend/gunicorn.conf.py"]
EXPOSE 5005
