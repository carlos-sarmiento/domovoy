#! /bin/sh

poetry export > docker_requirements.txt

docker build --no-cache -t domovoy:latest .

rm docker_requirements.txt