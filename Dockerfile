FROM quay.io/cdis/python:3.10-alpine-master as base

FROM base as builder
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev make postgresql-dev git curl
RUN pip install --upgrade pip
COPY pyproject.toml /src/pyproject.toml
COPY poetry.lock /src/poetry.lock
WORKDIR /src
RUN python -m venv /env \
    && . /env/bin/activate \
    && pip install --upgrade pip poetry==1.3.2 \
    && poetry install --without dev --no-interaction

# include code and run poetry again (this split allows for faster local builds when changing code and using docker cache):
COPY src /src/src
RUN . /env/bin/activate \
    && poetry install --without dev --no-interaction

FROM base
RUN apk add --no-cache postgresql-libs
COPY --from=builder /env /env
COPY --from=builder /src /src
WORKDIR /src
COPY config.ini .
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8
CMD ["/env/bin/gunicorn", "src.argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
#CMD ["sleep", "100000"]
