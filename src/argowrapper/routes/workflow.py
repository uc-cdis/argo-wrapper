from fastapi import APIRouter

from argowrapper.engine import ArgoEngine

router = APIRouter()
argo_engine = ArgoEngine()


@router.get("/test")
def test():
    """route to test that the argo-workflow is correctly running"""
    return {"message": "test"}


# submit argo workflow
@router.post("/submit")
def submit_workflow():
    """route to submit workflow"""
    # authenticate()
    message = argo_engine.submit_workflow({})
    return {"message": message}


# get status
@router.get("/status/{workflow_name}")
def get_workflow_status(workflow_name: str):
    """returns current status of a workflow"""
    # is_authorized = authenticate()
    # if not is_authorized:
    #    raise HTTPException(status_code=404, detail="user not authorized access to workflow status")
    message = argo_engine.get_workflow_status(workflow_name)
    return {"message": message}


# cancel workflow
@router.post("/cancel/{workflow_name}")
def cancel_workflow(workflow_name: str):
    """cancels a currently running workflow"""
    # authenticate()
    message = argo_engine.cancel_workflow(workflow_name)
    return {"message": message}


# get workflows
@router.get("/workflows/{user_name}")
def get_workflows(user_name: str):
    """returns the list of workflows the user has ran"""
    message = argo_engine.get_workfows_for_user(user_name)
    return {"message": message}
