FROM python:3.8.12-alpine as base

FROM base as builder
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev make postgresql-dev git curl
RUN pip install --upgrade pip
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
COPY . /src/
WORKDIR /src
RUN apk --no-cache add git && python -m venv /env && . /env/bin/activate && pip install --upgrade pip && $HOME/.poetry/bin/poetry install --no-dev --no-interaction && pip install git+https://github.com/argoproj/argo-workflows@master#subdirectory=sdks/python/client

FROM base
RUN apk add --no-cache postgresql-libs
COPY --from=builder /env /env
COPY --from=builder /src /src
WORKDIR /src
CMD ["/env/bin/gunicorn", "src.argo-wrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8
#CMD ["sleep", "100000"]
