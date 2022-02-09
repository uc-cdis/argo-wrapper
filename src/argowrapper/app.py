import asyncio
from importlib.metadata import entry_points

from fastapi import FastAPI
from fastapi.routing import APIRoute

from .routes import workflow


def get_app():
    app = FastAPI(title="argo wrapper")
    app.include_router(workflow.router)
    return app
