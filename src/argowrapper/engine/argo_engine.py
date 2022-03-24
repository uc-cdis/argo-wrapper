import string
import traceback
from typing import Dict, List

import argo_workflows
from argo_workflows.api import (
    archived_workflow_service_api,
    workflow_service_api,
    workflow_template_service_api,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)

from argowrapper import logger
from argowrapper.constants import ARGO_HOST
from argowrapper.engine.helpers import argo_engine_helper


class ArgoEngine:
    """
    A class to interact with argo engine

    Attributes:
        dry_run (bool): is dry run
        api_instance (WorkFlowServiceAPi): api client to interact with
        non-archived workflows archive_api_instance (ArchivedWorkflowServiceApi):
        api client to interact with archived workflows
    """

    def __repr__(self) -> str:
        return f"dry_run={self.dry_run}"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        configuration = argo_workflows.Configuration(
            host=ARGO_HOST,
        )
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)
        self.archeive_api_instance = (
            archived_workflow_service_api.ArchivedWorkflowServiceApi(api_client)
        )
        self.template_api_instance = (
            workflow_template_service_api.WorkflowTemplateServiceApi(api_client)
        )

    def _get_all_workflows(self):
        return self.api_instance.list_workflows(namespace="argo").to_str()

    def _get_workflow_status_dict(self, workflow_name: str) -> Dict:

        return self.api_instance.get_workflow(
            namespace="argo",
            name=workflow_name,
            fields="metadata.name,spec.arguments,status.phase,status.progress,status.startedAt,status.finishedAt,status.outputs",
            # Note that _check_return_type=False avoids an existing issue with OpenAPI generator.
            _check_return_type=False,
        ).to_dict()

    def _get_workflow_template(self, template_name: str) -> dict:
        try:
            return self.template_api_instance.get_workflow_template(
                namespace="argo", name=template_name
            ).to_dict()

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not get workflow template {template_name} due to {exception}"
            )
            raise Exception(f"workflow template {template_name} does not exist")

    def get_workflow_status(self, workflow_name: str) -> Dict[str, any]:
        """
        Gets the workflow status

        Args:
            workflow_name (str): name of workflow to get status of

        Returns:
            Dict[str, any]: returns a dict that looks like the below
                            {
                                "name": {workflow_name},
                                "arguments": {workflow_arguments},
                                "phase": {workflow_status} can be running, failed, succeded,
                                "progress": {x/total_steps}, tracks which step the workflow is on
                                "startedAt": {workflow_start_time},
                                "finishedAt": {workflow_end_time},
                                "outputs": {workflow_outputs}
                            }
        """
        if self.dry_run:
            return "workflow status"
        try:
            result = self._get_workflow_status_dict(workflow_name)
            return argo_engine_helper.parse_status(result)

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"getting workflow status for {workflow_name} due to {exception}"
            )
            raise Exception(
                f"could not get status of {workflow_name}, workflow does not exist"
            )

    def cancel_workflow(self, workflow_name: str) -> string:
        """
        Cancels a workflow that's running, this will delete the workflow

        Args:
            workflow_name (str): name of the workflow whose status will be canceled

        Returns:
            bool : True if workflow was sucessfully canceled, else False
        """
        if self.dry_run:
            logger.info(f"dry run for canceling {workflow_name}")
            return f"{workflow_name} canceled sucessfully"
        try:
            self.api_instance.delete_workflow(namespace="argo", name=workflow_name)
            return f"{workflow_name} canceled sucessfully"

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not cancel {workflow_name}, failed with error {exception}"
            )
            raise Exception(
                f"could not cancel {workflow_name} because workflow not found"
            )

    def submit_workflow(self, parameters: Dict[str, str]) -> str:
        """
        Submits a workflow with definied parameters

        Args:
            parameters (Dict[str, str]): a dictionary of input parameters of the submitted workflow

        Returns:
            str: workflow name of the submitted workflow if sucess, empty string if fail
        """

        try:
            workflow_yaml = self._get_workflow_template(parameters["template_version"])
            logger.info(workflow_yaml)
            workflow_yaml["kind"] = "Workflow"
            argo_engine_helper.add_parameters_to_gwas_workflow(
                parameters, workflow_yaml
            )
            argo_engine_helper.add_scaling_groups(
                parameters["gen3_user_name"], workflow_yaml
            )
            workflow_name = argo_engine_helper.add_name_to_workflow(workflow_yaml)

            logger.debug(
                f"the workflow {workflow_name} being submitted is {workflow_yaml}"
            )

            if self.dry_run:
                logger.info("dry run of workflow submission")
                logger.info(f"workflow being submitted {workflow_yaml}")
                logger.info(f"workflow name {workflow_name}")
                return workflow_name

            response = self.api_instance.create_workflow(
                namespace="argo",
                body=IoArgoprojWorkflowV1alpha1WorkflowCreateRequest(
                    workflow=workflow_yaml,
                    _check_return_type=False,
                    _check_type=False,
                ),
                _check_return_type=False,
            )
            logger.debug(response)
            return workflow_name

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(f"failed to submit workflow, failed with error {exception}")
            raise exception

    def get_workfows_for_user(self, username: str) -> List[str]:
        """
        Get a list of all workflow for a new user

        Args:
            username (str): name of the user whose workflows we are returning

        Returns:
            List[str]: List of workflow names that the user
            has ran if sucess, error message if fails

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

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not get workflows for {username}, failed with error {exception}"
            )
            raise exception
