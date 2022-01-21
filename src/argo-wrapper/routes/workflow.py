from fastapi import APIRouter

from ..engine import ArgoEngine

router = APIRouter()
argo_engine = ArgoEngine()


@router.get("/test")
def test():
    return {"message": "test"}


# submit argo workflow
@router.post("/submit")
def submit_workflow():
    # authenticate()
    message = argo_engine.submit_workflow({})
    return {"message": message}


# get status
@router.get("/status/{workflow_name}")
def get_workflow_status(workflow_name: str):
    # is_authorized = authenticate()
    # if not is_authorized:
    #    raise HTTPException(status_code=404, detail="user not authorized access to workflow status")
    message = argo_engine.get_workflow_status(workflow_name)
    return {"message": message}


# cancel workflow
@router.post("/cancel/{workflow_name}")
def cancel_workflow(workflow_name: str):
    # authenticate()
    message = argo_engine.cancel_workflow(workflow_name)
    return {"message": message}
