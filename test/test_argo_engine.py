import unittest.mock as mock

import pytest
from argowrapper import logger

from argo_workflows.exceptions import NotFoundException
from argowrapper.constants import *
from argowrapper.engine.argo_engine import *
import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper

from test.constants import EXAMPLE_AUTH_HEADER
from argowrapper.workflows.argo_workflows.gwas import *
from unittest.mock import patch
from freezegun import freeze_time


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

parameters = {
    "pheno_csv_key": "test_replace_value",
    "n_pcs": 100,
    "template_version": "test",
    "gen3_user_name": "test_user",
    "variables": variables,
    "outcome": outcome,
    "team_project": "dummy-team-project",
}

tag_data = {}


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code != 200:
                raise Exception()

    if kwargs["url"] == "http://fence-service/user":
        if tag_data["user_tags"] != 500:
            return MockResponse(tag_data["user_tags"], 200)
        else:
            return MockResponse({}, 500)

    return None


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=None)
    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_id_and_limit, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_monthly_workflow_cap"
    ) as mock_check_workflow_cap:
        mock_config_dict.return_value = config
        mock_id_and_limit.return_value = None, None
        mock_check_workflow_cap.return_value = 1, 50

        result = engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert "gwas" in result


def test_argo_engine_submit_with_billing_id():
    """returns workflow name if workflow submission suceeds"""
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=None)
    config = {"environment": "default", "scaling_groups": {"default": "group_1"}}

    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_id_and_limit, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_monthly_workflow_cap"
    ) as mock_check_workflow_cap:
        mock_config_dict.return_value = config
        mock_id_and_limit.return_value = "1234", None
        mock_check_workflow_cap.return_value = 1, 50

        result = engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        workflow_yaml = engine.api_instance.create_workflow.call_args[1][
            "body"
        ]._data_store
        assert (
            workflow_yaml["workflow"]["metadata"]["labels"]["billing_id"]
            == workflow_yaml["workflow"]["spec"]["podMetadata"]["labels"]["billing_id"]
            == "1234"
        )
        assert (
            workflow_yaml["workflow"]["spec"]["podMetadata"]["labels"]["gen3username"]
            == ""
        )


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
                    GEN3_USER_METADATA_LABEL: "user-cdis-2edummy-test-40gmail-2ecom",
                    GEN3_TEAM_PROJECT_METADATA_LABEL: "",
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
                    GEN3_USER_METADATA_LABEL: "",
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
        assert len(uniq_workflow_list) == 1
        # assert on values as mapped in argo_engine_helper.parse_details():
        assert "Canceled" == uniq_workflow_list[0]["phase"]
        assert "custom_name_active1" == uniq_workflow_list[0]["wf_name"]
        assert "2023-03-22T16:48:51Z" == uniq_workflow_list[0]["submittedAt"]
        assert (
            "cdis.dummy-test@gmail.com"
            == uniq_workflow_list[0][GEN3_USER_METADATA_LABEL]
        )
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

        # leave out the one that has no team project, to simulate the argo query:
        engine.api_instance.list_workflows = mock.MagicMock(
            return_value=WorkFlow(argo_workflows_mock_raw_response[1:])
        )
        # test also the get_workflows_for_team_project:
        uniq_workflow_list = engine.get_workflows_for_team_project("dummyteam")
        assert len(uniq_workflow_list) == 2
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
        # get_workflows_for_team_projects should return the same items as get_workflows_for_team_project if queried with just the one team:
        # (actually we need a smarter mock method to make the team project name count in this test...TODO - write better mock methods that simulate the
        # underlying filtering by Argo and returning different results for different team project queries)
        uniq_workflow_list = engine.get_workflows_for_team_projects(["dummyteam"])
        assert len(uniq_workflow_list) == 2
        assert "custom_name_active2" == uniq_workflow_list[0]["wf_name"]
        assert "custom_name_archived" == uniq_workflow_list[1]["wf_name"]
        assert "2023-03-22T19:59:59Z" == uniq_workflow_list[1]["submittedAt"]
        assert "dummyuser" == uniq_workflow_list[1][GEN3_USER_METADATA_LABEL]


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
    with mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_id_and_limit, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_monthly_workflow_cap"
    ) as mock_check_workflow_cap:
        mock_config_dict.return_value = config
        mock_id_and_limit.return_value = None, None
        mock_check_workflow_cap.return_value = 1, 50

        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        args = engine.api_instance.create_workflow.call_args_list
        for parameter in args[0][1]["body"]["workflow"]["spec"]["arguments"][
            "parameters"
        ]:
            if (param_name := parameter["name"]) in parameters and param_name not in (
                "variables"
            ):
                assert parameter["value"] == parameters[param_name]

            if param_name == "variables":
                result = parameter["value"].replace("\n", "")
                for variable in parameters[param_name]:
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
    ) as mock_config_dict, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_info_for_billing_id_and_workflow_limit"
    ) as mock_id_and_limit, mock.patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_monthly_workflow_cap"
    ) as mock_check_workflow_cap:
        mock_config_dict.return_value = config
        mock_id_and_limit.return_value = None, None
        mock_check_workflow_cap.return_value = 1, 50

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
                    "name": "step_one_name(0)",
                    "type": "Pod",
                    "displayName": "generate-attrition-csv",
                    "templateName": "step_one_template",
                    "message": "ReadTimeout",
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
    engine._find_first_failed_node = mock.MagicMock(return_value="step_one_name")
    archived_workflow_errors = engine.get_workflow_logs("archived_wf", "archived_uid")
    assert len(archived_workflow_errors) == 1
    assert archived_workflow_errors[0]["node_type"] == "Pod"
    assert archived_workflow_errors[0]["step_template"] == "step_one_template"
    assert (
        archived_workflow_errors[0]["error_interpreted"]
        == "A timeout occurred while fetching the attrition table information. Please retry running your workflow."
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
                    "name": "step_one_name(0)",
                    "type": "Pod",
                    "displayName": "generate-attrition-csv",
                    "templateName": "step_one_template",
                    "message": "ReadTimeout",
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
    engine._find_first_failed_node = mock.MagicMock(return_value="step_one_name")
    engine._get_workflow_log_dict = mock.MagicMock(return_value=mock_return_wf)
    workflow_errors = engine.get_workflow_logs("active_wf", "wf_uid")
    assert len(workflow_errors) == 1
    assert workflow_errors[0]["name"] == "step_one_name(0)"
    assert (
        workflow_errors[0]["error_interpreted"]
        == "A timeout occurred while fetching the attrition table information. Please retry running your workflow."
    )


def test_get_archived_workflow_wf_name_and_team_project():
    """check if this helper method returns the expected values and returns results from cache if called a second time for the same workflow"""
    engine = ArgoEngine()
    mock_return_wf = {
        "wf_name": "dummy_wf_name",
        GEN3_TEAM_PROJECT_METADATA_LABEL: "dummy_team_project_label",
        GEN3_USER_METADATA_LABEL: "dummy_user",
    }

    engine.get_workflow_details = mock.MagicMock(return_value=mock_return_wf)
    (
        given_name,
        team_project,
        gen3username,
    ) = engine._get_archived_workflow_wf_name_and_team_project("dummy_uid")
    assert given_name == "dummy_wf_name"
    assert team_project == "dummy_team_project_label"
    assert gen3username == "dummy_user"

    # test the internal caching that happens at _get_archived_workflow_wf_name_and_team_project,
    # by setting the get_workflow_details to return None and show that it was not called,
    # as the result is still the previous one:
    engine.get_workflow_details = mock.MagicMock(return_value=None)
    (
        given_name,
        team_project,
        gen3username,
    ) = engine._get_archived_workflow_wf_name_and_team_project("dummy_uid")
    assert given_name == "dummy_wf_name"
    assert team_project == "dummy_team_project_label"
    assert gen3username == "dummy_user"


@freeze_time("Nov 16th, 2023")
def test_get_user_workflows_for_current_month(monkeypatch):

    engine = ArgoEngine()
    workflows_mock_response = [
        {
            "uid": "uid_1",
            "phase": "Running",
            "submittedAt": "2023-11-14T16:44:02Z",
        },
        {
            "uid": "uid_2",
            "phase": "Succeeded",
            "submittedAt": "2023-11-15T17:52:52Z",
        },
        {
            "uid": "uid_3",
            "phase": "Failed",
            "submittedAt": "2023-11-02T00:00:00Z",
        },
        {
            "uid": "uid_4",
            "phase": "Succeeded",
            "submittedAt": "2023-10-31T00:00:00Z",
        },
    ]

    expected_workflow_reponse = [
        {
            "uid": "uid_1",
            "phase": "Running",
            "submittedAt": "2023-11-14T16:44:02Z",
        },
        {
            "uid": "uid_2",
            "phase": "Succeeded",
            "submittedAt": "2023-11-15T17:52:52Z",
        },
        {
            "uid": "uid_3",
            "phase": "Failed",
            "submittedAt": "2023-11-02T00:00:00Z",
        },
    ]
    engine.get_workflows_for_label_selector = mock.MagicMock(
        return_value=workflows_mock_response
    )

    user_monthly_workflow = engine.get_user_workflows_for_current_month(
        EXAMPLE_AUTH_HEADER
    )

    assert user_monthly_workflow == expected_workflow_reponse


def test_check_user_monthly_workflow_cap():
    headers = {
        "Content-Type": "application/json",
        "Authorization": EXAMPLE_AUTH_HEADER,
    }
    engine = ArgoEngine()

    with patch(
        "argowrapper.engine.argo_engine.ArgoEngine.get_user_workflows_for_current_month"
    ) as mock_get_workflow:
        mock_get_workflow.return_value = [
            {"wf_name": "workflow1"},
            {"wf_name": "workflow2"},
        ]

        # Test Under Default Limit
        assert (
            engine.check_user_monthly_workflow_cap(headers["Authorization"], None, None)
            == 2,
            GEN3_NON_VA_WORKFLOW_MONTHLY_CAP,
        )

        # Test Custom Limit
        assert (
            engine.check_user_monthly_workflow_cap(headers["Authorization"], None, 2)
            == 2,
            2,
        )

        # Test Billing Id User Exceeding Limit
        workflows = []
        for index in range(GEN3_NON_VA_WORKFLOW_MONTHLY_CAP + 1):
            workflows.append({"wf_name": "workflow" + str(index)})
        mock_get_workflow.return_value = workflows

        assert (
            engine.check_user_monthly_workflow_cap(
                headers["Authorization"], "1234", None
            )
            == GEN3_NON_VA_WORKFLOW_MONTHLY_CAP + 1,
            GEN3_NON_VA_WORKFLOW_MONTHLY_CAP,
        )

        # Test VA User Exceeding Limit
        workflows = []
        for index in range(GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP + 1):
            workflows.append({"wf_name": "workflow" + str(index)})
        mock_get_workflow.return_value = workflows
        assert (
            engine.check_user_monthly_workflow_cap(headers["Authorization"], None, None)
            == GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP + 1,
            GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP,
        )


"""
TODO DELETE
Temporarily remove for temp logging statement
def test_submit_workflow_with_user_billing_id():
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=None)

    with patch("requests.get") as mock_requests, mock.patch(
        "argowrapper.engine.argo_engine.argo_engine_helper._get_argo_config_dict"
    ) as mock_config_dict, patch(
        "argowrapper.engine.argo_engine.ArgoEngine.check_user_monthly_workflow_cap"
    ) as mock_check_workflow_cap:
        mock_requests.side_effect = mocked_requests_get

        config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
        mock_config_dict.return_value = config
        mock_check_workflow_cap.return_value = 2, 50

        # Sets User tags via mocked_requests_get
        tag_data["user_tags"] = {"tags": {}}
        result = engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)

        # Billing ID is Null
        assert mock_check_workflow_cap.call_args.args[1] == None
        # Custom Limit is Null
        assert mock_check_workflow_cap.call_args.args[2] == None

        tag_data["user_tags"] = {"tags": {"othertag1": "tag1"}}
        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert mock_check_workflow_cap.call_args.args[1] == None
        assert mock_check_workflow_cap.call_args.args[2] == None

        tag_data["user_tags"] = {"tags": {"othertag1": "tag1", "billing_id": "1234"}}
        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert mock_check_workflow_cap.call_args.args[1] == "1234"
        assert mock_check_workflow_cap.call_args.args[2] == None

        tag_data["user_tags"] = {
            "tags": {"othertag1": "tag1", "billing_id": "1234", "workflow_limit": 34}
        }
        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert mock_check_workflow_cap.call_args.args[1] == "1234"
        assert mock_check_workflow_cap.call_args.args[2] == 34

        tag_data["user_tags"] = {"tags": {"othertag1": "tag1", "workflow_limit": 34}}
        engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
        assert mock_check_workflow_cap.call_args.args[1] == None
        assert mock_check_workflow_cap.call_args.args[2] == 34

        tag_data["user_tags"] = 500
        with pytest.raises(Exception):
            engine.workflow_submission(parameters, EXAMPLE_AUTH_HEADER)
"""
