import string
import traceback
from typing import Dict, List

import argo_workflows
from argo_workflows.api import archived_workflow_service_api, workflow_service_api
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_terminate_request import (
    IoArgoprojWorkflowV1alpha1WorkflowTerminateRequest,
)

from argowrapper import logger
from argowrapper.constants import ARGO_HOST, ARGO_NAMESPACE, WORKFLOW
from argowrapper.engine.helpers import argo_engine_helper
from argowrapper.engine.helpers.workflow_factory import WorkflowFactory


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

    def _get_all_workflows(self):
        return self.api_instance.list_workflows(namespace=ARGO_NAMESPACE).to_str()

    def _get_workflow_status_dict(self, workflow_name: str) -> Dict:

        return self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="metadata.name,metadata.annotations,spec.arguments,spec.shutdown,status.phase,status.progress,status.startedAt,status.finishedAt,status.outputs",
            # Note that _check_return_type=False avoids an existing issue with OpenAPI generator.
            _check_return_type=False,
        ).to_dict()

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
                                "phase": {workflow_status} can be running, failed, succeded, canceling, canceled
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
            string : "{workflow_name} canceled sucessfully" if suceed, error message if not
        """
        if self.dry_run:
            logger.info(f"dry run for canceling {workflow_name}")
            return f"{workflow_name} canceled sucessfully"
        try:
            self.api_instance.terminate_workflow(
                namespace=ARGO_NAMESPACE,
                name=workflow_name,
                body=IoArgoprojWorkflowV1alpha1WorkflowTerminateRequest(
                    name=workflow_name,
                    namespace=ARGO_NAMESPACE,
                    _check_type=False,
                ),
                _check_return_type=False,
            )
            return f"{workflow_name} canceled sucessfully"

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not cancel {workflow_name}, failed with error {exception}"
            )
            raise Exception(
                f"could not cancel {workflow_name} because workflow not found"
            )

    def get_workfows_for_user(self, auth_header: str) -> List[str]:
        """
        Get a list of all workflow for a new user

        Args:
            auth_header: authorization header that contains the user's jwt token

        Returns:
            List[str]: List of workflow names that the user
            has ran if sucess, error message if fails

        """
        username = argo_engine_helper.get_username_from_token(auth_header)
        user_label = argo_engine_helper.convert_gen3username_to_label(username)
        label_selector = f"gen3username={user_label}"

        try:
            workflows = self.api_instance.list_workflows(
                namespace=ARGO_NAMESPACE,
                list_options_label_selector=label_selector,
                _check_return_type=False,
                fields="items.metadata.name",
            )

            if not workflows.items:
                logger.info(f"no workflows exist for user {username}")
                return []

            names = [
                workflow.get("metadata", {}).get("name") for workflow in workflows.items
            ]

            return names

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not get workflows for {username}, failed with error {exception}"
            )
            raise exception

    def get_workflow_logs(self, workflow_name: str) -> List[Dict]:
        res = self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="status.nodes",
            # Note that _check_return_type=False avoids an existing issue with OpenAPI generator.
            _check_return_type=False,
        ).to_dict()

        errors = []

        for _, step in res.get("status", {}).get("nodes", {}).items():
            if step.get("phase") == "Failed" and "Error" in step.get("message", ""):
                errors.append(
                    {
                        "name": step.get("name"),
                        "step_template": step.get("templateName"),
                        "error_message": step.get("message"),
                    }
                )
        return errors

    def workflow_submission(self, request_body: Dict, auth_header: str):
        workflow = WorkflowFactory._get_workflow(
            ARGO_NAMESPACE, request_body, auth_header, WORKFLOW.GWAS
        )
        workflow_yaml = workflow._to_dict()
        logger.debug(workflow_yaml)
        try:
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
        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(f"could not submit workflow, failed with error {exception}")
            raise exception

        return workflow.wf_name
