FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /usr/src/app

COPY pyproject.toml uv.lock README.md  ./

COPY domovoy ./domovoy

RUN uv sync --frozen

WORKDIR /config

CMD [ "uv", "run", "/usr/src/app/domovoy/cli.py", "--project", "/usr/src/app/", "--config", "/config/config.yml" ]