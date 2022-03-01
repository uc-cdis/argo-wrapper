from fastapi import APIRouter, Header
from argowrapper.auth import Auth
from argowrapper.engine import ArgoEngine
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

router = APIRouter()
argo_engine = ArgoEngine()
auth = Auth()


class WorkflowParameters(BaseModel):
    n_pcs: int
    covariantes: str
    out_prefix: str
    outcome: str
    outcome_is_binary: str
    maf_threshold: float
    imputation_score_cutoff: float


def auth_helper(token):
    if token == "":
        return HTMLResponse(
            content="authentication token required",
            status_code=401,
        )
    if not auth.authenticate(token=token):
        return HTMLResponse(
            content="token is not authorized, out of date, or malformed",
            status_code=401,
        )

    return None


@router.get("/test")
def test():
    """route to test that the argo-workflow is correctly running"""
    return {"message": "test"}


# submit argo workflow
@router.post("/submit")
def submit_workflow(
    workflowParameters: WorkflowParameters, Authorization: str = Header(None)
):
    """route to submit workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    message = argo_engine.submit_workflow(workflowParameters.dict())
    return {"message": message}


# get status
@router.get("/status/{workflow_name}")
def get_workflow_status(workflow_name: str, Authorization: str = Header(None)):
    """returns current status of a workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    message = argo_engine.get_workflow_status(workflow_name)
    return {"message": message}


# cancel workflow
@router.post("/cancel/{workflow_name}")
def cancel_workflow(workflow_name: str, Authorization: str = Header(None)):
    """cancels a currently running workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    message = argo_engine.cancel_workflow(workflow_name)
    return {"message": message}


# get workflows
@router.get("/workflows/{user_name}")
def get_workflows(user_name: str, Authorization: str = Header(None)):
    """returns the list of workflows the user has ran"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    message = argo_engine.get_workfows_for_user(user_name)
    return {"message": message}
