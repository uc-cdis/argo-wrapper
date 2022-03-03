from fastapi import APIRouter, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from argowrapper.auth import Auth
from argowrapper.engine import ArgoEngine

router = APIRouter()
argo_engine = ArgoEngine()
auth = Auth()


class WorkflowParameters(BaseModel):  # pylint: disable=too-few-public-methods
    """
    A class that encompases the request body being passed
    """

    n_pcs: int
    covariantes: str
    out_prefix: str
    outcome: str
    outcome_is_binary: str
    maf_threshold: float
    imputation_score_cutoff: float
    template_version: str


def auth_helper(token):
    if token == "":
        return HTMLResponse(
            content="authentication token required",
            status_code=HTTP_401_UNAUTHORIZED,
        )
    if not auth.authenticate(token=token):
        return HTMLResponse(
            content="token is not authorized, out of date, or malformed",
            status_code=HTTP_401_UNAUTHORIZED,
        )

    return None


@router.get("/test")
def test():
    """route to test that the argo-workflow is correctly running"""
    return {"message": "test"}


# submit argo workflow
@router.post("/submit", status_code=HTTP_200_OK)
def submit_workflow(
    workflow_parameters: WorkflowParameters,
    Authorization: str = Header(None),  # pylint: disable=invalid-name
) -> str:
    """route to submit workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    try:
        return argo_engine.submit_workflow(workflow_parameters.dict())

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get status
@router.get("/status/{workflow_name}", status_code=HTTP_200_OK)
def get_workflow_status(
    workflow_name: str, Authorization: str = Header(None)
) -> str:  # pylint: disable=invalid-name
    """returns current status of a workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    try:
        return argo_engine.get_workflow_status(workflow_name)

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# cancel workflow
@router.post("/cancel/{workflow_name}", status_code=HTTP_200_OK)
def cancel_workflow(
    workflow_name: str, Authorization: str = Header(None)
) -> str:  # pylint: disable=invalid-name
    """cancels a currently running workflow"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    try:
        return argo_engine.cancel_workflow(workflow_name)

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get workflows
@router.get("/workflows/{user_name}", status_code=HTTP_200_OK)
def get_workflows(
    user_name: str, Authorization: str = Header(None)
) -> str:  # pylint: disable=invalid-name
    """returns the list of workflows the user has ran"""
    if (auth_res := auth_helper(Authorization)) :
        return auth_res

    try:
        return argo_engine.get_workfows_for_user(user_name)

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )
