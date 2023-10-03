FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal as base

ENV appname=argowrapper

FROM base as builder
RUN dnf install -y python3 python3-pip \
    && dnf clean all \
    && rm -rf /var/cache/yum/

WORKDIR /$appname

# copy ONLY poetry artifact, install the dependencies but not indexd
# this will make sure than the dependencies is cached

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY poetry.lock pyproject.toml /$appname/
RUN pip install --upgrade poetry \
    && poetry install --without dev --no-interaction

COPY src /$appname/src
RUN poetry install --without dev --no-interaction

FROM base

RUN dnf install -y python3 python3-pip \
    && dnf clean all \
    && rm -rf /var/cache/yum/

COPY --from=builder /venv /venv
COPY --from=builder /$appname /$appname
WORKDIR /$appname
COPY config.ini .
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8
CMD ["/env/bin/gunicorn", "argowrapper.argowrapper.asgi:app", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker"]
