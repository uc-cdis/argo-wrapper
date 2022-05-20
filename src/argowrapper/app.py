from fastapi import FastAPI

from .routes import routes


def get_app():
    app = FastAPI(title="argo wrapper")
    app.include_router(routes.router)
    return app
