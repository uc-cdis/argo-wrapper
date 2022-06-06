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

    parsed_status = argo_engine_helper.parse_status(wf_status_dict)
    assert parsed_status.get("phase") == parsed_phase


def test_get_username_from_token():
    """tests context["user"]["name"] can be parsed from example auth header"""
    assert (
        argo_engine_helper.get_username_from_token(EXAMPLE_AUTH_HEADER) == "test user"
    )
