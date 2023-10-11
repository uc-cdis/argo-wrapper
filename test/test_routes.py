import json
from typing import Any, Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from argowrapper.constants import *

from argowrapper.routes.routes import router


def start_application():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(scope="function")
def app() -> Generator[FastAPI, Any, None]:
    """
    Create a fresh database on each test case.
    """
    _app = start_application()
    yield _app


@pytest.fixture(scope="function")
def client(app: FastAPI) -> Generator[TestClient, Any, None]:
    with TestClient(app) as client:
        yield client


def test_submit_workflow(client):

    variables = [
        {"variable_type": "concept", "concept_id": "2000000324"},
        {"variable_type": "concept", "concept_id": "2000000123"},
        {"variable_type": "custom_dichotomous", "cohort_ids": [1, 3]},
    ]

    data = {
        "n_pcs": 3,
        "variables": variables,
        "hare_population": "hare",
        "out_prefix": "vadc_genesis",
        "outcome": 1,
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "template_version": "gwas-template-latest",
        "source_id": 4,
        "case_cohort_definition_id": 70,
        "control_cohort_definition_id": -1,
        "workflow_name": "wf_name",
        TEAM_PROJECT_FIELD_NAME: "dummy-team-project",
    }

    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"workflow_123"'
        mock_auth.assert_called_with(
            token="bearer 1234", team_project="dummy-team-project"
        )
        mock_log.assert_called_with("check_auth_and_team_project")


def test_submit_workflow_missing_team_project(client):

    data = {
        "n_pcs": 3,
    }
    with pytest.raises(Exception) as exception:
        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert (
            f"the '{TEAM_PROJECT_FIELD_NAME}' field is required for this endpoint"
            in str(exception)
        )


def test_get_workflow_details_valid_team_project(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = {
            GEN3_USER_METADATA_LABEL: "dummyuser",
            GEN3_TEAM_PROJECT_METADATA_LABEL: "dummyteam",
        }
        response = client.get(
            "/status/workflow_123?uid=workflow_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        expected_reponse = '"{}":"dummyuser","{}":"dummyteam"'.format(
            GEN3_USER_METADATA_LABEL, GEN3_TEAM_PROJECT_METADATA_LABEL
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == "{" + expected_reponse + "}"
        mock_auth.assert_called_with(token="bearer 1234", team_project="dummyteam")
        mock_log.assert_called_with("check_auth")


def test_get_workflow_details_valid_user(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine_helper.get_username_from_token"
    ) as mock_helper:
        mock_auth.return_value = True
        mock_engine.return_value = {
            GEN3_USER_METADATA_LABEL: "user-dummyuser",
        }
        mock_helper.return_value = "dummyuser"
        response = client.get(
            "/status/workflow_123?uid=workflow_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        expected_reponse = '"{}":"user-dummyuser"'.format(GEN3_USER_METADATA_LABEL)
        assert response.status_code == 200
        assert response.content.decode("utf-8") == "{" + expected_reponse + "}"
        mock_auth.assert_called_with(token="bearer 1234")


def test_get_workflow_details_for_unauthorized_user_scenario1(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine_helper.get_username_from_token"
    ) as mock_helper:
        mock_auth.return_value = False  # mock failed authentication
        mock_engine.return_value = {
            GEN3_USER_METADATA_LABEL: "user-dummyuser",
        }
        mock_helper.return_value = "otheruser"
        response = client.get(
            "/status/workflow_123?uid=workflow_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 401
        assert (
            "token is missing, not authorized, out of date, or malformed"
            in response.content.decode("utf-8")
        )


def test_get_workflow_details_for_unauthorized_user_scenario2(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine_helper.get_username_from_token"
    ) as mock_helper:
        mock_auth.return_value = True
        mock_engine.return_value = {
            GEN3_USER_METADATA_LABEL: "user-dummyuser",
        }
        mock_helper.return_value = "otheruser"
        response = client.get(
            "/status/workflow_123?uid=workflow_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 401
        assert "user is not the author of this workflow" in response.content.decode(
            "utf-8"
        )


def test_cancel_workflow(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.cancel_workflow"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_workflow_details, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123 canceled sucessfully"
        mock_workflow_details.return_value = {
            GEN3_TEAM_PROJECT_METADATA_LABEL: "dummyteam"
        }
        response = client.post(
            "/cancel/workflow_123",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"workflow_123 canceled sucessfully"'
        mock_auth.assert_called_with(token="bearer 1234", team_project="dummyteam")
        mock_log.assert_called_with("check_auth")


def test_retry_workflow(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.retry_workflow"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_workflow_details, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123 retried sucessfully"
        mock_workflow_details.return_value = {
            GEN3_TEAM_PROJECT_METADATA_LABEL: "dummyteam"
        }
        response = client.post(
            "/retry/workflow_123?uid=wf_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"workflow_123 retried sucessfully"'
        mock_auth.assert_called_with(token="bearer 1234", team_project="dummyteam")
        mock_log.assert_called_with("check_auth")


def test_get_user_workflows(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflows_for_user"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = ["wf_1", "wf_2"]
        response = client.get(
            "/workflows",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '["wf_1","wf_2"]'
        mock_auth.assert_called_with(token="bearer 1234")
        mock_log.assert_called_with("check_auth_and_optional_team_projects")


def test_get_user_workflows_with_team_projects(client):
    def mock_get_workflows_for_team_projects(team_projects):
        # dummy implementation...but allows us to check if the team_projects were
        # successfully parsed from the request parameters:
        return team_projects

    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflows_for_team_projects",
        mock_get_workflows_for_team_projects,
    ):
        mock_auth.return_value = True
        response = client.get(
            "/workflows?team_projects=team1&team_projects=team2",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '["team1","team2"]'
        mock_auth.assert_called_with(token="bearer 1234", team_project="team2")


def test_get_workflow_logs(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_logs"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_workflow_details, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = True
        mock_engine.return_value = [
            {
                "name": "wf_name",
                "step_template": "wf_template",
                "error_message": "wf_error",
            }
        ]
        mock_workflow_details.return_value = {
            GEN3_TEAM_PROJECT_METADATA_LABEL: "dummyteam"
        }
        response = client.get(
            "/logs/wf_123?uid=wf_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert (
            response.content.decode("utf-8")
            == '[{"name":"wf_name","step_template":"wf_template","error_message":"wf_error"}]'
        )
        mock_log.assert_called_with("check_auth")


def test_if_endpoints_are_set_to_the_right_check_auth(client):
    """one generic test method to test whether endpoints are
    calling the right check_auth methods"""
    with patch("argowrapper.routes.routes.log_auth_check_type") as mock_log:
        client.post(
            "/submit",
            data=json.dumps({TEAM_PROJECT_FIELD_NAME: "abc"}),
        )
        mock_log.assert_called_with("check_auth_and_team_project")

        client.get("/status/workflow_123?uid=workflow_uid")
        mock_log.assert_called_with("check_auth")

        client.post("/retry/workflow_123?uid=workflow_uid")
        mock_log.assert_called_with("check_auth")

        client.post("/cancel/workflow_123")
        mock_log.assert_called_with("check_auth")

        client.get("/workflows?team_projects=team1&team_projects=team2")
        mock_log.assert_called_with("check_auth_and_optional_team_projects")

        client.get("/logs/workflow_123?uid=workflow_uid")
        mock_log.assert_called_with("check_auth")
