import unittest.mock as mock

from argowrapper.engine.argo_engine import ArgoEngine


class WorkFlow:
    def __init__(self, items):
        self.items = items


def test_argo_engine_submit_succeeded():
    """returns workflow name if workflow submission suceeds"""
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=workflow_name)
    with mock.patch.object(
        engine, "_ArgoEngine__generate_workflow_name", return_value=workflow_name
    ):
        result = engine.submit_workflow({})
        assert result == workflow_name


def test_argo_engine_submit_failed():
    """returns empty string is workflow submission fails"""
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(
        side_effect=Exception("bad input")
    )
    with mock.patch.object(
        engine, "_ArgoEngine__generate_workflow_name", return_value=workflow_name
    ):
        result = engine.submit_workflow({})
        assert result == ""


def test_argo_engine_cancel_succeeded():
    """returns True if workflow cancelation suceeds"""
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(return_value=None)
    result = engine.cancel_workflow("wf_name")
    assert result == True


def test_argo_engine_cancel_failed():
    """returns False if workflow cancelation fails"""
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    result = engine.cancel_workflow("wf_name")
    assert result == False


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
    result = engine.get_workflow_status("test_wf")
    assert result == ""


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

    result = engine.get_workfows_for_user("test")
    assert result == "failed to get workflow for user"
