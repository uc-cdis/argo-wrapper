import traceback
from functools import wraps
from typing import Dict, List, Any, Optional

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
    GEN3_NON_VA_WORKFLOW_MONTHLY_CAP,
)

from argowrapper import logger
from argowrapper.auth import Auth
from argowrapper.engine.argo_engine import ArgoEngine
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper

import requests

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
        import json

        logger.info("arguments:")
        logger.info(json.dumps(kwargs))
        request = kwargs["request"]
        token = request.headers.get("Authorization")
        team_project = kwargs[TEAM_PROJECT_FIELD_NAME]
        cohort_ids = []
        source_id = kwargs["source_id"]
        if "outcome" in kwargs and "cohort_ids" in kwargs["outcome"]:
            cohort_ids = cohort_ids.append(kwargs["outcome"]["cohort_ids"])

        if "variables" in kwargs:
            variables = kwargs["variables"]
            for v in variables:
                if "cohort_ids" in v:
                    cohort_ids.append(v["cohort_ids"])

        if team_project and source_id and len(team_project) > 0 and len(cohort_ids) > 0:
            header = {"cookie": "fence={}".format(token)}
            url = "https://cohort-middleware-service/cohortdefinition-stats/by-source-id/{}/by-team-project?team-project={}".format(
                source_id, team_project
            )

            logger.info("team project is " + team_project)
            logger.info("source_id is " + source_id)
            logger.info("cohort ids are " + " ".join(cohort_ids))
            logger.info("request url is " + url)

            try:
                r = requests.get(url=url, headers=header)
                r.raise_for_status()
                team_cohort_info = r.json()
                team_cohort_id_set = set()
                if "cohort_definitions_and_stats" in team_cohort_info:
                    for t in team_cohort_info:
                        if "cohort_definition_id" in t:
                            team_cohort_id_set.add(t["cohort_definition_id"])
                cohort_id_set = set(cohort_ids)

                if cohort_id_set.issubset(team_cohort_id_set):
                    logger.info(
                        "cohort ids submitted belong to user's team project. Continue.."
                    )
                    return fn(*args, **kwargs)
                else:
                    logger.error(
                        "cohort ids submitted do NOT belong to user's team project."
                    )
                    return HTMLResponse(
                        content="Cohort ids submitted do NOT belong to user's team project.",
                        status_code=HTTP_401_UNAUTHORIZED,
                    )
            except Exception as e:
                exception = Exception("Something went wrong", e)
                logger.error(exception)
                traceback.print_exc()
                raise exception
        else:
            # some required parameters is missing, return bad request:
            return HTMLResponse(
                content="Missing required parameters",
                status_code=HTTP_400_BAD_REQUEST,
            )

    return wrapper


def check_user_billing_id(request):
    """
    Check whether user is non-VA user
    if user is VA-user, do nothing and proceed
    if user is non-VA user () billing id tag exists in fence user info)
    add billing Id to argo metadata and pod metadata
    remove gen3 username from pod metadata
    """

    header = {"Authorization": request.headers.get("Authorization")}
    # TODO: Make this configurable
    url = "http://fence-service/user"
    try:
        r = requests.get(url=url, headers=header)
        r.raise_for_status()
        user_info = r.json()
    except Exception as e:
        exception = Exception("Could not determine user billing info from fence", e)
        logger.error(exception)
        traceback.print_exc()
        raise exception
    logger.info("Got user info successfully. Checking for billing id..")

    if "tags" in user_info and "billing_id" in user_info["tags"]:
        billing_id = user_info["tags"]["billing_id"]
        logger.info("billing id found in user tags: " + billing_id)
        return billing_id
    else:
        logger.info("billing id not found.")
        return None


def check_user_reached_monthly_workflow_cap(request_token):
    """
    Query Argo service to see how many successful run user already
    have in the current calendar month. If the number is greater than
    the threshold, return error.
    """

    try:
        current_month_workflows = argo_engine.get_user_workflows_for_current_month(
            request_token
        )

        if len(current_month_workflows) >= GEN3_NON_VA_WORKFLOW_MONTHLY_CAP:
            logger.info(
                "User already executed {} workflows this month and cannot create new ones anymore.".format(
                    len(current_month_workflows)
                )
            )
            logger.info(
                "The currently monthly cap is {}.".format(
                    GEN3_NON_VA_WORKFLOW_MONTHLY_CAP
                )
            )
            return True

        return False
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        raise e


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
) -> str:
    """route to submit workflow"""
    try:
        reached_monthly_cap = False

        # check if user has a billing id tag:
        billing_id = check_user_billing_id(request)

        # if user has billing_id (non-VA user), check if they already reached the monthly cap
        if billing_id:
            reached_monthly_cap = check_user_reached_monthly_workflow_cap(
                request.headers.get("Authorization")
            )

        # submit workflow:
        if not reached_monthly_cap:
            return argo_engine.workflow_submission(
                request_body, request.headers.get("Authorization"), billing_id
            )
        else:
            return HTMLResponse(
                content="You have reached the workflow monthly cap.",
                status_code=HTTP_403_FORBIDDEN,
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
@check_auth_and_optional_team_projects
def get_workflows(
    request: Request,  # pylint: disable=unused-argument
    team_projects: Optional[List[str]] = Query(default=None),
) -> List[str]:
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
