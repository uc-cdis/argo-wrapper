ARG AZLINUX_BASE_VERSION=master

FROM 707767160287.dkr.ecr.us-east-1.amazonaws.com/gen3/python-build-base:${AZLINUX_BASE_VERSION} AS base
# FROM quay.io/cdis/python-build-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=argowrapper

FROM base AS builder

WORKDIR /$appname

# Use virtualenvs.in-project to remove ambiguity about where Poetry creates the virtual environment,
# i.e. the virtualenv will be created under the `.venv` directory in the project folder:
COPY poetry.lock pyproject.toml /$appname/
RUN pip install --upgrade pip poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install --without dev --no-interaction --no-root

# Copy source code and perform dependency installation
COPY src /$appname/src
RUN poetry install --without dev --no-interaction

FROM base

# Copy the virtual environment and project files
COPY --from=builder /$appname/.venv /venv
COPY --from=builder /$appname /$appname

WORKDIR /$appname

COPY config.ini .
CMD ["gunicorn", "argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
