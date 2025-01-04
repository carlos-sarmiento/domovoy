FROM python:3.13

WORKDIR /usr/src/app

COPY docker_requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY domovoy ./domovoy

ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONPATH /usr/src/app:${PYTHONPATH}

WORKDIR /config

CMD [ "python", "/usr/src/app/domovoy/cli.py", "--config", "/config/config.yml" ]