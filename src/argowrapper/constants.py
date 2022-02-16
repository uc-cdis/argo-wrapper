from enum import Enum


class WorkflowStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "Succeeded"
    FAILED = "failed"


WORKFLOW_LOCATION = "/home/vhdcprod/argo-setup/hello-world.yaml"
ARGO_HOST = "https://argo-server.argo.svc.cluster.local:2746"
ACCESS_TOKEN = "test"
TEST_WF_PATH = "argo_workflows/test.yaml"
TOKEN_REGEX = r"[Bb]earer"
ARGO_ACCESS_SERVICE = "argo_workflow"
ARGO_ACCESS_METHOD = "access"
ARGO_ACCESS_RESOURCES = "/services/workflow/argo/admin"
