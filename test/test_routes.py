import json
from typing import Any, Generator
from unittest.mock import patch
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from argowrapper.constants import *
from test.constants import EXAMPLE_AUTH_HEADER
from argowrapper.routes.routes import (
    router,
    check_user_reached_monthly_workflow_cap,
    get_user_monthly_workflow,
)
from argowrapper.constants import GEN3_NON_VA_WORKFLOW_MONTHLY_CAP

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
    "outcome": {
        "variable_type": "custom_dichotomous",
        "cohort_ids": [2],
        "provided_name": "test Pheno",
    },
    "maf_threshold": 0.01,
    "imputation_score_cutoff": 0.3,
    "template_version": "gwas-template-latest",
    "source_id": 4,
    "case_cohort_definition_id": 70,
    "control_cohort_definition_id": -1,
    "source_population_cohort": 4,
    "workflow_name": "wf_name",
    TEAM_PROJECT_FIELD_NAME: "dummy-team-project",
    "user_tags": None,  # For testing purpose
}

cohort_definition_data = {
    "cohort_definitions_and_stats": [
        {"cohort_definition_id": 1, "cohort_name": "Cohort 1", "size": 1},
        {"cohort_definition_id": 2, "cohort_name": "Cohort 2", "size": 2},
        {"cohort_definition_id": 3, "cohort_name": "Cohort 3", "size": 3},
        {"cohort_definition_id": 4, "cohort_name": "Cohort 4", "size": 4},
    ]
}


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


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code == 500:
                raise Exception("fence is down")
            if self.status_code != 200:
                raise Exception()

    if (
        kwargs["url"]
        == "http://cohort-middleware-service/cohortdefinition-stats/by-source-id/4/by-team-project?team-project=dummy-team-project"
    ):
        return MockResponse(cohort_definition_data, 200)

    if kwargs["url"] == "http://fence-service/user":
        if data["user_tags"] != 500:
            return MockResponse(data["user_tags"], 200)
        else:
            return MockResponse({}, 500)

    return None


def test_submit_workflow(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log, patch(
        "argowrapper.routes.routes.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_check_billing_id, patch(
        "requests.get"
    ) as mock_requests, patch(
        "argowrapper.routes.routes.check_user_reached_monthly_workflow_cap"
    ) as mock_check_monthly_cap:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        mock_check_billing_id.return_value = None, None
        mock_requests.side_effect = mocked_requests_get
        mock_check_monthly_cap.return_value = False

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"workflow_123"'
        mock_auth.assert_called_with(
            token=EXAMPLE_AUTH_HEADER, team_project="dummy-team-project"
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


def test_submit_workflow_failing_auth(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = False
        response = client.post(
            "/submit",
            data=json.dumps({TEAM_PROJECT_FIELD_NAME: "dummy-team-project"}),
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 401
        assert (
            response.content.decode("utf-8")
            == "token is missing, not authorized, out of date, or malformed, or team_project access not granted"
        )
        mock_auth.assert_called_with(
            token="bearer 1234", team_project="dummy-team-project"
        )
        mock_log.assert_called_with("check_auth_and_team_project")


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
            == response.content.decode("utf-8")
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


def test_get_workflow_details_for_unauthorized_user_scenario3(client):
    def mock_authenticate(token, team_project=None):
        """dummy implementation that fails if team_project is set"""
        if team_project:
            return False
        else:
            return True

    with patch(
        "argowrapper.routes.routes.auth.authenticate", mock_authenticate
    ) as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.argo_engine_helper.get_username_from_token"
    ) as mock_helper:
        mock_auth.return_value = True
        mock_engine.return_value = {
            GEN3_USER_METADATA_LABEL: "user-dummyuser",
            GEN3_TEAM_PROJECT_METADATA_LABEL: "user-dummy-team",
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
            "token is missing, not authorized, out of date, or malformed, or team_project access not granted"
            == response.content.decode("utf-8")
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


def test_get_user_workflows_error_scenario1(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = False
        response = client.get(
            "/workflows?team_projects=team1&team_projects=team2",
            headers={
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 401
        assert (
            response.content.decode("utf-8")
            == "token is missing, not authorized, out of date, or malformed, or team_project access not granted"
        )
        mock_auth.assert_called_with(token="bearer 1234", team_project="team1")
        mock_log.assert_called_with("check_auth_and_optional_team_projects")


def test_get_user_workflows_error_scenario2(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log:
        mock_auth.return_value = False
        response = client.get(
            "/workflows",
            headers={
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 401
        assert (
            response.content.decode("utf-8")
            == "token is missing, not authorized, out of date, or malformed"
        )
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
    ), patch(
        "argowrapper.routes.routes.argo_engine.get_workflows_for_user"
    ) as mock_get_workflows_for_user:
        mock_get_workflows_for_user.return_value = []
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


def test_submit_workflow_with_user_billing_id(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log, patch(
        "requests.get"
    ) as mock_requests, patch(
        "argowrapper.engine.argo_engine.ArgoEngine.get_user_workflows_for_current_month"
    ) as mock_get_workflow:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        mock_requests.side_effect = mocked_requests_get
        mock_get_workflow.return_value = [
            {"wf_name": "workflow1"},
            {"wf_name": "workflow2"},
        ]

        data["user_tags"] = {"tags": {}}
        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 200
        assert mock_engine.call_args.args[2] == None

        data["user_tags"] = {"tags": {"othertag1": "tag1"}}

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 200
        assert mock_engine.call_args.args[2] == None

        data["user_tags"] = {"tags": {"othertag1": "tag1", "billing_id": "1234"}}

        with patch(
            "argowrapper.routes.routes.check_user_reached_monthly_workflow_cap"
        ) as mock_check_monthly_cap:
            mock_check_monthly_cap.return_value = False
            response = client.post(
                "/submit",
                data=json.dumps(data),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": EXAMPLE_AUTH_HEADER,
                },
            )
            assert mock_engine.call_args.args[2] == "1234"

        data["user_tags"] = 500

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 500


def test_check_user_reached_monthly_workflow_cap():
    headers = {
        "Content-Type": "application/json",
        "Authorization": EXAMPLE_AUTH_HEADER,
    }

    with patch(
        "argowrapper.engine.argo_engine.ArgoEngine.get_user_workflows_for_current_month"
    ) as mock_get_workflow:
        mock_get_workflow.return_value = [
            {"wf_name": "workflow1"},
            {"wf_name": "workflow2"},
        ]

        # Test Under Default Limit
        assert (
            check_user_reached_monthly_workflow_cap(
                headers["Authorization"], None, None
            )
            == False
        )

        # Test Custom Limit
        assert (
            check_user_reached_monthly_workflow_cap(headers["Authorization"], None, 2)
            == True
        )

        # Test Billing Id User Exceeding Limit
        workflows = []
        for index in range(GEN3_NON_VA_WORKFLOW_MONTHLY_CAP + 1):
            workflows.append({"wf_name": "workflow" + str(index)})
        mock_get_workflow.return_value = workflows

        assert (
            check_user_reached_monthly_workflow_cap(
                headers["Authorization"], "1234", None
            )
            == True
        )

        # Test VA User Exceeding Limit
        workflows = []
        for index in range(GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP + 1):
            workflows.append({"wf_name": "workflow" + str(index)})
        mock_get_workflow.return_value = workflows
        assert (
            check_user_reached_monthly_workflow_cap(
                headers["Authorization"], None, None
            )
            == True
        )


def test_submit_workflow_with_billing_id_and_over_monthly_cap(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log, patch(
        "argowrapper.routes.routes.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_check_billing_id, patch(
        "argowrapper.routes.routes.check_user_reached_monthly_workflow_cap"
    ) as mock_check_monthly_cap, patch(
        "requests.get"
    ) as mock_requests:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        mock_check_billing_id.return_value = "1234", None
        mock_check_monthly_cap.return_value = True
        mock_requests.side_effect = mocked_requests_get

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 403


def test_submit_workflow_over_monthly_cap(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log, patch(
        "argowrapper.routes.routes.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_check_billing_id, patch(
        "argowrapper.routes.routes.check_user_reached_monthly_workflow_cap"
    ) as mock_check_monthly_cap, patch(
        "requests.get"
    ) as mock_requests:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        mock_check_billing_id.return_value = None, None
        mock_check_monthly_cap.return_value = True
        mock_requests.side_effect = mocked_requests_get

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 403


def test_submit_workflow_with_non_team_project_cohort(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine, patch(
        "argowrapper.routes.routes.log_auth_check_type"
    ) as mock_log, patch(
        "argowrapper.routes.routes.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_check_billing_id, patch(
        "requests.get"
    ) as mock_requests:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123"
        mock_check_billing_id.return_value = None, None
        mock_requests.side_effect = mocked_requests_get

        data["outcome"]["cohort_ids"] = [400]

        response = client.post(
            "/submit",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": EXAMPLE_AUTH_HEADER,
            },
        )
        assert response.status_code == 400


def test_get_user_monthly_workflow():
    headers = {
        "Content-Type": "application/json",
        "Authorization": EXAMPLE_AUTH_HEADER,
    }

    with patch(
        "argowrapper.engine.argo_engine.ArgoEngine.get_user_workflows_for_current_month"
    ) as mock_get_workflow:
        mock_get_workflow.return_value = [
            {"wf_name": "workflow1"},
            {"wf_name": "workflow2"},
        ]

        assert get_user_monthly_workflow(headers["Authorization"]) == [
            {"wf_name": "workflow1"},
            {"wf_name": "workflow2"},
        ]
