import json
from typing import Any, Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    }

    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.workflow_submission"
    ) as mock_engine:
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


def test_get_workflow_details(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_details"
    ) as mock_engine:
        mock_auth.return_value = True
        mock_engine.return_value = "running"
        response = client.get(
            "/status/workflow_123?uid=workflow_uid",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"running"'


def test_cancel_workflow(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.cancel_workflow"
    ) as mock_engine:
        mock_auth.return_value = True
        mock_engine.return_value = "workflow_123 canceled sucessfully"
        response = client.post(
            "/cancel/workflow_123",
            headers={
                "Content-Type": "application/json",
                "Authorization": "bearer 1234",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == '"workflow_123 canceled sucessfully"'


def test_get_user_workflows(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflows_for_user"
    ) as mock_engine:
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


def test_get_workflow_logs(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_logs"
    ) as mock_engine:
        mock_auth.return_value = True
        mock_engine.return_value = [
            {
                "name": "wf_name",
                "step_template": "wf_template",
                "error_message": "wf_error",
            }
        ]
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
