FROM quay.io/cdis/python:3.10-slim-buster

ENV appname=src

RUN pip install --no-cache-dir --upgrade pip poetry==1.3.2

WORKDIR /$appname

# copy ONLY poetry artifact, install the dependencies but not indexd
# this will make sure than the dependencies is cached
COPY poetry.lock pyproject.toml /$appname/
RUN poetry config virtualenvs.create false \
    && poetry install -vv --no-root --only main --no-interaction \
    && poetry show -v

# copy source code ONLY after installing dependencies
COPY . /$appname

# install argo-wrapper
RUN poetry config virtualenvs.create false \
    && poetry install -vv --only main --no-interaction \
    && poetry show -v

CMD ["/env/bin/gunicorn", "src.argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
