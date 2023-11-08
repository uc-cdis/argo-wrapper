import unittest.mock as mock

import pytest
from argowrapper import logger

from argo_workflows.exceptions import NotFoundException
from argowrapper.constants import *
from argowrapper.engine.argo_engine import *
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper

from test.constants import EXAMPLE_AUTH_HEADER
from argowrapper.workflows.argo_workflows.gwas import *


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
            "team_project": "dummy-team-project",
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


def test_argo_engine_retry_succeeded_non_archived_workflow():
    """returns True if workflow retry suceeds"""
    engine = ArgoEngine()
    engine.archive_api_instance.retry_archived_workflow = mock.MagicMock(
        side_effect=NotFoundException("workflow does not exist")
    )
    engine.api_instance.retry_workflow = mock.MagicMock(return_value=None)
    result = engine.retry_workflow("wf_name", "uid")
    assert result == "wf_name retried sucessfully"


def test_argo_engine_retry_succeeded_archived_workflow():
    """checks if expected exception is raised when retry fails"""
    engine = ArgoEngine()
    engine.api_instance.retry_workflow = mock.MagicMock(
        side_effect=NotFoundException("workflow does not exist")
    )
    engine.archive_api_instance.retry_archived_workflow = mock.MagicMock(
        return_value=None
    )
    result = engine.retry_workflow("wf_name", "uid")
    assert result == "archived wf_name retried sucessfully"


def test_argo_engine_retry_failed_scenario1(caplog):
    """checks if expected exception is raised when archived retry fails"""
    engine = ArgoEngine()
    engine.api_instance.retry_workflow = mock.MagicMock(
        side_effect=NotFoundException("workflow does not exist")
    )
    engine.archive_api_instance.retry_archived_workflow = mock.MagicMock(
        side_effect=Exception("other exception")
    )
    # we expect "other exception" in this case:
    with pytest.raises(Exception) as exception:
        engine.retry_workflow("wf_name", "uid")
    assert "other exception" in str(exception)


def test_argo_engine_retry_failed_scenario2(caplog):
    """checks if expected exception is raised when regular retry fails"""
    engine = ArgoEngine()
    engine.archive_api_instance.retry_archived_workflow = mock.MagicMock(
        side_effect=NotFoundException("workflow not found")
    )
    engine.api_instance.retry_workflow = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    # because the archived endpoint throws NotFoundException, and
    # this is handled in retry_workflow, we expect the second Exception:
    with pytest.raises(Exception) as exception:
        engine.retry_workflow("wf_name", "uid")
    assert "workflow does not exist" in str(exception)


def test_argo_engine_get_status_archived_workflow_succeeded():
    engine = ArgoEngine()
    mock_return_archived_wf = {
        "metadata": {
            "name": "archived_wf",
            "annotations": {"workflow_name": "custom_name"},
            "labels": {},
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
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )
    archived_wf_details = engine.get_workflow_details("archived_wf", "archived_uid")
    assert archived_wf_details["wf_name"] == "custom_name"
    assert archived_wf_details["progress"] == "7/7"
    assert archived_wf_details["outputs"] == {}


def test_argo_engine_get_workflow_details_succeeded():
    """Test active workflow status when uid is not found in archive workflow endpoint"""
    engine = ArgoEngine()
    mock_return_wf = {
        "metadata": {
            "name": "hello-world-mwnw5",
            "annotations": {"workflow_name": "custome_wf_name"},
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
                GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                    "dummyteam"
                ),
            },
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
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        side_effect=NotFoundException
    )
    engine._get_workflow_details_dict = mock.MagicMock(return_value=mock_return_wf)
    wf_details = engine.get_workflow_details("test_wf", "wf_uid")
    assert wf_details["wf_name"] == "custome_wf_name"
    assert wf_details["phase"] == "Running"
    assert wf_details["progress"] == "0/1"
    assert wf_details[GEN3_USER_METADATA_LABEL] == "dummyuser"
    assert wf_details[GEN3_TEAM_PROJECT_METADATA_LABEL] == "dummyteam"


def test_argo_engine_get_workflow_details_succeeded_no_team_project():
    """Test active workflow status when uid is not found in archive workflow endpoint
    and include a test for backwards compatibility regarding the optional
    GEN3_TEAM_PROJECT_METADATA_LABEL"""
    engine = ArgoEngine()
    mock_return_wf = {
        "metadata": {
            "name": "hello-world-mwnw5",
            "annotations": {"workflow_name": "custome_wf_name"},
            "labels": {GEN3_USER_METADATA_LABEL: "dummyuser"},
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
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        side_effect=NotFoundException
    )
    engine._get_workflow_details_dict = mock.MagicMock(return_value=mock_return_wf)
    wf_details = engine.get_workflow_details("test_wf", "wf_uid")
    assert wf_details["wf_name"] == "custome_wf_name"
    assert wf_details["phase"] == "Running"
    assert wf_details["progress"] == "0/1"
    assert wf_details[GEN3_USER_METADATA_LABEL] == "dummyuser"
    assert wf_details[GEN3_TEAM_PROJECT_METADATA_LABEL] is None


def test_argo_engine_get_status_failed():
    """returns empty string if workflow get status fails at archived workflow endpoint"""
    engine = ArgoEngine()
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    with pytest.raises(Exception):
        engine.get_workflow_details("test_wf")


def test_argo_engine_get_workflows_for_user_and_team_projects_suceeded():
    """returns list of workflow names if get workflows for user suceeds"""
    engine = ArgoEngine()
    argo_workflows_mock_raw_response = [
        {
            "metadata": {
                "annotations": {"workflow_name": "custom_name_active1"},
                "name": "workflow_one",
                "namespace": "argo",
                "uid": "uid_one",
                "creationTimestamp": "2023-03-22T16:48:51Z",
                "labels": {
                    GEN3_USER_METADATA_LABEL: "dummyuser",
                    GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                        "dummyteam"
                    ),
                },
            },
            "spec": {"arguments": {}, "shutdown": "Terminate"},
            "status": {
                "phase": "Failed",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": "2022-03-22T18:58:48Z",
            },
        },
        {
            "metadata": {
                "annotations": {"workflow_name": "custom_name_active2"},
                "name": "workflow_two",
                "namespace": "argo",
                "uid": "uid_2",
                "creationTimestamp": "2023-03-22T17:47:51Z",
                "labels": {
                    GEN3_USER_METADATA_LABEL: "dummyuser",
                    GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                        "dummyteam"
                    ),
                },
            },
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
    ]
    # archived workflows list response is slightly different from above (main relevant difference is the
    # missing "annotations" section in "metadata"):
    argo_archived_workflows_mock_raw_response = [
        {
            "metadata": {
                "name": "workflow_two",
                "namespace": "argo",
                "uid": "uid_2",
                "creationTimestamp": "2023-03-22T18:57:51Z",
                "labels": {
                    GEN3_USER_METADATA_LABEL: "dummyuser",
                    GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                        "dummyteam"
                    ),
                },
            },
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
        {
            "metadata": {
                "name": "workflow_three",
                "namespace": "argo",
                "uid": "uid_3",
                "creationTimestamp": "2023-03-22T19:59:59Z",
                "labels": {
                    GEN3_USER_METADATA_LABEL: "dummyuser",
                    GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                        "dummyteam"
                    ),
                },
            },
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2023-02-03T18:56:48Z",
                "finishedAt": None,
            },
        },
    ]
    # for archived workflows, the "annotations" section needs to be retrieved from a
    # separate endpoint, which is mocked here:
    mock_return_archived_wf = {
        "metadata": {
            "annotations": {"workflow_name": "custom_name_archived"},
            "labels": {
                GEN3_USER_METADATA_LABEL: "dummyuser",
                GEN3_TEAM_PROJECT_METADATA_LABEL: argo_engine_helper.convert_gen3teamproject_to_pod_label(
                    "dummyteam"
                ),
            },
        },
        "spec": {},
        "status": {},
    }
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )

    # replace call to Argo with hard-coded return value mock. Note that this means that
    # the filtering is not tested here. TODO - a system test is needed or a more ellaborate mock to test this part.
    engine.api_instance.list_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_workflows_mock_raw_response)
    )
    engine.archive_api_instance.list_archived_workflows = mock.MagicMock(
        return_value=WorkFlow(argo_archived_workflows_mock_raw_response)
    )

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_pod_label"
    ):
        uniq_workflow_list = engine.get_workflows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 3
        # assert on values as mapped in argo_engine_helper.parse_details():
        assert "Canceled" == uniq_workflow_list[0]["phase"]
        assert "workflow_three" == uniq_workflow_list[2]["name"]
        assert "custom_name_active1" == uniq_workflow_list[0]["wf_name"]
        assert "2023-03-22T16:48:51Z" == uniq_workflow_list[0]["submittedAt"]
        # preference is given to active workflows, so we expect [1] to have this name instead of custom_name_archived:
        assert "custom_name_active2" == uniq_workflow_list[1]["wf_name"]
        assert "2023-03-22T17:47:51Z" == uniq_workflow_list[1]["submittedAt"]
        # workflow [2] is archived:
        assert "custom_name_archived" == uniq_workflow_list[2]["wf_name"]
        assert "2023-03-22T19:59:59Z" == uniq_workflow_list[2]["submittedAt"]
        assert (
            GEN3_USER_METADATA_LABEL
            in engine.api_instance.list_workflows.call_args[1][
                "list_options_label_selector"
            ]
        )
        assert (
            GEN3_USER_METADATA_LABEL
            in engine.archive_api_instance.list_archived_workflows.call_args[1][
                "list_options_label_selector"
            ]
        )

        # test also the get_workflows_for_team_project:
        uniq_workflow_list = engine.get_workflows_for_team_project("dummyteam")
        assert len(uniq_workflow_list) == 3
        assert (
            engine.api_instance.list_workflows.call_args[1][
                "list_options_label_selector"
            ]
            == f"{GEN3_TEAM_PROJECT_METADATA_LABEL}={argo_engine_helper.convert_gen3teamproject_to_pod_label('dummyteam')}"
        )
        assert (
            engine.archive_api_instance.list_archived_workflows.call_args[1][
                "list_options_label_selector"
            ]
            == f"{GEN3_TEAM_PROJECT_METADATA_LABEL}={argo_engine_helper.convert_gen3teamproject_to_pod_label('dummyteam')}"
        )
        # get_workflows_for_team_projects should return the same items as get_workflows_for_team_project if queried with just the same team:
        uniq_workflow_list = engine.get_workflows_for_team_projects(["dummyteam"])
        assert len(uniq_workflow_list) == 3


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
        engine.get_workflows_for_user("test")


def test_argo_engine_get_workflows_for_user_empty():
    """Worklfow list of active workflow is empty"""
    engine = ArgoEngine()
    argo_workflows_mock_raw_response = None
    argo_archived_workflows_mock_raw_response = [
        {
            "metadata": {
                "name": "workflow_two",
                "namespace": "argo",
                "uid": "uid_2",
                "labels": {},
            },
            "spec": {"arguments": {}},
            "status": {
                "phase": "Succeeded",
                "startedAt": "2022-03-22T18:56:48Z",
                "finishedAt": None,
            },
        },
        {
            "metadata": {
                "name": "workflow_three",
                "namespace": "argo",
                "uid": "uid_3",
                "labels": {},
            },
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
    # for archived workflows, an extra "get details" call goes out
    # to complement missing parts that are not in the list call above,
    # so we need to mock an extra response:
    mock_return_archived_wf = {
        "metadata": {
            "annotations": {"workflow_name": "custom_name_archived"},
            "labels": {},
        },
        "spec": {},
        "status": {},
    }
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.get_username_from_token"
    ), mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_pod_label"
    ):
        uniq_workflow_list = engine.get_workflows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 2
        assert "Succeeded" == uniq_workflow_list[0]["phase"]
        assert "workflow_three" == uniq_workflow_list[1]["name"]
        # we return same mock reponse for both, so they end up getting the same mock wf_name:
        assert "custom_name_archived" == uniq_workflow_list[0]["wf_name"]
        assert "custom_name_archived" == uniq_workflow_list[1]["wf_name"]


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
        "argowrapper.engine.argo_engine.argo_engine_helper.convert_gen3username_to_pod_label"
    ):
        uniq_workflow_list = engine.get_workflows_for_user("test_jwt_token")
        assert len(uniq_workflow_list) == 0


def test_argo_engine_get_workflows_for_team_projects_and_user():
    """Test is user and 'team project' workflows are combined as a single output"""
    engine = ArgoEngine()
    user_workflows_mock_response = [
        {
            "uid": "uid_2",
        },
        {
            "uid": "uid_3",
        },
    ]

    team_project_workflows_mock_response = [
        {
            "uid": "uid_2",
        },
        {
            "uid": "uid_4",
        },
    ]
    engine.get_workflows_for_team_projects = mock.MagicMock(
        return_value=team_project_workflows_mock_response
    )
    engine.get_workflows_for_user = mock.MagicMock(
        return_value=user_workflows_mock_response
    )
    uniq_workflow_list = engine.get_workflows_for_team_projects_and_user(
        ["team1"], "test_user_jwt_token"
    )
    # Note that arguments above are not used. The only thing this test is testing is
    # whether the get_workflows_for_team_projects_and_user is taking both lists
    # and merging them based on uid value of the items
    assert len(uniq_workflow_list) == 3


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
        "team_project": "dummy-team-project",
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
        "team_project": "dummy-team-project",
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
        "team_project": "dummy-team-project",
    }

    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, pytest.raises(Exception):
        mock_config_dict.return_value = config
        res = engine.workflow_submission(request_body, EXAMPLE_AUTH_HEADER)


def test_argo_engine_get_archived_workflow_log_succeeded():
    """
    Fetch workflow error logs at archived workflow endpoint
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
                    "type": "Retry",
                    "displayName": "run-plots",
                    "templateName": "step_one_template",
                    "message": "Error (exit code 126)",
                    "phase": "Failed",
                }
            },
        },
    }
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        return_value=mock_return_archived_wf
    )
    engine._get_workflow_node_artifact = mock.MagicMock(
        return_value="Problem with mutate()"
    )
    archived_workflow_errors = engine.get_workflow_logs("archived_wf", "archived_uid")
    assert len(archived_workflow_errors) == 1
    assert archived_workflow_errors[0]["node_type"] == "Retry"
    assert archived_workflow_errors[0]["step_template"] == "step_one_template"
    assert (
        archived_workflow_errors[0]["error_interpreted"]
        == "Small cohort size or unbalanced cohort sizes."
    )


def test_argo_engine_get_workflow_log_succeeded():
    """
    Fetch workflow error logs at workflow endpoint, but failed to fetch at archived workflow endpoint
    """
    engine = ArgoEngine()
    mock_return_wf = {
        "status": {
            "phase": "Failed",
            "nodes": {
                "step_one_name": {
                    "name": "step_one_name",
                    "type": "Retry",
                    "displayName": "generate-attrition-csv",
                    "templateName": "step_one_template",
                    "message": "Error (exit code 126)",
                    "phase": "Failed",
                }
            },
        }
    }
    engine._get_archived_workflow_details_dict = mock.MagicMock(
        side_effect=NotFoundException("Not found")
    )
    engine._get_workflow_phase = mock.MagicMock(return_value="Failed")
    engine._get_workflow_node_artifact = mock.MagicMock(
        return_value="requests.exceptions.ReadTimeout\nHTTPConnectionPool"
    )

    engine._get_workflow_log_dict = mock.MagicMock(return_value=mock_return_wf)
    workflow_errors = engine.get_workflow_logs("active_wf", "wf_uid")
    assert len(workflow_errors) == 1
    assert workflow_errors[0]["name"] == "step_one_name"
    assert (
        workflow_errors[0]["error_interpreted"]
        == "Timeout occurred while fetching attrition table information. Please retry."
    )
    assert workflow_errors[0]["error_message"] == "Error (exit code 126)"
