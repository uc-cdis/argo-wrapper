import importlib.resources as pkg_resources
import json
import unittest.mock as mock

import pytest
import yaml

from argo_workflows.exceptions import NotFoundException
from argowrapper import argo_workflows_templates
from argowrapper.constants import *
from argowrapper.engine.argo_engine import *
from test.constants import EXAMPLE_AUTH_HEADER


class WorkFlow:
    def __init__(self, items):
        self.items = items


variables = [
    {"variable_type": "concept", "concept_id": "2000000324"},
    {"variable_type": "concept", "concept_id": "2000000123"},
    {"variable_type": "custom_dichotomous", "cohort_ids": [1, 3]},
]
outcome = 1

VARIABLES_IN_STRING_FORMAT = "[{'variable_type': 'concept', 'concept_id': 2000006886},{'variable_type': 'concept', 'concept_id': 2000006885},{'variable_type': 'custom_dichotomous', 'cohort_ids': [301, 401], 'provided_name': 'My Custom Dichotomous'}]"


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=None)
    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict:
        mock_config_dict.return_value = config
        parameters = {
            "pheno_csv_key": "test_replace_value",
            "n_pcs": 100,
            "template_version": "test",
            "gen3_user_name": "test_user",
            "variables": variables,
        }
        result = engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert "gwas" in result


def test_argo_engine_submit_failed():
    """returns empty string is workflow submission fails"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("bad input")
    )

    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}

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


def test_argo_engine_get_status_archived_workflow_succeeded():
    engine = ArgoEngine()
    mock_return_archived_wf = {
        "metadata": {
            "name": "archived_wf",
            "annotations": {"workflow_name": "custom_name"},
        },
        "spec": {"arguments": "test_args"},
        "status": {
            "phase": "Succeeded",
            "progress": "7/7",
            "startedAt": "test_starttime",
            "finishedAt": "test_finishtime",
            "outputs": {},
        },
    }
    engine._get_archived_workflow_status_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )
    archived_wf_status = engine.get_workflow_status("archived_wf", "archived_uid")
    assert archived_wf_status["wf_name"] == "custom_name"
    assert archived_wf_status["progress"] == "7/7"
    assert archived_wf_status["outputs"] == {}


def test_argo_engine_get_status_workflow_succeeded():
    """Test active workflow status when uid is not found in archive workflow endpoint"""
    engine = ArgoEngine()
    mock_return_wf = {
        "metadata": {
            "name": "hello-world-mwnw5",
            "annotations": {"workflow_name": "custome_wf_name"},
        },
        "spec": {"arguments": {}},
        "status": {
            "finishedAt": None,
            "phase": "Running",
            "progress": "0/1",
            "startedAt": "2022-03-22T18:56:48Z",
            "outputs": {},
        },
    }
    engine._get_archived_workflow_status_dict = mock.MagicMock(
        side_effect=NotFoundException
    )
    engine._get_workflow_status_dict = mock.MagicMock(return_value=mock_return_wf)
    wf_status = engine.get_workflow_status("test_wf", "wf_uid")
    assert wf_status["wf_name"] == "custome_wf_name"
    assert wf_status["phase"] == "Running"
    assert wf_status["progress"] == "0/1"


def test_argo_engine_get_status_failed():
    """returns empty string if workflow get status fails at archived workflow endpoint"""
    engine = ArgoEngine()
    engine._get_archived_workflow_status_dict = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    with pytest.raises(Exception):
        engine.get_workflow_status("test_wf")


def test_argo_engine_get_workflows_for_user_suceeded():
    """returns list of workflow names if get workflows for user suceeds"""
    engine = ArgoEngine()
    argo_workflows_mock_raw_response = [
        {
            "metadata": {"name": "workflow_one", "namespace": "argo", "uid": "uid_one"},
            "spec": {"arguments": {}, "shutdown": "Terminate"},
            "status": {
                "phase": "Failed",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": "2022-03-22T18:58:48Z",
            },
        },
        {
            "metadata": {"name": "workflow_two", "namespace": "argo", "uid": "uid_2"},
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
    ]
    argo_archived_workflows_mock_raw_response = [
        {
            "metadata": {"name": "workflow_two", "namespace": "argo", "uid": "uid_2"},
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
        {
            "metadata": {"name": "workflow_three", "namespace": "argo", "uid": "uid_3"},
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2023-02-03T18:56:48Z",
                "finishedAt": None,
            },
        },
    ]

    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_workflows_mock_raw_response)
    )
    engine.archive_api_instance.list_archived_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_archived_workflows_mock_raw_response)
    )

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_label"
    ):
        uniq_workflow_list = engine.get_workfows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 3
        assert "Canceled" == uniq_workflow_list[0]["phase"]
        assert "workflow_three" == uniq_workflow_list[2]["name"]


def test_argo_engine_get_workflows_for_user_failed():
    """returns error message if get workflows for user fails"""
    engine = ArgoEngine()
    engine.api_instance.list_workflows = mock.MagicMock(
        side_effect=Exception("user does not exist")
    )
    engine.archive_api_instance.list_archived_workflows = mock.MagicMock(
        side_effect=Exception("user does not exist")
    )
    with pytest.raises(Exception):
        engine.get_workfows_for_user("test")


def test_argo_engine_get_workflows_for_user_empty():
    """Worklfow list of active workflow is empty"""
    engine = ArgoEngine()
    argo_workflows_mock_raw_response = None
    argo_archived_workflows_mock_raw_response = [
        {
            "metadata": {"name": "workflow_two", "namespace": "argo", "uid": "uid_2"},
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
        {
            "metadata": {"name": "workflow_three", "namespace": "argo", "uid": "uid_3"},
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2023-02-03T18:56:48Z",
                "finishedAt": None,
            },
        },
    ]
    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_workflows_mock_raw_response)
    )
    engine.archive_api_instance.list_archived_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_archived_workflows_mock_raw_response)
    )
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_label"
    ):
        uniq_workflow_list = engine.get_workfows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 2
        assert "Succeeded" == uniq_workflow_list[0]["phase"]
        assert "workflow_three" == uniq_workflow_list[1]["name"]


def test_argo_engine_get_workflows_for_user_empty_both():
    """Both workfow list of active workflow and archived workflow are empty"""
    engine = ArgoEngine()
    argo_workflows_mock_raw_response = None
    argo_archived_workflows_mock_raw_response = None
    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_workflows_mock_raw_response)
    )
    engine.archive_api_instance.list_archived_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_archived_workflows_mock_raw_response)
    )
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_label"
    ):
        uniq_workflow_list = engine.get_workfows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 0


def test_argo_engine_submit_yaml_succeeded():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock()
    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
    input_parameters = {
        "pheno_csv_key": "test_replace_value",
        "n_pcs": 100,
        "template_version": "test",
        "gen3_user_name": "test_user",
        "variables": variables,
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
            ) in input_parameters and param_name not in ("variables"):
                assert parameter["value"] == input_parameters[param_name]

            if param_name == "variables":
                result = parameter["value"].replace("\n", "")
                for variable in input_parameters[param_name]:
                    for key in variable:
                        assert str(key) in result


def test_argo_engine_new_submit_succeeded():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock()
    request_body = {
        "n_pcs": 3,
        "variables": variables,
        "out_prefix": "vadc_genesis",
        "outcome": outcome,
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "template_version": "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
        "source_id": 4,
        "cohort_definition_id": 70,
    }

    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
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
        "variables": variables,
        "out_prefix": "vadc_genesis",
        "outcome": outcome,
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "template_version": "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
        "source_id": 4,
        "cohort_definition_id": 70,
    }

    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, pytest.raises(Exception):
        mock_config_dict.return_value = config
        res = engine.workflow_submission(request_body, EXAMPLE_AUTH_HEADER)


def test_argo_engine_get_archived_workflow_log_succeeded():
    """
    Fetch workflow details at archived workflow endpoint
    """
    engine = ArgoEngine()
    mock_return_archived_wf = {
        "metadata": {"name": "archived_wf"},
        "spec": {"arguments": "test_args"},
        "status": {
            "phase": "Failed",
            "nodes": {
                "step_one_name": {
                    "name": "step_one_name",
                    "templateName": "step_one_template",
                    "message": "Error (exit code 126)",
                    "phase": "Failed",
                }
            },
        },
    }
    engine._get_archived_workflow_status_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )
    archived_workflow_errors = engine.get_workflow_logs("archived_wf", "archived_uid")
    assert len(archived_workflow_errors) == 1
    assert archived_workflow_errors[0]["name"] == "step_one_name"
    assert archived_workflow_errors[0]["step_template"] == "step_one_template"
    assert archived_workflow_errors[0]["error_message"] == "Error (exit code 126)"


def test_argo_engine_get_workflow_log_succeeded():
    """
    Fetch workflow details at workflow endpoint, but failed to fetch at archived workflow endpoint
    """
    engine = ArgoEngine()
    mock_return_archived_wf = {"code": 5, "message": "not found"}
    mock_return_wf = {
        "status": {
            "phase": "Failed",
            "nodes": {
                "step_one_name": {
                    "name": "step_one_name",
                    "templateName": "step_one_template",
                    "message": "Error (exit code 126)",
                    "phase": "Failed",
                }
            },
        }
    }
    engine._get_archived_workflow_status_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )
    engine._get_workflow_log_dict = mock.MagicMock(return_value=mock_return_wf)
    workflow_errors = engine.get_workflow_logs("active_wf", "wf_uid")
    assert len(workflow_errors) == 1
    assert workflow_errors[0]["name"] == "step_one_name"
    assert workflow_errors[0]["step_template"] == "step_one_template"
    assert workflow_errors[0]["error_message"] == "Error (exit code 126)"
