from os import name
from enum import Enum
from typing import Dict, types
from ..constants import *
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
        # token = subprocess.check_output(argo_command.split(" "))
        return "token"

    def __generate_workflow_name(self) -> str:
        return "test"

    def __repr__(self) -> str:
        return f"token={self.argo_token} dry_run={self.dry_run}"

    def __init__(self, dry_run=False):
        argo_token = "token" if dry_run else self.__generate_argo_token()
        self.dry_run = dry_run
        self.argo_token = argo_token

        """
        configuration = argo_workflows.Configuration(
            host=ARGO_HOST, access_token=argo_token
        )

        """

        configuration = argo_workflows.Configuration(host=ARGO_HOST)
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)

    def get_workflow_status(self, workflow_name: str) -> str:
        if self.dry_run:
            return "workflow status"
        result = self.api_instance.get_workflow(namespace="argo", name=workflow_name)
        return result

    def cancel_workflow(self, workflow_name: str) -> bool:
        if self.dry_run:
            return "canceled workflow"
        self.api_instance.delete_workflow(namespace="argo", name=workflow_name)
        status = self.get_workflow_status(workflow_name)
        logging.info(status)
        return status

    def submit_workflow(self, parameters: Dict[str, str]) -> str:
        if self.dry_run:
            return "submit workflow"
        # try with argo cli
        print("hello this is just a test")
        workflow_name = self.__generate_workflow_name()
        test_wf_path = pathlib.Path(__file__).parents[1]
        print(f"here is the test workflow dir {test_wf_path}")
        test_wf_path = test_wf_path.joinpath(TEST_WF_PATH)
        print(test_wf_path)

        with open(test_wf_path, "r") as stream:
            try:
                manifest = yaml.safe_load(stream)
                print(manifest)
                api_response = self.api_instance.create_workflow(
                    namespace="argo",
                    body=IoArgoprojWorkflowV1alpha1WorkflowCreateRequest(
                        workflow=manifest,
                        name=workflow_name,
                        _check_return_type=False,
                        _check_type=False,
                    ),
                )
                logging.info(api_response)
            except:
                logging.info("could not submit workflow")

        return workflow_name
