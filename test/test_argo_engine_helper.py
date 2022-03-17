import unittest.mock as mock
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
import importlib.resources as pkg_resources
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
import yaml
import pytest


@pytest.fixture(scope="module")
def setup():
    print("*****SETUP*****")
    stream = pkg_resources.open_text(argo_workflows_templates, TEST_WF)
    workflow_yaml = yaml.safe_load(stream)
    yield


stream = pkg_resources.open_text(argo_workflows_templates, TEST_WF)
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

    assert workflow_yaml["spec"]["node_selector"]["role"] == group
    assert workflow_yaml["spec"]["tolerations"][0]["value"] == group
