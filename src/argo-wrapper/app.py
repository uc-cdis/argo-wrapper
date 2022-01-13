from fastapi import FastAPI
from importlib.metadata import entry_points
import logging

def get_app():
    app = FastAPI(title="argo wrapper")
    load_modules(app)
    return app

def load_modules(app=None):
    for ep in entry_points()["argo-wrapper.modules"]:
        logging.info("Loading module: %s", ep.name)
        mod = ep.load()
        if app:
            init_app = getattr(mod, "init_app", None)
            if init_app:
                init_app(app)