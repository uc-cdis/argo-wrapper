ARG AZLINUX_BASE_VERSION=master

# FROM 707767160287.dkr.ecr.us-east-1.amazonaws.com/gen3/python-build-base:${AZLINUX_BASE_VERSION} AS base
FROM quay.io/cdis/python-build-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=argowrapper

FROM base AS builder

WORKDIR /$appname

# Only install dependencies.
COPY poetry.lock pyproject.toml /$appname/
RUN pip install --upgrade pip poetry \
    && poetry install --without dev --no-interaction --no-root

# Copy source code and install the app itself.
COPY src /$appname/src
RUN poetry install --without dev --no-interaction

FROM base

COPY --from=builder /venv /venv
COPY --from=builder /$appname /$appname

WORKDIR /$appname

COPY config.ini .
CMD ["gunicorn", "argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
