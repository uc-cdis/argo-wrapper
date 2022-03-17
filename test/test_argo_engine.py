import unittest.mock as mock
from argowrapper.engine.argo_engine import *
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
import yaml
import pytest

import importlib.resources as pkg_resources


class WorkFlow:
    def __init__(self, items):
        self.items = items


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=workflow_name)
    stream = pkg_resources.open_text(argo_workflows_templates, TEST_WF)
    workflow_yaml = yaml.safe_load(stream)
    engine._get_workflow_template = mock.MagicMock(return_value=workflow_yaml)

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ) as add_name, mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ):
        add_name.return_value = workflow_name
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
            "gen3_user_name": "test_user",
        }
        result = engine.submit_workflow(parameters)
        assert result == workflow_name


def test_argo_engine_submit_failed():
    """returns empty string is workflow submission fails"""
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("bad input")
    )
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ) as add_name, mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ), pytest.raises(
        Exception
    ):
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
        }
        engine.submit_workflow(parameters)


def test_argo_engine_cancel_succeeded():
    """returns True if workflow cancelation suceeds"""
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(return_value=None)
    result = engine.cancel_workflow("wf_name")
    assert result == "wf_name canceled sucessfully"


def test_argo_engine_cancel_failed():
    """returns False if workflow cancelation fails"""
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    with pytest.raises(Exception):
        engine.cancel_workflow("wf_name")


def test_argo_engine_get_status_succeeded():
    """returns "running" for a running workflow if workflow get status suceeds"""
    engine = ArgoEngine()
    engine._get_workflow_status_dict = mock.MagicMock(
        return_value={"status": {"phase": "running"}}
    )
    result = engine.get_workflow_status("test_wf")
    assert result == "running"


def test_argo_engine_get_status_failed():
    """returns empty string if workflow get status fails"""
    engine = ArgoEngine()
    engine._get_workflow_status_dict = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    with pytest.raises(Exception):
        engine.get_workflow_status("test_wf")


def test_argo_engine_get_workflow_for_user_suceeded():
    """returns list of workflow names if get workflows for user suceeds"""
    engine = ArgoEngine()
    workflows = [
        {"metadata": {"name": "archieved_name"}},
        {"metadata": {"name": "running_name"}},
    ]
    archived_workflows = [{"metadata": {"name": "archieved_name"}}]

    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(workflows)
    )
    engine.archeive_api_instance.list_archived_workflows = mock.MagicMock(
        return_value=WorkFlow(archived_workflows)
    )

    result = engine.get_workfows_for_user("test")
    assert len(result) == 2
    assert "archieved_name" in result
    assert "running_name" in result


def test_argo_engine_get_workflow_for_user_failed():
    """returns error message if get workflows for user fails"""
    engine = ArgoEngine()
    engine.api_instance.list_workflows = mock.MagicMock(
        side_effect=Exception("user does not exist")
    )
    with pytest.raises(Exception):
        engine.get_workfows_for_user("test")


def test_argo_engine_submit_yaml_succeeded():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock()
    stream = pkg_resources.open_text(argo_workflows_templates, TEST_WF)
    workflow_yaml = yaml.safe_load(stream)
    engine._get_workflow_template = mock.MagicMock(return_value=workflow_yaml)
    input_parameters = {
        "pheno_csv_key": "test_replace_value",
        "n_pcs": 100,
        "template_version": "test",
        "gen3_user_name": "test_user",
    }
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ) as add_name, mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ):
        engine.submit_workflow(input_parameters)
        args = engine.api_instance.create_workflow.call_args_list
        for parameter in args[0][1]["body"]["workflow"]["spec"]["arguments"][
            "parameters"
        ]:
            if (param_name := parameter["name"]) in input_parameters:
                assert parameter["value"] == input_parameters[param_name]
