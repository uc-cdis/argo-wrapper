from os import name
import constants
from enum import Enum
from typing import Dict, types
import subprocess
import pathlib
import yaml
import logging


import argo_workflows

from argo_workflows.api import workflow_service_api
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)


class ArgoEngine(object):
    def __generate_argo_token(self) -> str:
        argo_command = "argo auth token"
        token = subprocess.check_output(argo_command.split(" "))
        return token

    def __generate_workflow_name(self) -> str:
        return "test"

    def __init__(self):
        argo_token = self.__generate_argo_token()

        configuration = argo_workflows.Configuration(
            host=constants.ARGO_HOST, access_token=argo_token
        )
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)

    def get_workflow_status(
        self, workflow_name: str
    ) ->str:
        result = self.api_instance.get_workflow(namespace="argo", name=workflow_name)
        return result

    def cancel_workflow(self, workflow_name: str) -> bool:
        # argo cli
        self.api_instance.delete_workflow(namespace="argo", name=workflow_name)
        status = self.get_workflow_status(workflow_name)
        logging.info(status)
        return status == ""

    def submit_workflow(self, parameters: Dict[str, str]) -> str:
        # try with argo cli
        workflow_name = self.__generate_workflow_name()
        test_wf_path = (
            pathlib.Path(__file__).parent.absolute().joinpath(constants.TEST_WF_PATH)
        )

        with open(test_wf_path, "r") as stream:
            try:
                manifest = yaml.safe_load(stream)
                logging.info(manifest)
                api_response = self.api_instance.create_workflow(
                    namespace="argo",
                    body=IoArgoprojWorkflowV1alpha1WorkflowCreateRequest(workflow=manifest, name=workflow_name, _check_return_type=False, _check_type=False))
                logging.info(api_response)
            except:
                logging.info("could not submit workflow")

        return workflow_name