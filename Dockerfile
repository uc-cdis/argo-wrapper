ARG AZLINUX_BASE_VERSION=master

FROM 707767160287.dkr.ecr.us-east-1.amazonaws.com/gen3/python-build-base:${AZLINUX_BASE_VERSION} as base
# FROM quay.io/cdis/python-build-base:${AZLINUX_BASE_VERSION} as base

ENV appname=argowrapper
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1
ENV PATH="/venv/bin:$PATH"
ENV VIRTUAL_ENV="/venv"

FROM base as builder

WORKDIR /$appname

COPY poetry.lock pyproject.toml /$appname/
RUN pip install --upgrade poetry \
    && poetry install --without dev --no-interaction

COPY src /$appname/src
RUN poetry install --without dev --no-interaction

FROM base

COPY --from=builder /venv /venv
COPY --from=builder /$appname /$appname

WORKDIR /$appname

COPY config.ini .
CMD ["gunicorn", "argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
