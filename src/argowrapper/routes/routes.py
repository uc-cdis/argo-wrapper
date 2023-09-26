import traceback
from functools import wraps
from typing import Dict, List, Any

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from argowrapper.constants import TEAM_PROJECT_FIELD_NAME, TEAM_PROJECT_LIST_FIELD_NAME

from argowrapper import logger
from argowrapper.auth import Auth
from argowrapper.engine.argo_engine import ArgoEngine
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper

router = APIRouter()
argo_engine = ArgoEngine()
auth = Auth()


def check_auth(fn):
    """custom annotation to authenticate user request"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        if not auth.authenticate(token=token):
            return HTMLResponse(
                content="token is missing, not authorized, out of date, or malformed",
                status_code=HTTP_401_UNAUTHORIZED,
            )

        return fn(*args, **kwargs)

    return wrapper


def check_auth_and_team_project(fn):
    """custom annotation to authenticate user request AND check teamproject authorization"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        request_body = argo_engine_helper._convert_request_body_to_parameter_dict(
            kwargs["request_body"]
        )
        team_project = request_body.get(TEAM_PROJECT_FIELD_NAME)
        if not team_project:
            raise Exception(
                "the '{}' field is required for this endpoint, but was not found in the request body".format(
                    TEAM_PROJECT_FIELD_NAME
                )
            )
        if not auth.authenticate(token=token, team_project=team_project):
            return HTMLResponse(
                content="token is missing, not authorized, out of date, or malformed, or team_project access not granted",
                status_code=HTTP_401_UNAUTHORIZED,
            )

        return fn(*args, **kwargs)

    return wrapper


def check_auth_and_team_projects(fn):
    """custom annotation to authenticate user request AND check teamproject authorizations"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        team_projects = kwargs[TEAM_PROJECT_LIST_FIELD_NAME]
        if team_projects and len(team_projects) > 0:
            # validate/ensure that user has been granted access to each of the given team_project codes:
            for team_project in team_projects:
                if not auth.authenticate(token=token, team_project=team_project):
                    return HTMLResponse(
                        content="token is missing, not authorized, out of date, or malformed, or team_project access not granted",
                        status_code=HTTP_401_UNAUTHORIZED,
                    )
        else:
            # fall back to just the general user authorization for argo-wrapper:
            if not auth.authenticate(token=token):
                return HTMLResponse(
                    content="token is missing, not authorized, out of date, or malformed",
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
@check_auth_and_team_project
def submit_workflow(
    request_body: Dict[Any, Any],
    request: Request,  # pylint: disable=unused-argument
) -> str:
    """route to submit workflow"""

    try:
        return argo_engine.workflow_submission(
            request_body, request.headers.get("Authorization")
        )

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get status
@router.get("/status/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_details(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> Dict[str, any]:
    """returns details of a workflow"""

    try:
        return argo_engine.get_workflow_details(workflow_name, uid)

    except Exception as exception:
        return HTMLResponse(
            content=str(exception),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# retry workflow
@router.post("/retry/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def retry_workflow(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> str:
    """retries a currently failed workflow"""

    try:
        return argo_engine.retry_workflow(workflow_name, uid)

    except Exception as exception:
        logger.error(traceback.format_exc())
        logger.error(f"could not retry {workflow_name}, failed with error {exception}")
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
@check_auth_and_team_projects
def get_workflows(
    request: Request,  # pylint: disable=unused-argument
    team_projects: List[str] | None = Query(default=None),
) -> List[str]:
    """returns the list of workflows the user has ran"""

    try:
        if team_projects and len(team_projects) > 0:
            return argo_engine.get_workflows_for_team_projects(
                team_projects=team_projects
            )
        else:
            # no team_projects, so fall back to default behavior of returning just the user workflows:
            return argo_engine.get_workflows_for_user(
                request.headers.get("Authorization")
            )

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/logs/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_logs(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> List[str]:
    """returns the list of workflows the user has ran"""

    try:
        return argo_engine.get_workflow_logs(workflow_name, uid)

    except Exception as exception:
        return HTMLResponse(
            content=exception,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )
