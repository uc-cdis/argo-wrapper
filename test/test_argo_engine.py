import importlib.resources as pkg_resources
import unittest.mock as mock

import pytest
import yaml

from argowrapper import argo_workflows_templates
from argowrapper.constants import *
from argowrapper.engine.argo_engine import *
from test.constants import EXAMPLE_AUTH_HEADER


class WorkFlow:
    def __init__(self, items):
        self.items = items


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=workflow_name)
    stream = pkg_resources.open_text(argo_workflows_templates, WF_HEADER)
    workflow_yaml = yaml.safe_load(stream)
    engine._get_workflow_template = mock.MagicMock(return_value=workflow_yaml)

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ) as add_name, mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_gen3user_label_and_annotation"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_label"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_cohort_middleware_request"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.setup_workspace_token_service"
    ):
        add_name.return_value = workflow_name
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
            "gen3_user_name": "test_user",
            "covariates": ["123"],
        }
        result = engine.submit_workflow(parameters, "test_jwt_token")
        assert result == workflow_name


def test_argo_engine_submit_failed():
    """returns empty string is workflow submission fails"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("bad input")
    )
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), pytest.raises(
        Exception
    ):
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
        }
        engine.submit_workflow(parameters, "")


def test_argo_engine_cancel_succeeded():
    """returns True if workflow cancelation suceeds"""
    engine = ArgoEngine()
    engine.api_instance.terminate_workflow = mock.MagicMock(return_value=None)
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
    mock_return = {
        "metadata": {"name": "hello-world-mwnw5"},
        "spec": {"arguments": {}},
        "status": {
            "finishedAt": None,
            "phase": "Running",
            "progress": "0/1",
            "startedAt": "2022-03-22T18:56:48Z",
        },
        "outputs": {},
    }
    engine._get_workflow_status_dict = mock.MagicMock(return_value=mock_return)
    result = engine.get_workflow_status("test_wf")
    assert result["name"] == "hello-world-mwnw5"
    assert result["arguments"] == {}
    assert result["phase"] == "Running"
    assert result["progress"] == "0/1"
    assert result["startedAt"] == "2022-03-22T18:56:48Z"
    assert result["finishedAt"] == None
    assert result["outputs"] == {}


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

    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(workflows)
    )

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_label"
    ):
        result = engine.get_workfows_for_user("test_jwt_token")
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
    stream = pkg_resources.open_text(argo_workflows_templates, WF_HEADER)
    workflow_yaml = yaml.safe_load(stream)
    engine._get_workflow_template = mock.MagicMock(return_value=workflow_yaml)
    input_parameters = {
        "pheno_csv_key": "test_replace_value",
        "n_pcs": 100,
        "template_version": "test",
        "gen3_user_name": "test_user",
        "covariates": ["123"],
    }
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_name_to_workflow"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_scaling_groups"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_gen3user_label_and_annotation"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.add_cohort_middleware_request"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.setup_workspace_token_service"
    ):
        engine.submit_workflow(input_parameters, "")
        args = engine.api_instance.create_workflow.call_args_list
        for parameter in args[0][1]["body"]["workflow"]["spec"]["arguments"][
            "parameters"
        ]:
            if (
                param_name := parameter["name"]
            ) in input_parameters and not "covariates":
                assert parameter["value"] == input_parameters[param_name]
            elif param_name == "covariates":
                assert parameter["value"] == " ".join(input_parameters["covariates"])


def test_argo_engine_new_submit_succeeded():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock()
    request_body = {
        "n_pcs": 3,
        "covariates": ["ID_2000006886", "ID_2000000324"],
        "out_prefix": "vadc_genesis",
        "outcome": "ID_2000006885",
        "outcome_is_binary": "false",
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "template_version": "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
        "source_id": 4,
        "cohort_definition_id": 70,
    }

    config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict:
        mock_config_dict.return_value = config
        res = engine.new_workflow_submission(request_body, EXAMPLE_AUTH_HEADER)
        assert len(res) > 0


def test_argo_engine_new_submit_failed():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("workflow misformatted")
    )
    request_body = {
        "n_pcs": 3,
        "covariates": ["ID_2000006886", "ID_2000000324"],
        "out_prefix": "vadc_genesis",
        "outcome": "ID_2000006885",
        "outcome_is_binary": "false",
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "template_version": "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
        "source_id": 4,
        "cohort_definition_id": 70,
    }

    config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, pytest.raises(Exception):
        mock_config_dict.return_value = config
        res = engine.new_workflow_submission(request_body, EXAMPLE_AUTH_HEADER)
