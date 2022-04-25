from collections import namedtuple
import unittest.mock as mock
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
import importlib.resources as pkg_resources
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
import yaml
import pytest
import re


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
    parameters = {"pheno_csv_key": "test_replace_value", "n_pcs": 100}
    argo_engine_helper.add_parameters_to_gwas_workflow(parameters, workflow_yaml)

    parameter_dicts = [
        parameter_dict
        for parameter_dict in workflow_yaml["spec"]["arguments"]["parameters"]
    ]
    for dict in parameter_dicts:
        if (param_name := dict["name"]) in parameters:
            assert dict["value"] == parameters[param_name]


def test_argo_engine_helper_add_name_to_workflow():
    workflow_name = "wf_123"
    argo_engine_helper.generate_workflow_name = mock.MagicMock(
        return_value=workflow_name
    )
    argo_engine_helper.add_name_to_workflow(workflow_yaml)

    assert "generateName" not in workflow_yaml["metadata"]
    assert workflow_yaml["metadata"]["name"] == workflow_name


def test_argo_engine_helper_add_scaling_groups():
    config = {"scaling_groups": {"test_user": (group := "group_1")}}

    argo_engine_helper._get_argo_config_dict = mock.MagicMock(return_value=config)
    argo_engine_helper.add_scaling_groups("test_user", workflow_yaml)

    assert workflow_yaml["spec"]["nodeSelector"]["role"] == group


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
