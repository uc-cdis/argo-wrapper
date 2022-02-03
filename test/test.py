from argowrapper.engine.argo_engine import ArgoEngine
import unittest.mock as mock


class Status:
    def to_dict(self):
        return {"test": "123"}


def test_argo_engine_submit_succeeded():
    workflow_name = "wf_name"
    engine = ArgoEngine()
    engine.api_instance.create_workflow = mock.MagicMock(return_value=workflow_name)
    with mock.patch.object(
        engine, "_ArgoEngine__generate_workflow_name", return_value=workflow_name
    ):
        result = engine.submit_workflow({})
        assert result == workflow_name


def test_argo_engine_submit_failed():
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
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(return_value=None)
    result = engine.cancel_workflow("wf_name")
    assert result == True


def test_argo_engine_cancel_failed():
    engine = ArgoEngine()
    engine.api_instance.delete_workflow = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    result = engine.cancel_workflow("wf_name")
    assert result == False


def test_argo_engine_get_status_succeeded():
    engine = ArgoEngine()
    engine._get_workflow_status_dict = mock.MagicMock(
        return_value={"status": {"phase": "running"}}
    )
    result = engine.get_workflow_status("test_wf")
    assert result == "running"


def test_argo_engine_get_status_failed():
    engine = ArgoEngine()
    engine._get_workflow_status_dict = mock.MagicMock(
        side_effect=Exception("workflow does not exist")
    )
    result = engine.get_workflow_status("test_wf")
    assert result == ""
