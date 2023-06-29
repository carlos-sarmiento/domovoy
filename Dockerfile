FROM python:3.11

WORKDIR /usr/src/app

COPY docker_requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY domovoy ./domovoy

ENV PYTHONPATH /usr/src/app:${PYTHONPATH}

CMD [ "python", "/usr/src/app/domovoy/cli.py", "--config", "/config/config.yml" ]