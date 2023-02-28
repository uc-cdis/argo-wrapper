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
    if match := special_character_match.group():
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

    archived_wf_status_dict = {
        "metadata": {
            "name": "test_archived_wf",
            "annotations": {
                "workflow_name": "archived_wf_name"
            }
        },
        "spec": {
            "arguments": "test_args"
        },
        "status": {
            "phase": "Succeeded",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
            "progress": "7/7",
            "outputs": {}
        }

    }
    parsed_status = argo_engine_helper.parse_status(wf_status_dict, "active_workflow")
    archived_parsed_status = argo_engine_helper.parse_status(archived_wf_status_dict, "archived_workflow")
    assert parsed_status.get("phase") == parsed_phase
    assert archived_parsed_status.get("wf_name") == "archived_wf_name"


def test_parse_list_item():
    """tests that workflow list item get correct phase based on workflow shutdown and phase"""
    wf_list_item = {
        "metadata": {
            "name": "test_wf",
            "uid": "test_uid",
            "namespace": "argo",
            "creationTimestamp": "test_starttime"

        },
        "spec": {
            "arguments": "test_args",
            "shutdown": "Terminate"
        },
        "status": {
            "phase": "Running",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime"
        }
    }
    archived_workflow_list_item = {
        "metadata" : {
            "name": "test_wf_archived",
            "uid": "test_uid_archived",
            "namespace": "argo",
            "creationTimestamp": "test_starttime_archived"
        },
        "spec": {
            "arguments": {}
        },
        "status": {
            "phase": "Succeeded",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime"
        }
    }
    parsed_list_item = argo_engine_helper.parse_list_item(wf_list_item, "active_workflow")
    parsed_list_item_archived = argo_engine_helper.parse_list_item(archived_workflow_list_item, "archived_workflow")
    assert parsed_list_item.get("phase") == "Canceling"
    assert parsed_list_item_archived.get("name") == "test_wf_archived"


def test_remove_list_duplicates():
    """tests that remove_list_duplicates is able to only contain workflows with unique workflow uid"""
    active_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end"
        }
    ]
    archived_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end"
        },
        {
            "name": "test_wf_2",
            "uid": "test_wf_2_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end"
        }
    ]
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(active_wf_list, archived_wf_list)
    assert len(uniq_wf_list) == 2

def test_remove_list_duplicates_both_empty():
    """Test that remove_list_duplicates is able to handle empty list input"""
    active_wf_list = []
    archived_wf_list = []
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(active_wf_list, archived_wf_list)
    assert len(uniq_wf_list) == 0

def test_remove_list_duplicates_one_empty():
    """Test that remove_list_duplicates is able to handle a single empty list input"""
    archived_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end"
        },
        {
            "name": "test_wf_2",
            "uid": "test_wf_2_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end"
        }
    ]
    active_wf_list = []
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(active_wf_list, archived_wf_list)
    assert len(uniq_wf_list) == 2
    assert "test_wf_2" == uniq_wf_list[1]["name"]

def test_get_username_from_token():
    """tests context["user"]["name"] can be parsed from example auth header"""
    assert (
        argo_engine_helper.get_username_from_token(EXAMPLE_AUTH_HEADER) == "test user"
    )


def test__convert_request_body_to_parameter_dict():
    request_body = {
        "source_id": 1,
        "study_population_cohort": 123,
        "case_cohort_definition_id": 456,
        "control_cohort_definition_id": 789,
        "variables": [
            {"variable_type": "concept", "concept_id": 2000000324},
            {"variable_type": "concept", "concept_id": 2000006885},
            {"variable_type": "concept", "concept_id": 2000007027},
            {
                "variable_type": "custom_dichotomous",
                "provided_name": "my outcome",
                "cohort_ids": [1, 99],
            },
        ],
        "hare_population": "Hispanic",
        "hare_concept_id": 2000007027,
        "out_prefix": "abc",
        "outcome": {"variable_type": "concept", "concept_id": 2000001234},
        "n_pcs": 3,
        "maf_threshold": 0.5,
        "imputation_score_cutoff": 0.3,
    }
    result = argo_engine_helper._convert_request_body_to_parameter_dict(
        request_body=request_body
    )
    # expect the same as above, but with complex values stringified:
    expected_result = {
        "source_id": 1,
        "study_population_cohort": 123,
        "case_cohort_definition_id": 456,
        "control_cohort_definition_id": 789,
        "variables": '[\n{\n"variable_type": "concept",\n"concept_id": 2000000324\n},\n{\n"variable_type": "concept",\n"concept_id": 2000006885\n},\n{\n"variable_type": "concept",\n"concept_id": 2000007027\n},\n{\n"variable_type": "custom_dichotomous",\n"provided_name": "my outcome",\n"cohort_ids": [\n1,\n99\n]\n}\n]',
        "hare_population": "Hispanic",
        "hare_concept_id": 2000007027,
        "out_prefix": "abc",
        "outcome": '{\n"variable_type": "concept",\n"concept_id": 2000001234\n}',
        "n_pcs": 3,
        "maf_threshold": 0.5,
        "imputation_score_cutoff": 0.3,
    }
    assert len(expected_result.items()) == len(result.items())
    for key, value in expected_result.items():
        assert value == result[key]
