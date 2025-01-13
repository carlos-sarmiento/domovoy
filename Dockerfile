FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /usr/src/app

COPY pyproject.toml uv.lock README.md  ./

COPY domovoy ./domovoy

RUN uv sync --frozen

CMD [ "uv", "run", "domovoy/cli.py", "--config", "/config/config.yml" ]