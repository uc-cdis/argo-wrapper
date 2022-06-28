import importlib.resources as pkg_resources
import json
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


covariates = [
    {"variable_type": "concept", "prefixed_concept_id": "ID_2000000324"},
    {"variable_type": "concept", "prefixed_concept_id": "ID_2000000123"},
    {"variable_type": "custom_dichotomous", "cohort_ids": [1, 3]},
]
outcome = {"concept_type": "concept"}


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=None)
    config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict:
        mock_config_dict.return_value = config
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
            "gen3_user_name": "test_user",
            "covariates": covariates,
        }
        result = engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert "argo-wrapper" in result


def test_argo_engine_submit_failed():
    """returns empty string is workflow submission fails"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("bad input")
    )

    config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, pytest.raises(Exception):
        mock_config_dict.return_value = config
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
        }
        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)


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
    config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}
    input_parameters = {
        "pheno_csv_key": "test_replace_value",
        "n_pcs": 100,
        "template_version": "test",
        "gen3_user_name": "test_user",
        "covariates": covariates,
        "outcome": outcome,
    }
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict:
        mock_config_dict.return_value = config
        engine.workflow_submission(input_parameters, EXAMPLE_AUTH_HEADER)
        args = engine.api_instance.create_workflow.call_args_list
        for parameter in args[0][1]["body"]["workflow"]["spec"]["arguments"][
            "parameters"
        ]:
            if (
                param_name := parameter["name"]
            ) in input_parameters and param_name not in ("covariates", "outcome"):
                assert parameter["value"] == input_parameters[param_name]

            if param_name == "covariates":
                for index, covariate in enumerate(parameter["value"]):
                    assert covariate == json.dumps(
                        input_parameters[param_name][index], indent=0
                    )

            if param_name == "outcome":
                assert parameter["value"] == json.dumps(
                    input_parameters[param_name], indent=0
                )


def test_argo_engine_new_submit_succeeded():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock()
    request_body = {
        "n_pcs": 3,
        "covariates": covariates,
        "out_prefix": "vadc_genesis",
        "outcome": outcome,
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
        res = engine.workflow_submission(request_body, EXAMPLE_AUTH_HEADER)
        assert len(res) > 0


def test_argo_engine_new_submit_failed():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("workflow misformatted")
    )
    request_body = {
        "n_pcs": 3,
        "covariates": covariates,
        "out_prefix": "vadc_genesis",
        "outcome": outcome,
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
        res = engine.workflow_submission(request_body, EXAMPLE_AUTH_HEADER)
