from enum import Enum
import pprint
from typing import Dict, types
from ..constants import *
import pathlib
import yaml
import logging
import string
import random

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
        ending_id = "".join(random.choices(string.digits, k=10))
        return "test-workflow-" + ending_id

    def __repr__(self) -> str:
        return f"token={self.argo_token} dry_run={self.dry_run}"

    def __init__(self, dry_run=False):
        argo_token = "token" if dry_run else self.__generate_argo_token()
        self.dry_run = dry_run
        self.argo_token = argo_token

        configuration = argo_workflows.Configuration(
            host=ARGO_HOST,
            api_key={"BearerToken": ACCESS_TOKEN},
            api_key_prefix={"BearerToken": "Bearer"},
        )
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)

    def _get_all_workflows(self):
        return self.api_instance.list_workflows(namespace="argo").to_str()

    def _parse_status(self, status_dict: Dict[str, any]):
        return status_dict["status"]["phase"]

    def get_workflow_status(self, workflow_name: str) -> str:
        if self.dry_run:
            return "workflow status"
        print(f"workflow name {workflow_name}")

        result = self.api_instance.get_workflow(
            namespace="argo", name=workflow_name
        ).to_dict()
        result = self._parse_status(result)

        return result

    def cancel_workflow(self, workflow_name: str) -> bool:
        if self.dry_run:
            return "canceled workflow"
        try:
            response = self.api_instance.delete_workflow(
                namespace="argo", name=workflow_name
            )
        except:
            logging.info(f"the workflow with name {workflow_name} does not exist")
            print("workflow {workflow_name} does not exist")
            return False
        print(response)

        return True

    def submit_workflow(self, parameters: Dict[str, str]) -> str:
        if self.dry_run:
            return "submit workflow"

        workflow_name = self.__generate_workflow_name()
        test_wf_path = pathlib.Path(__file__).parents[1]
        test_wf_path = test_wf_path.joinpath(TEST_WF_PATH)

        with open(test_wf_path, "r") as stream:
            try:
                manifest = yaml.safe_load(stream)
                del manifest["metadata"]["generateName"]
                manifest["metadata"]["name"] = workflow_name
                api_response = self.api_instance.create_workflow(
                    namespace="argo",
                    body=IoArgoprojWorkflowV1alpha1WorkflowCreateRequest(
                        workflow=manifest,
                        _check_return_type=False,
                        _check_type=False,
                    ),
                )
                logging.info(api_response)
            except:
                logging.info("could not submit workflow")

        return workflow_name
