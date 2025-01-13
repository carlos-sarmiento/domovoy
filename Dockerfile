FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /usr/src/app

COPY pyproject.toml uv.lock README.md  ./

RUN uv pip install --system -r pyproject.toml

COPY domovoy ./domovoy

RUN uv pip install --system -e .

WORKDIR /config

CMD [ "uv", "run", "/usr/src/app/domovoy/cli.py", "--config", "/config/config.yml" ]