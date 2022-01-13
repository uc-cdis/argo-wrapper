from fastapi import FastAPI

def get_app():
    app = FastAPI(title="argo wrapper")
    return app