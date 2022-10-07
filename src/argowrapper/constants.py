from enum import Enum
from typing import Final
import re
import configparser
import os
from argowrapper import logger

config = configparser.ConfigParser()
config_file = os.getenv("ARGO_WRAPPER_CONFIG_FILE")
if config_file is None:
    logger.info("starting up with default settings / PROD mode...")
    config.read("config.ini")
else:
    logger.warn(
        f"!! starting up with custom settings / DEV mode, using config file {config_file}..."
    )
    config.read(config_file)

logger.info(f"Argo host: {config['DEFAULT']['ARGO_HOST']}")
logger.info(f"Access method: {config['DEFAULT']['ARGO_ACCESS_METHOD']}")

ARGO_HOST: Final = config["DEFAULT"]["ARGO_HOST"]
TEST_WF: Final = "test.yaml"
WF_HEADER: Final = "header.yaml"
ARGO_NAMESPACE: Final = "argo"
TOKEN_REGEX: Final = re.compile("bearer", re.IGNORECASE)
ARGO_ACCESS_SERVICE: Final = "argo_workflow"
ARGO_ACCESS_METHOD: Final = config["DEFAULT"]["ARGO_ACCESS_METHOD"]
ARGO_ACCESS_RESOURCES: Final = "/services/workflow/argo/admin"
ARGO_CONFIG_PATH: Final = "/argo.json"
API_VERSION: Final = "argoproj.io/v1alpha1"
BACKUP_PVC_NAME: Final = "va-input-nfs-pvc"
WORKFLOW_KIND: Final = "workflow"


class POD_COMPLETION_STRATEGY(Enum):
    ONWORKFLOWSUCCESS: Final = "OnWorkflowSuccess"
    ONPODSUCESS: Final = "OnPodSuccess"
    ONPODCOMPLETION: Final = "OnPodCompletion"


class WORKFLOW_ENTRYPOINT(Enum):
    GWAS_ENTRYPOINT: Final = "gwas-workflow"


class WORKFLOW(Enum):
    GWAS: Final = "GWAS"
