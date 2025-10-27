# Start from the buildbase image (which itself starts from Hardened)
FROM quay.io/cdis/amazonlinux-base:3.13-buildbase AS base

ENV appname=argowrapper

FROM base AS builder

WORKDIR /$appname

# Use virtualenvs. config to remove ambiguity about where Poetry creates the virtual environment,
# i.e. the virtualenv will be created under the `/venv` directory:
COPY poetry.lock pyproject.toml /$appname/
RUN pip install --upgrade pip poetry \
    && poetry config virtualenvs.create true \
    && poetry config virtualenvs.path /venv \
    && poetry install -vv --no-root --only main --no-interaction

# Copy source code and perform dependency installation
COPY src /$appname/src
RUN poetry install --without dev --no-interaction

FROM base

# Copy the virtual environment and project files
COPY --from=builder /venv /venv
COPY --from=builder /$appname /$appname

# Switch to the mandatory non-root user 
# (user 'gen3' with UID 1000 is created in the base image)
USER gen3

WORKDIR /$appname

COPY config.ini .
CMD ["gunicorn", "argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
