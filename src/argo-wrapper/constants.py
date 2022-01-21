from enum import Enum


class WorkflowStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "Succeeded"
    FAILED = "failed"


WORKFLOW_LOCATION = "/home/vhdcprod/argo-setup/hello-world.yaml"
ARGO_HOST = "https://127.0.0.1:2746"
TEST_WF_PATH = "argo_workflows/test.yaml"
