import importlib.resources as pkg_resources
import re
import unittest.mock as mock
from collections import namedtuple

import pytest
import yaml

import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
from test.constants import EXAMPLE_AUTH_HEADER


def _convert_to_label(special_character_match: str) -> str:
    if (match := special_character_match.group()) :
        match = match.strip("-")
        byte_array = bytearray.fromhex(match)
        return byte_array.decode()


def convert_username_label_to_gen3username(label: str) -> str:
    """this function will reverse the conversion of a username to label as
    defined by the convert_gen3username_to_label function. eg "user--21" -> "!"

    Args:
        label (str): _description_

    Returns:
        : _description_
    """
    label = label.replace("user-", "", 1)
    regex = r"-[0-9A-Za-z]{2}"
    return re.sub(regex, _convert_to_label, label)


@pytest.fixture(scope="module")
def setup():
    print("*****SETUP*****")
    stream = pkg_resources.open_text(argo_workflows_templates, WF_HEADER)
    workflow_yaml = yaml.safe_load(stream)
    yield


stream = pkg_resources.open_text(argo_workflows_templates, WF_HEADER)
workflow_yaml = yaml.safe_load(stream)


def test_argo_engine_helper_add_parameters_to_gwas_workflow():
    """tests that parameters are added correctly from request body to gwas workflow"""
    parameters = {
        "pheno_csv_key": "test_replace_value",
        "n_pcs": 100,
        "covariates": ["123"],
    }
    argo_engine_helper.add_parameters_to_gwas_workflow(parameters, workflow_yaml)

    parameter_dicts = [
        parameter_dict
        for parameter_dict in workflow_yaml["spec"]["arguments"]["parameters"]
    ]
    for dict in parameter_dicts:
        if (param_name := dict["name"]) in parameters and not "covariates":
            assert dict["value"] == parameters[param_name]
        elif param_name == "covariates":
            assert dict["value"] == " ".join(parameters["covariates"])


def test_argo_engine_helper_add_name_to_workflow():
    """tests generated workflow name added to gwas workflow"""
    workflow_name = "wf_123"
    argo_engine_helper.generate_workflow_name = mock.MagicMock(
        return_value=workflow_name
    )
    argo_engine_helper.add_name_to_workflow(workflow_yaml)

    assert workflow_yaml["metadata"]["name"] == workflow_name


def test_argo_engine_helper_prod_add_scaling_groups():
    """tests scaling groups in prod are added"""
    config = {"scaling_groups": {"test_user": (group := "group_1")}}

    argo_engine_helper._get_argo_config_dict = mock.MagicMock(return_value=config)
    argo_engine_helper.add_scaling_groups("test_user", workflow_yaml)

    assert workflow_yaml["spec"]["nodeSelector"]["role"] == group


def test_argo_engine_helper_qa_add_scaling_groups():
    """tests scaling groups in qa do not exist"""
    config = {"qa_scaling_groups": {"test_user": (group := "group_1")}}

    argo_engine_helper._get_argo_config_dict = mock.MagicMock(return_value=config)
    argo_engine_helper.add_scaling_groups("test_user", workflow_yaml)

    assert workflow_yaml["spec"].get("nodeSelector") is None


def test_add_gen3user_label_and_annotation():
    """tests user label and annotations are added to workflow"""
    username_label_pair = UsernameLabelPair("abc123", "user-abc123")
    argo_engine_helper.add_gen3user_label_and_annotation(
        username_label_pair.username, workflow_yaml
    )

    assert (
        workflow_yaml["spec"]["podMetadata"]["labels"]["gen3username"]
        == username_label_pair.label
    )
    assert (
        workflow_yaml["metadata"]["labels"]["gen3username"] == username_label_pair.label
    )
    assert (
        workflow_yaml["spec"]["podMetadata"]["annotations"]["gen3username"]
        == username_label_pair.username
    )


UsernameLabelPair = namedtuple("UsernameLabelPair", "username label")
user_label_data = [
    UsernameLabelPair("abc123", "user-abc123"),
    UsernameLabelPair("48@!(CEab***", "user-48-40-21-28CEab-2a-2a-2a"),
    UsernameLabelPair("-scott.VA@gmail.com", "user--2dscott-2eVA-40gmail-2ecom"),
]


@pytest.mark.parametrize("username,label", user_label_data)
def test_convert_username_label_to_gen3username(username, label):
    assert argo_engine_helper.convert_gen3username_to_label(username) == label


@pytest.mark.parametrize("username,label", user_label_data)
def test_convert_gen3username_to_label(username, label):
    assert convert_username_label_to_gen3username(label) == username


WorkflowStatusData = namedtuple("WorkflowStatusData", "parsed_phase shutdown phase")
phase_shutdown_data = [
    WorkflowStatusData("Canceling", "Terminate", "Running"),
    WorkflowStatusData("Canceled", "Terminate", "Failed"),
    WorkflowStatusData("Running", "Running", "Running"),
]


@pytest.mark.parametrize("parsed_phase,shutdown,phase", phase_shutdown_data)
def test_parse_status(parsed_phase, shutdown, phase):
    """tests that status workflow get correct phase based on workflow shutdown and phase"""
    wf_status_dict = {
        "metadata": {"name": "test_wf"},
        "spec": {
            "arguments": "test_args",
            "shutdown": shutdown,
        },
        "status": {
            "phase": phase,
            "progress": "1/5",
        },
    }

    parsed_status = argo_engine_helper.parse_status(wf_status_dict)
    assert parsed_status.get("phase") == parsed_phase


def test_get_username_from_token():
    """tests context["user"]["name"] can be parsed from example auth header"""
    assert (
        argo_engine_helper.get_username_from_token(EXAMPLE_AUTH_HEADER) == "test user"
    )


def test_add_cohort_middleware_request():
    """tests cohort middleware parameters are added to gwas workflow"""
    config = {"environment": "default"}
    argo_engine_helper._get_argo_config_dict = mock.MagicMock(return_value=config)

    request_body = {
        "covariates": ["ID_2000006886", "ID_2000000324"],
        "outcome": "ID_2000006885",
        "source_id": 4,
        "cohort_definition_id": 70,
    }

    argo_engine_helper.add_cohort_middleware_request(request_body, workflow_yaml)
    for dict in workflow_yaml["spec"]["arguments"]["parameters"]:
        if dict.get("name") == "cohort_middleware_url":
            assert (
                dict["value"]
                == "http://cohort-middleware-service.default/cohort-data/by-source-id/4/by-cohort-definition-id/70"
            )
        if dict.get("name") == "cohort_middleware_body":
            assert (
                dict["value"]
                == '{"PrefixedConceptIds": ["ID_2000006886", "ID_2000000324", "ID_2000006885"]}'
            )


def test_setup_workspace_token_service():
    """tests workspace token service is working properly for indexd"""
    config = {"environment": "default"}
    argo_engine_helper._get_argo_config_dict = mock.MagicMock(return_value=config)

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.requests.get"
    ) as mock_get:
        mock_get.return_value = {"status_code": 400}

        assert (
            argo_engine_helper.setup_workspace_token_service(EXAMPLE_AUTH_HEADER)
            == False
        )

        mock_get.return_value = {"status_code": 403}

        argo_engine_helper.setup_workspace_token_service(EXAMPLE_AUTH_HEADER) == True
