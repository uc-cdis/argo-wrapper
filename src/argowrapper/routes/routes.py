from functools import wraps
from typing import Dict, List, NamedTuple

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import html
from pydantic import BaseModel
from starlette.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from argowrapper.auth import Auth
from argowrapper.engine.argo_engine import ArgoEngine

router = APIRouter()
argo_engine = ArgoEngine()
auth = Auth()


class RequestBody(BaseModel):  # pylint: disable=too-few-public-methods
    """
    A class that encompases the request body being passed
    """

    n_pcs: int
    variables: List[Dict]
    hare_population: str
    out_prefix: str
    outcome: int
    maf_threshold: float
    imputation_score_cutoff: float
    template_version: str
    source_id: int
    case_cohort_definition_id: int
    control_cohort_definition_id: int
    workflow_name: str


def check_auth(fn):
    """custom annotation to authenticate user request"""

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
    request_body: RequestBody,
    request: Request,  # pylint: disable=unused-argument
) -> str:
    """route to submit workflow"""

    try:
        auth_token = html.escape(request.headers.get("Authorization"))
        return argo_engine.workflow_submission(request_body.dict(), auth_token)

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


@router.get("/archivedWorkflows", status_code=HTTP_200_OK)
def get_workflows(
    request: Request,  # pylint: disable=unused-argument
) -> List[NamedTuple]:

    try:
        auth_token = html.escape(request.headers.get("Authorization"))
        return argo_engine.get_archived_workfows_for_user(auth_token)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/archivedworkflowstatus/{workflow_uid}", status_code=HTTP_200_OK)
@check_auth
def get_workflows(
    workflow_uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> List[str]:

    try:
        return argo_engine.get_archived_workflow_status(workflow_uid)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get workflows
@router.get("/workflows", status_code=HTTP_200_OK)
@check_auth
def get_workflows(
    request: Request,  # pylint: disable=unused-argument
) -> List[str]:
    """returns the list of workflows the user has ran"""

    try:
        auth_token = html.escape(request.headers.get("Authorization"))
        return argo_engine.get_workfows_for_user(auth_token)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/logs/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_logs(
    workflow_name,
    request: Request,  # pylint: disable=unused-argument
) -> List[str]:
    """returns the list of workflows the user has ran"""

    try:
        return argo_engine.get_workflow_logs(workflow_name)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )
