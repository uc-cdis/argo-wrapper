from fastapi import FastAPI

from .routes import workflow


def get_app():
    app = FastAPI(title="argo wrapper")
    app.include_router(workflow.router)
    return app
