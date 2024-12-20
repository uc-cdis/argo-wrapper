import traceback
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_400_BAD_REQUEST,
)
from argowrapper.constants import (
    TEAM_PROJECT_FIELD_NAME,
    TEAM_PROJECT_LIST_FIELD_NAME,
    GEN3_TEAM_PROJECT_METADATA_LABEL,
    GEN3_USER_METADATA_LABEL,
    EXCEED_WORKFLOW_LIMIT_ERROR,
)

from argowrapper import logger
from argowrapper.auth import Auth
from argowrapper.engine.argo_engine import ArgoEngine
from argowrapper.auth.utils import get_cohort_ids_for_team_project

import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper

router = APIRouter()
argo_engine = ArgoEngine()
auth = Auth()


def log_auth_check_type(auth_check_type):
    logger.info(f"Checking authentication and authorization using {auth_check_type}")


def check_auth(fn):
    """custom annotation to authenticate user request and check whether the
    user is authorized to access argo-wrapper and the workflow in question"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        log_auth_check_type("check_auth")
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        # check authentication and basic argo-wrapper authorization:
        if not auth.authenticate(token=token):
            return HTMLResponse(
                content="token is missing, not authorized, out of date, or malformed",
                status_code=HTTP_401_UNAUTHORIZED,
            )
        # get workflow details. If the workflow has a "team project" label, check if the
        # user is authorized to this "team project":
        workflow_name = kwargs["workflow_name"]
        uid = kwargs.get("uid")
        workflow_details = argo_engine.get_workflow_details(workflow_name, uid)
        if (
            GEN3_TEAM_PROJECT_METADATA_LABEL in workflow_details
            and workflow_details[GEN3_TEAM_PROJECT_METADATA_LABEL]
        ):
            if not auth.authenticate(
                token=token,
                team_project=workflow_details[GEN3_TEAM_PROJECT_METADATA_LABEL],
            ):
                return HTMLResponse(
                    content="token is missing, not authorized, out of date, or malformed, or team_project access not granted",
                    status_code=HTTP_401_UNAUTHORIZED,
                )
        else:
            # If the "team project"label is not there, check if
            # the workflow is one of the user's own workflows:
            workflow_user = workflow_details[GEN3_USER_METADATA_LABEL]
            username = argo_engine_helper.get_username_from_token(token)
            current_user = argo_engine_helper.convert_gen3username_to_pod_label(
                username
            )
            if current_user != workflow_user:
                return HTMLResponse(
                    content="user is not the author of this workflow, and hence cannot access it",
                    status_code=HTTP_401_UNAUTHORIZED,
                )

        return fn(*args, **kwargs)

    return wrapper


def check_auth_and_team_project(fn):
    """custom annotation to authenticate user request AND check teamproject authorization"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        log_auth_check_type("check_auth_and_team_project")
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


def check_auth_and_optional_team_projects(fn):
    """custom annotation to authenticate user request AND check teamproject authorizations"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        log_auth_check_type("check_auth_and_optional_team_projects")
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


def check_team_projects_and_cohorts(fn):
    """custom annotation to make sure cohort in request belong to user's team project"""

    @wraps(fn)
    def wrapper(*args, **kwargs):

        token = kwargs["request"].headers.get("Authorization")
        request_body = kwargs["request_body"]
        team_project = request_body[TEAM_PROJECT_FIELD_NAME]
        source_id = request_body["source_id"]

        # Construct set with all cohort ids requested
        cohort_ids = []
        if "cohort_ids" in request_body["outcome"]:
            cohort_ids.extend(request_body["outcome"]["cohort_ids"])

        variables = request_body["variables"]
        for v in variables:
            if "cohort_ids" in v:
                cohort_ids.extend(v["cohort_ids"])

        if "source_population_cohort" in request_body:
            cohort_ids.append(request_body["source_population_cohort"])

        cohort_id_set = set(cohort_ids)

        if team_project and source_id and len(team_project) > 0 and len(cohort_ids) > 0:
            # Get team project cohort ids
            team_cohort_id_set = get_cohort_ids_for_team_project(
                token, source_id, team_project
            )

            logger.debug("cohort ids are " + " ".join(str(c) for c in cohort_ids))
            logger.debug(
                "team cohort ids are " + " ".join(str(c) for c in team_cohort_id_set)
            )

            # Compare the two sets
            if cohort_id_set.issubset(team_cohort_id_set):
                logger.debug(
                    "cohort ids submitted all belong to the same team project. Continue.."
                )
                return fn(*args, **kwargs)
            else:
                logger.error(
                    "Cohort ids submitted do NOT all belong to the same team project."
                )
                return HTMLResponse(
                    content="Cohort ids submitted do NOT all belong to the same team project.",
                    status_code=HTTP_400_BAD_REQUEST,
                )

        else:
            # some required parameters is missing, return bad request:
            return HTMLResponse(
                content="Missing required parameters",
                status_code=HTTP_400_BAD_REQUEST,
            )

    return wrapper


@router.get("/test")
def test():
    """route to test that the argo-workflow is correctly running"""
    return {"message": "test"}


# submit argo workflow
@router.post("/submit", status_code=HTTP_200_OK)
@check_auth_and_team_project
@check_team_projects_and_cohorts
def submit_workflow(
    request_body: Dict[Any, Any],
    request: Request,  # pylint: disable=unused-argument
) -> Union[str, Any]:
    """route to submit workflow"""
    try:
        return argo_engine.workflow_submission(
            request_body, request.headers.get("Authorization")
        )
    except Exception as exception:
        logger.error(str(exception))
        if str(exception) == EXCEED_WORKFLOW_LIMIT_ERROR:
            return HTMLResponse(
                content="You have reached the monthly workflow cap.",
                status_code=HTTP_403_FORBIDDEN,
            )
        else:
            return HTMLResponse(
                content="Unexpected Error Occurred",
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            )


# get status
@router.get("/status/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_details(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> Union[Dict[str, Any], str, Any]:
    """returns details of a workflow"""

    try:
        return argo_engine.get_workflow_details(workflow_name, uid)

    except Exception as exception:
        logger.error(str(exception))
        return HTMLResponse(
            content="Unexpected Error Occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# retry workflow
@router.post("/retry/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def retry_workflow(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> Union[str, Any]:
    """retries a currently failed workflow"""
    workflow_details = argo_engine.get_workflow_details(workflow_name, uid)
    try:
        new_parameters = {}
        for param in workflow_details.get("arguments").get("parameters"):
            new_parameters[param.get("name")] = param.get("value")

        result = argo_engine.workflow_submission(
            new_parameters, request.headers.get("Authorization")
        )
        return result + " retried successfully"
    except Exception as exception:
        logger.error(traceback.format_exc())
        logger.error(f"could not retry {workflow_name}, failed with error {exception}")
        return HTMLResponse(
            content="Could not retry workflow, error occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# cancel workflow
@router.post("/cancel/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def cancel_workflow(
    workflow_name: str,
    request: Request,  # pylint: disable=unused-argument
) -> Union[str, Any]:
    """cancels a currently running workflow"""

    try:
        return argo_engine.cancel_workflow(workflow_name)

    except Exception as exception:
        logger.error(str(exception))
        return HTMLResponse(
            content="Unexpected Error Occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get workflows
@router.get("/workflows", status_code=HTTP_200_OK)
@check_auth_and_optional_team_projects
def get_workflows(
    request: Request,  # pylint: disable=unused-argument
    team_projects: Optional[List[str]] = Query(default=None),
) -> Union[List[Dict], Any]:
    """returns the list of workflows the user has ran"""

    try:
        if team_projects and len(team_projects) > 0:
            return argo_engine.get_workflows_for_team_projects_and_user(
                team_projects=team_projects,
                auth_header=request.headers.get("Authorization"),
            )
        else:
            # no team_projects, so fall back to querying the workflows that belong just to the user (no team project):
            return argo_engine.get_workflows_for_user(
                request.headers.get("Authorization")
            )

    except Exception as exception:
        logger.error(str(exception))
        return HTMLResponse(
            content="Unexpected Error Occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/logs/{workflow_name}", status_code=HTTP_200_OK)
@check_auth
def get_workflow_logs(
    workflow_name: str,
    uid: str,
    request: Request,  # pylint: disable=unused-argument
) -> Union[List[Dict], Any]:
    """returns the list of workflows the user has ran"""

    try:
        return argo_engine.get_workflow_logs(workflow_name, uid)

    except Exception as exception:
        logger.error(str(exception))
        return HTMLResponse(
            content="Unexpected Error Occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/workflows/user-monthly", status_code=HTTP_200_OK)
def get_user_monthly_workflow(
    request: Request,
) -> Dict[str, Any]:
    """
    Query Argo service to see how many successful run user already
    have in the current calendar month. Return workflow numbers and workflow cap
    """

    try:
        (
            billing_id,
            workflow_limit,
        ) = argo_engine.check_user_info_for_billing_id_and_workflow_limit(
            request.headers.get("Authorization")
        )

        # if user has billing_id (non-VA user), check if they already reached the monthly cap
        workflow_run, workflow_limit = argo_engine.check_user_monthly_workflow_cap(
            request.headers.get("Authorization"), billing_id, workflow_limit
        )

        result = {"workflow_run": workflow_run, "workflow_limit": workflow_limit}
        return result
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        raise e
