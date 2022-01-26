from enum import Enum


class WorkflowStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "Succeeded"
    FAILED = "failed"


WORKFLOW_LOCATION = "/home/vhdcprod/argo-setup/hello-world.yaml"
ARGO_HOST = "https://argo-server.argo.svc.cluster.local:2746"
ACCESS_TOKEN = "test"
TEST_WF_PATH = "argo_workflows/test.yaml"
