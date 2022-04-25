import json
from typing import Any
from typing import Generator

import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argowrapper.routes.workflow import router


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
        "covariantes": "test_cov",
        "out_prefix": "test_out_prefix",
        "outcome": "test_outcome",
        "outcome_is_binary": "TRUE",
        "maf_threshold": 1.01,
        "imputation_score_cutoff": 2.02,
        "template_version": "test",
        "source_id": 2,
        "cohort_definition_id": 70,
    }
    with patch("argowrapper.routes.workflow.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.workflow.argo_engine.submit_workflow"
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
    with patch("argowrapper.routes.workflow.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.workflow.argo_engine.get_workflow_status"
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
    with patch("argowrapper.routes.workflow.auth.authenticate") as mock_auth, patch(
        "argowrapper.routes.workflow.argo_engine.cancel_workflow"
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
