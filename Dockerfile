FROM quay.io/cdis/python:3.10-alpine-master as base

FROM base as builder
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev make postgresql-dev git curl
RUN pip install --upgrade pip
COPY . /src/
WORKDIR /src
RUN apk --no-cache add git \
    && python -m venv /env \
    && . /env/bin/activate \
    && pip install --upgrade pip poetry \
    && poetry install --no-dev --no-interaction

FROM base
RUN apk add --no-cache postgresql-libs
COPY --from=builder /env /env
COPY --from=builder /src /src
WORKDIR /src
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8
CMD ["/env/bin/gunicorn", "src.argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
#CMD ["sleep", "100000"]
