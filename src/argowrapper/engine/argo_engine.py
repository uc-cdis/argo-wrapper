import pathlib
import random
import string
from typing import Dict, List

import argo_workflows
import yaml
from argo_workflows.api import archived_workflow_service_api, workflow_service_api
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)

try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as pkg_resources

from argowrapper import logger
from argowrapper.constants import *
from argowrapper import argo_workflows_templates


class ArgoEngine(object):
    """
    A class to interact with argo engine

    Attributes:
        dry_run (bool): is dry run
        api_instance (WorkFlowServiceAPi): api client to interact with non-archived workflows
        archive_api_instance (ArchivedWorkflowServiceApi): api client to interact with archived workflows
    """

    def __generate_workflow_name(self) -> str:
        ending_id = "".join(random.choices(string.digits, k=10))
        return "argo-wrapper-workflow-" + ending_id

    def __repr__(self) -> str:
        return f"dry_run={self.dry_run}"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        configuration = argo_workflows.Configuration(
            host=QA_HOST,
            # host=PROD_HOST,
        )
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)
        self.archeive_api_instance = (
            archived_workflow_service_api.ArchivedWorkflowServiceApi(api_client)
        )

    def _get_all_workflows(self):
        return self.api_instance.list_workflows(namespace="argo").to_str()

    def _parse_status(self, status_dict: Dict[str, any]):
        return status_dict["status"]["phase"]

    def _get_workflow_status_dict(self, workflow_name: str) -> Dict:
        return self.api_instance.get_workflow(
            namespace="argo", name=workflow_name
        ).to_dict()

    def get_workflow_status(self, workflow_name: str) -> str:
        """
        Gets the workflow status

        Args:
            workflow_name (str): name of workflow to get status of

        Returns:
            str: "running" or "failed" or "suceeded" if success. empty string if failed
        """
        if self.dry_run:
            return "workflow status"
        try:
            result = self._get_workflow_status_dict(workflow_name)
            result = self._parse_status(result)
        except Exception as e:
            logger.info(f"getting workflow status for {workflow_name} due to {e}")
            return ""

        return result

    def cancel_workflow(self, workflow_name: str) -> bool:
        """
        Cancels a workflow that's running, this will delete the workflow

        Args:
            workflow_name (str): name of the workflow whose status will be canceled

        Returns:
            bool : True if workflow was sucessfully canceled, else False
        """
        if self.dry_run:
            return "canceled workflow"
        try:
            self.api_instance.delete_workflow(namespace="argo", name=workflow_name)
        except Exception as e:
            logger.info(f"the workflow with name {workflow_name} does not exist")
            return False

        return True

    def submit_workflow(self, parameters: Dict[str, str]) -> str:
        """
        Submits a workflow with definied parameters

        Args:
            parameters (Dict[str, str]): a dictionary of input parameters of the submitted workflow

        Returns:
            str: workflow name of the submitted workflow if sucess, empty string if fail
        """
        if self.dry_run:
            return "submit workflow"

        workflow_name = self.__generate_workflow_name()
        stream = pkg_resources.open_text(argo_workflows_templates, TEST_WF)

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
            logger.info(api_response)
        except Exception as e:
            logger.error(e)
            logger.info("error while submitting workflow")
            return ""

        return workflow_name

    def get_workfows_for_user(self, username: str) -> List[str]:
        """
        Get a list of all workflow for a new user

        Args:
            username (str): name of the user whose workflows we are returning

        Returns:
            List[str]: List of workflow names that the user has ran if sucess, error message if fails

        """
        label_selector = f"custom-username={username}"

        try:
            running_workflows = self.api_instance.list_workflows(
                namespace="argo",
                list_options_label_selector=label_selector,
                _check_return_type=False,
                fields="items.metadata.name",
            )

            archived_workflows = self.archeive_api_instance.list_archived_workflows(
                list_options_label_selector=label_selector
            )

            names = [
                workflow["metadata"]["name"] for workflow in running_workflows.items
            ]
            archived_names = [
                archived_workflow["metadata"]["name"]
                for archived_workflow in archived_workflows.items
            ]

            return list(set(names + archived_names))

        except Exception as e:
            logger.info(e)
            return "failed to get workflow for user"
