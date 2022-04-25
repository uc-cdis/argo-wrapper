from functools import wraps
from typing import List, Dict
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from argowrapper.auth import Auth
from argowrapper.engine import ArgoEngine
from argowrapper.engine.helpers import argo_engine_helper

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


def check_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        if not token:
            return HTMLResponse(
                content="authentication token required",
                status_code=HTTP_401_UNAUTHORIZED,
            )

        if not auth.authenticate(token=token):
            return HTMLResponse(
                content="token is not authorized, out of date, or malformed",
                status_code=HTTP_401_UNAUTHORIZED,
            )

        return fn(*args, **kwargs)

    return wrapper


@router.get("/test")
def test():
    """route to test that the argo-workflow is correctly running"""
    return {"message": "test"}


# submit argo workflow
@router.post("/submit", status_code=HTTP_200_OK)
@check_auth
def submit_workflow(
    workflow_parameters: WorkflowParameters,
    request: Request,  # pylint: disable=unused-argument
) -> str:
    """route to submit workflow"""

    try:
        return argo_engine.submit_workflow(
            workflow_parameters.dict(), request.headers.get("Authorization")
        )

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get status
@router.get("/status/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_status(
    workflow_name: str,
    request: Request,  # pylint: disable=unused-argument
) -> Dict[str, any]:
    """returns current status of a workflow"""

    try:
        return argo_engine.get_workflow_status(workflow_name)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# cancel workflow
@router.post("/cancel/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def cancel_workflow(
    workflow_name: str,
    request: Request,  # pylint: disable=unused-argument
) -> str:
    """cancels a currently running workflow"""

    try:
        return argo_engine.cancel_workflow(workflow_name)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get workflows
@router.get("/workflows", status_code=HTTP_200_OK)
@check_auth
def get_workflows(
    user_name: str,
    request: Request,  # pylint: disable=unused-argument
) -> List[str]:
    """returns the list of workflows the user has ran"""

    try:
        return argo_engine.get_workfows_for_user(request.headers.get("Authorization"))

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )
