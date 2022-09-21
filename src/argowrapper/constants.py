from enum import Enum
from typing import Final
import re

ARGO_HOST: Final = "http://argo-argo-workflows-server.argo.svc.cluster.local:2746"
TEST_WF: Final = "test.yaml"
WF_HEADER: Final = "header.yaml"
ARGO_NAMESPACE: Final = "argo"
TOKEN_REGEX: Final = re.compile("bearer", re.IGNORECASE)
ARGO_ACCESS_SERVICE: Final = "argo_workflow"
ARGO_ACCESS_METHOD: Final = "access"
ARGO_ACCESS_RESOURCES: Final = "/services/workflow/argo/admin"
ARGO_CONFIG_PATH: Final = "/argo.json"
API_VERSION: Final = "argoproj.io/v1alpha1"
BACKUP_PVC_NAME: Final = "va-input-nfs-pvc"
WORKFLOW_KIND: Final = "workflow"


class POD_COMPLETION_STRATEGY(Enum):
    ONWORKFLOWSUCCESS: Final = "OnWorkflowSuccess"
    ONPODSUCESS: Final = "OnPodSuccess"


class WORKFLOW_ENTRYPOINT(Enum):
    GWAS_ENTRYPOINT: Final = "gwas-workflow"


class WORKFLOW(Enum):
    GWAS: Final = "GWAS"
