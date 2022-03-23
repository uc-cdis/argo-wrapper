from enum import Enum


class WorkflowStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "Succeeded"
    FAILED = "failed"


ARGO_HOST = "http://argo-argo-workflows-server.argo.svc.cluster.local:2746"
TEST_WF = "test.yaml"
TOKEN_REGEX = r"[Bb]earer"
ARGO_ACCESS_SERVICE = "argo_workflow"
ARGO_ACCESS_METHOD = "access"
ARGO_ACCESS_RESOURCES = "/services/workflow/argo/admin"
ARGO_CONFIG_PATH = "/argo.json"
