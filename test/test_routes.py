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
    data = {
        "n_pcs": 5,
        "covariates": ["1234", "1412"],
        "out_prefix": "test_out_prefix",
        "outcome": "-1",
        "maf_threshold": 1.01,
        "imputation_score_cutoff": 2.02,
        "template_version": "test",
        "source_id": 2,
        "case_cohort_definition_id": 70,
        "control_cohort_definition_id": -1,
        "workflow_name": "user-input-name",
        "hare_population": "hare_pop_1",
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


def test_get_workflow_status(client):
    with patch("argowrapper.routes.routes.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.routes.argo_engine.get_workflow_status"
    ) as mock_engine:
        mock_auth.return_value = True
        mock_engine.return_value = "running"
        response = client.get(
            "/status/workflow_123",
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
        "argowrapper.routes.routes.argo_engine.get_workfows_for_user"
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
            "/logs/wf_123",
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
