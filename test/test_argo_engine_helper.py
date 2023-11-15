import importlib.resources as pkg_resources
import re
import unittest.mock as mock
from collections import namedtuple

import pytest
import yaml

import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
from test.constants import EXAMPLE_AUTH_HEADER, EXAMPLE_JUST_TOKEN


def _convert_to_label(special_character_match: str) -> str:
    if match := special_character_match.group():
        match = match.strip("-")
        byte_array = bytearray.fromhex(match)
        return byte_array.decode()


def convert_username_label_to_gen3username(label: str) -> str:
    """this function will reverse the conversion of a username to label as
    defined by the convert_gen3username_to_pod_label function. eg "user--21" -> "!"

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


UsernameLabelPair = namedtuple("UsernameLabelPair", "username label")
user_label_data = [
    UsernameLabelPair("abc123", "user-abc123"),
    UsernameLabelPair("48@!(CEab***", "user-48-40-21-28CEab-2a-2a-2a"),
    UsernameLabelPair("-scott.VA@gmail.com", "user--2dscott-2eVA-40gmail-2ecom"),
]


@pytest.mark.parametrize("username,label", user_label_data)
def test_convert_username_label_to_gen3username(username, label):
    assert argo_engine_helper.convert_gen3username_to_pod_label(username) == label


@pytest.mark.parametrize("username,label", user_label_data)
def test_convert_gen3username_to_pod_label(username, label):
    assert convert_username_label_to_gen3username(label) == username


def test_convert_gen3teamproject_to_pod_label_and_back():
    team_project = "/gwas_projects/project2"
    pod_label = argo_engine_helper.convert_gen3teamproject_to_pod_label(team_project)
    assert pod_label == "2f677761735f70726f6a656374732f70726f6a65637432"
    converted_team_project = argo_engine_helper.convert_pod_label_to_gen3teamproject(
        pod_label
    )
    assert team_project == converted_team_project


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
        "metadata": {
            "name": "test_wf",
            "labels": {},
        },
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
            "annotations": {"workflow_name": "archived_wf_name"},
            "labels": {},
        },
        "spec": {"arguments": "test_args"},
        "status": {
            "phase": "Succeeded",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
            "progress": "7/7",
            "outputs": {},
        },
    }
    parsed_details = argo_engine_helper.parse_details(wf_status_dict, "active_workflow")
    archived_parsed_details = argo_engine_helper.parse_details(
        archived_wf_status_dict, "archived_workflow"
    )
    assert parsed_details.get("phase") == parsed_phase
    assert archived_parsed_details.get("wf_name") == "archived_wf_name"


def test_parse_common_details():
    """tests that workflow list item get correct phase based on workflow shutdown and phase"""
    workflow_item = {
        "metadata": {
            "name": "test_wf",
            "uid": "test_uid",
            "namespace": "argo",
            "creationTimestamp": "test_starttime",
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
                GEN3_TEAM_PROJECT_METADATA_LABEL: "dummyteam",
            },
        },
        "spec": {"arguments": "test_args", "shutdown": "Terminate"},
        "status": {
            "phase": "Running",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
        },
    }
    archived_workflow_item = {
        "metadata": {
            "name": "test_wf_archived",
            "uid": "test_uid_archived",
            "namespace": "argo",
            "creationTimestamp": "test_starttime_archived",
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
            },
        },
        "status": {
            "phase": "Succeeded",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
        },
    }
    parsed_item = argo_engine_helper.parse_common_details(
        workflow_item, "active_workflow"
    )
    parsed_item_archived = argo_engine_helper.parse_common_details(
        archived_workflow_item, "archived_workflow"
    )
    assert parsed_item.get("phase") == "Canceling"
    assert parsed_item_archived.get("name") == "test_wf_archived"


def test_parse_details():
    workflow_item = {
        "metadata": {
            "name": "test_wf",
            "annotations": {"workflow_name": "custom_name"},
            "uid": "test_uid",
            "namespace": "argo",
            "creationTimestamp": "test_starttime",
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
                GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                    "dummyteam"
                ),
            },
        },
        "spec": {"arguments": "test_args", "shutdown": "Terminate"},
        "status": {
            "phase": "Running",
            "progress": "1/5",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
            "outputs": {"out1": "one"},
        },
    }

    parsed_item = argo_engine_helper.parse_details(workflow_item, "active_workflow")
    assert parsed_item.get("phase") == "Canceling"
    assert parsed_item.get(GEN3_USER_METADATA_LABEL) == "dummyuser"
    assert parsed_item.get(GEN3_TEAM_PROJECT_METADATA_LABEL) == "dummyteam"
    assert parsed_item.get("wf_name") == "custom_name"
    assert parsed_item.get("arguments") == "test_args"
    assert parsed_item.get("progress") == "1/5"
    assert parsed_item.get("outputs") == {"out1": "one"}

    parsed_item = argo_engine_helper.parse_details(workflow_item, "archived_workflow")
    assert parsed_item.get("phase") == "Running"
    assert parsed_item.get(GEN3_USER_METADATA_LABEL) == "dummyuser"
    assert parsed_item.get(GEN3_TEAM_PROJECT_METADATA_LABEL) == "dummyteam"
    assert parsed_item.get("wf_name") == "custom_name"
    assert parsed_item.get("arguments") == "test_args"
    assert parsed_item.get("progress") == "1/5"
    assert parsed_item.get("outputs") == {"out1": "one"}


def test_parse_list_item():
    workflow_item = {
        "metadata": {
            "name": "test_wf",
            "annotations": {"workflow_name": "custom_name"},
            "uid": "test_uid",
            "namespace": "argo",
            "creationTimestamp": "test_creationtime",
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
                GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                    "dummyteam"
                ),
            },
        },
        "spec": {"shutdown": "Terminate"},
        "status": {
            "phase": "Running",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
        },
    }

    parsed_item = argo_engine_helper.parse_list_item(workflow_item, "active_workflow")
    assert parsed_item.get("name") == "test_wf"
    assert parsed_item.get("phase") == "Canceling"
    assert parsed_item.get("submittedAt") == "test_creationtime"
    assert parsed_item.get("startedAt") == "test_starttime"
    assert parsed_item.get("finishedAt") == "test_finishtime"
    assert parsed_item.get("wf_name") == "custom_name"
    assert parsed_item.get("uid") == "test_uid"

    def dummy_get_archived_workflow_wf_name_and_team_project(workflow_uid):
        return "dummy_wf_name", "dummy_team_project"

    parsed_item = argo_engine_helper.parse_list_item(
        workflow_item,
        "archived_workflow",
        dummy_get_archived_workflow_wf_name_and_team_project,
    )
    assert parsed_item.get("wf_name") == "dummy_wf_name"
    assert parsed_item.get(GEN3_TEAM_PROJECT_METADATA_LABEL) == "dummy_team_project"


def test_remove_list_duplicates():
    """tests that remove_list_duplicates is able to only contain workflows with unique workflow uid"""
    active_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        }
    ]
    archived_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        },
        {
            "name": "test_wf_2",
            "uid": "test_wf_2_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        },
    ]
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(
        active_wf_list, archived_wf_list
    )
    assert len(uniq_wf_list) == 2


def test_remove_list_duplicates_no_duplicates():
    """tests that remove_list_duplicates also works in the scenario where there is nothing to do (lists are already unique)"""
    active_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        }
    ]
    archived_wf_list = [
        {
            "name": "test_wf_2",
            "uid": "test_wf_2_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        },
    ]
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(
        active_wf_list, archived_wf_list
    )
    assert len(uniq_wf_list) == 2


def test_remove_list_duplicates_both_empty():
    """Test that remove_list_duplicates is able to handle empty list input"""
    active_wf_list = []
    archived_wf_list = []
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(
        active_wf_list, archived_wf_list
    )
    assert len(uniq_wf_list) == 0


def test_remove_list_duplicates_one_empty():
    """Test that remove_list_duplicates is able to handle a single empty list input"""
    archived_wf_list = [
        {
            "name": "test_wf_1",
            "uid": "test_wf_1_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        },
        {
            "name": "test_wf_2",
            "uid": "test_wf_2_uid",
            "phase": "Succeeded",
            "startedAt": "test_start",
            "finishedAt": "test_end",
        },
    ]
    active_wf_list = []
    uniq_wf_list = argo_engine_helper.remove_list_duplicate(
        active_wf_list, archived_wf_list
    )
    assert len(uniq_wf_list) == 2
    assert "test_wf_2" == uniq_wf_list[1]["name"]


def test_get_username_from_token():
    """tests context["user"]["name"] can be parsed from example auth header"""
    assert (
        argo_engine_helper.get_username_from_token(EXAMPLE_AUTH_HEADER) == "test user"
    )
    assert argo_engine_helper.get_username_from_token(EXAMPLE_JUST_TOKEN) == "test user"


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
