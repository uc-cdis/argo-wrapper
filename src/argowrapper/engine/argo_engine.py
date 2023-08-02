import string
import traceback
from typing import Dict, List, Literal

import argo_workflows
from argo_workflows.api import archived_workflow_service_api, workflow_service_api, artifact_service_api
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_terminate_request import (
    IoArgoprojWorkflowV1alpha1WorkflowTerminateRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_retry_request import (
    IoArgoprojWorkflowV1alpha1WorkflowRetryRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_retry_archived_workflow_request import (
    IoArgoprojWorkflowV1alpha1RetryArchivedWorkflowRequest,
)
from argo_workflows.exceptions import NotFoundException

from argowrapper import logger
from argowrapper.constants import ARGO_HOST, ARGO_NAMESPACE, WORKFLOW
from argowrapper.engine.helpers import argo_engine_helper
from argowrapper.engine.helpers.workflow_factory import WorkflowFactory
from argowrapper.workflows.argo_workflows.gwas import GWAS


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
        # workflow "given names" by uid cache:
        self.workflow_given_names_cache = {}

        configuration = argo_workflows.Configuration(
            host=ARGO_HOST,
        )
        configuration.verify_ssl = False

        api_client = argo_workflows.ApiClient(configuration)
        self.api_instance = workflow_service_api.WorkflowServiceApi(api_client)
        self.archive_api_instance = (
            archived_workflow_service_api.ArchivedWorkflowServiceApi(api_client)
        )
        self.artifact_api_instance = artifact_service_api.ArtifactServiceApi(api_client)

    def _get_all_workflows(self):
        return self.api_instance.list_workflows(namespace=ARGO_NAMESPACE).to_str()

    def _get_workflow_details_dict(self, workflow_name: str) -> Dict:

        return self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="metadata.name,metadata.annotations,metadata.creationTimestamp,spec.arguments,spec.shutdown,status.phase,status.progress,status.startedAt,status.finishedAt,status.outputs",
            # Note that _check_return_type=False avoids an existing issue with OpenAPI generator.
            _check_return_type=False,
        ).to_dict()

    def _get_archived_workflow_details_dict(self, uid: str) -> Dict:
        """
        Queries the archived workflows api.
        Raises a argo_workflows.exceptions.NotFoundException if the workflow uid cannot be found
        as an archived workflow
        """
        # good to know: this one by default already includes some of the necessary fields like metadata.annotations,metadata.creationTimestamp ...and unfortunately we can't control the fields like in the call to get_workflow() above with "fields" parameter...
        return self.archive_api_instance.get_archived_workflow(
            uid=uid, _check_return_type=False
        ).to_dict()

    def _get_workflow_log_dict(self, workflow_name: str) -> Dict:
        return self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="status.nodes",
            _check_return_type=False,
        ).to_dict()

    def _get_workflow_phase(self, workflow_name: str) -> str:
        phase_return = self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="status.phase",
            _check_return_type=False,    
        ).to_dict()
        return phase_return["status"].get("phase")
    
    def _get_workflow_node_artifact(self, id_discriminator: Literal['workflow', 'archived-workflows'], wf_id: str, node_id: str) -> str:
        api_response = self.archive_api_instance.get_artifact_file(
            namespace=ARGO_NAMESPACE,
            id_discriminator=id_discriminator,
            id=wf_id,
            node_id=node_id,
            artifact_discriminator="outputs",
            artifact_name="main-logs"
        )
        return api_response

    def _get_log_errors(self, id_discrimator: str, wf_id: str, status_nodes_dict: Dict) -> List[Dict]:
        errors = []
        for pod_id, step in status_nodes_dict.items():
            if step.get("phase") in ("Failed", "Error") and step.get("type")=="Retry":
                message = (
                    step["message"] if step.get("message") else "No message provided"
                )
                pod_type = step.get("type")
                pod_step = step.get("displayName")
                pod_step_template =  step.get("templateName")
                pod_phase = step.get("phase")
                pod_outputs_mainlog = self._get_workflow_node_artifact(
                    id_discriminator=id_discrimator,
                    wf_id=wf_id,
                    node_id=pod_id
                )
                pod_log_interpreted = GWAS.interpret_gwas_workflow_error(
                    step_name=pod_step,
                    main_log=pod_outputs_mainlog
                )
                errors.append(
                    {
                        "name": step.get("name"),
                        "pod_id": pod_id,
                        "pod_type": pod_type,
                        "pod_phase": pod_phase,
                        "step_name": pod_step,
                        "step_template": pod_step_template,
                        "error_message": message,
                        "error_interpreted": pod_log_interpreted
                    }
                )
            else:
                pass
        return errors

    def get_workflow_details(self, workflow_name: str, uid: str) -> Dict[str, any]:
        """
        Gets the workflow status

        Args:
            workflow_name (str): name of an active workflow to get status of
            uid (str): uid of an archived workflow to get status of

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
            archived_workflow_details = self._get_archived_workflow_details_dict(uid)
            archived_wf_details_parsed = argo_engine_helper.parse_details(
                archived_workflow_details, "archived_workflow"
            )
            return archived_wf_details_parsed
        except NotFoundException as exception:
            logger.info(
                f"Can't find {workflow_name} workflow at archived workflow endpoint"
            )
            logger.info(f"Look up {workflow_name} workflow at workflow endpoint")
            activate_workflow_details_parsed = self._get_workflow_details_dict(
                workflow_name
            )
            return argo_engine_helper.parse_details(
                activate_workflow_details_parsed, "active_workflow"
            )
        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"getting workflow status for {workflow_name} due to {exception}"
            )
            raise Exception(
                f"could not get status of {workflow_name}, workflow does not exist"
            )

    def cancel_workflow(self, workflow_name: str) -> str:
        """
        Cancels a workflow that's running, this will delete the workflow

        Args:
            workflow_name (str): name of the workflow whose status will be canceled

        Returns:
            str : "{workflow_name} canceled sucessfully" if suceed, error message if not
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

    def retry_workflow(self, workflow_name: str, uid: str) -> str:
        """
        Retries a failed workflow

        Args:
            workflow_name (str): name of the failed workflow to retry
            uid (str): uid of an failed AND archived workflow to retry
        Returns:
            str : "{workflow_name} retried sucessfully" if suceed, error message if not
        """
        if self.dry_run:
            logger.info(f"dry run for retrying {workflow_name}")
            return f"{workflow_name} retried sucessfully"
        try:
            # Try the regular retry first (will raise NotFoundException if workflow is not on cluster anymore):
            self.api_instance.retry_workflow(
                namespace=ARGO_NAMESPACE,
                name=workflow_name,
                body=IoArgoprojWorkflowV1alpha1WorkflowRetryRequest(
                    name=workflow_name,  # TODO - understand why we repeat these args
                    namespace=ARGO_NAMESPACE,
                    _check_type=False,
                ),
                _check_return_type=False,
            )
            return f"{workflow_name} retried sucessfully"
        except NotFoundException:
            # Workflow not found on cluster, try archived workflow endpoint:
            logger.info(f"Can't find the {workflow_name} workflow on the cluster")
            logger.info(
                f"Will try to retry the {workflow_name} workflow using the archived workflow endpoint"
            )
            self.archive_api_instance.retry_archived_workflow(
                uid=uid,
                body=IoArgoprojWorkflowV1alpha1RetryArchivedWorkflowRequest(
                    uid=uid,
                    namespace=ARGO_NAMESPACE,
                    _check_type=False,
                ),
                _check_return_type=False,
            )
            return f"archived {workflow_name} retried sucessfully"

    def _get_archived_workflow_given_name(self, archived_workflow_uid) -> str:
        """
        Gets the name details for the given archived workflow

        It tries to get it from cache first. If not in cache, it will query the
        argo endpoint for archived workflows and parse out the 'workflow_name'
        from the annotations section (aka 'workflow given name' or
        'workflow name given by the user').

        **Only for archived workflows**: active workflows return in the /workflows
        list with their annotations, so this method of getting the annotations
        via a second request is really only needed as a workaround for archived
        workflows.

        Returns:
            str: the custom, user given, workflow name found in the annotations
                 section of the workflow
        """
        if archived_workflow_uid in self.workflow_given_names_cache:
            return self.workflow_given_names_cache[archived_workflow_uid]
        # call workflow details endpoint:
        workflow_details = self.get_workflow_details(None, archived_workflow_uid)
        #  get the workflow given name from the parsed details:
        given_name = workflow_details["wf_name"]
        self.workflow_given_names_cache[archived_workflow_uid] = given_name
        return given_name

    def get_workflows_for_user(self, auth_header: str) -> List[Dict]:
        """
        Get a list of all workflows for a new user. Each item in the list
        contains the workflow name, its status, start and end time.

        Args:
            auth_header: authorization header that contains the user's jwt token

        Returns:
            List[Dict]: List of workflow dictionaries with details of workflows
            that the user has ran.

        Raises:
            raises Exception in case of any error.
        """
        username = argo_engine_helper.get_username_from_token(auth_header)
        user_label = argo_engine_helper.convert_gen3username_to_label(username)
        label_selector = f"gen3username={user_label}"

        try:
            workflow_list_return = self.api_instance.list_workflows(
                namespace=ARGO_NAMESPACE,
                list_options_label_selector=label_selector,
                _check_return_type=False,
                fields="items.metadata.name,items.metadata.namespace,items.metadata.annotations,items.metadata.uid,items.metadata.creationTimestamp,items.spec.arguments,items.spec.shutdown,items.status.phase,items.status.startedAt,items.status.finishedAt",
            )
            archived_workflow_list_return = (
                self.archive_api_instance.list_archived_workflows(
                    list_options_label_selector=label_selector,
                    _check_return_type=False,
                )
            )

            if not (workflow_list_return.items or archived_workflow_list_return.items):
                logger.info(
                    f"no active workflows or archived workflow exist for user {user_label}"
                )
                return []

            if workflow_list_return.items:
                workflow_list = [
                    argo_engine_helper.parse_list_item(
                        workflow, workflow_type="active_workflow"
                    )
                    for workflow in workflow_list_return.items
                ]
            else:
                workflow_list = []

            if archived_workflow_list_return.items:
                archived_workflow_list = [
                    argo_engine_helper.parse_list_item(
                        workflow,
                        workflow_type="archived_workflow",
                        get_archived_workflow_given_name=self._get_archived_workflow_given_name,
                    )
                    for workflow in archived_workflow_list_return.items
                ]
            else:
                archived_workflow_list = []

            uniq_workflow = argo_engine_helper.remove_list_duplicate(
                workflow_list, archived_workflow_list
            )
            return uniq_workflow

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"could not get workflows for {username}, failed with error {exception}"
            )
            raise exception

    def get_workflow_logs(self, workflow_name: str, uid: str) -> List[Dict]:
        """
        Gets the workflow errors from failed workflow

        Args:
            workflow_name (str): name of an active workflow to get status of
            uid (str): uid of an archived workflow to get status of

        Returns:
            Dict[str, any]: returns a list of dictionaries of errors of Retry nodes
        """
        try:
            archived_workflow_dict = self._get_archived_workflow_details_dict(uid)
            archived_workflow_phase = archived_workflow_dict["status"].get("phase")
            if archived_workflow_phase in ("Failed", "Error"):
                archived_workflow_details_nodes = archived_workflow_dict["status"].get(
                "nodes")
                archived_workflow_errors = self._get_log_errors(
                    id_discrimator="archived-workflows",
                    wf_id=uid,
                    status_nodes_dict=archived_workflow_details_nodes
                    )
                return archived_workflow_errors
            else:
                logger.info(
                    f"Workflow {workflow_name} with uid {uid} doesn't have a Failed or Error phase"
                )
                return []

        except (KeyError, NotFoundException):
            logger.info(
                f"Can't find the log of {workflow_name} workflow at archived workflow endpoint"
            )
            logger.info(
                f"Look up the log of {workflow_name} workflow at workflow endpoint"
            )
            active_workflow_phase = self._get_workflow_phase(workflow_name)
            if active_workflow_phase in ("Failed", "Error"):
                active_workflow_log_return = self._get_workflow_log_dict(workflow_name)
                active_workflow_details_nodes = active_workflow_log_return["status"].get(
                    "nodes"
                    )
                active_workflow_errors = self._get_log_errors(
                    id_discrimator="workflow",
                    wf_id=workflow_name,
                    status_nodes_dict=active_workflow_details_nodes
                    )
                return active_workflow_errors
            else:
                logger.info(
                    f"Workflow {workflow_name} with uid {uid} doesn't have a Failed or Error phase"
                )
                return []

        except Exception as exception:
            logger.error(traceback.format_exc())
            logger.error(
                f"getting workflow status for {workflow_name} due to {exception}"
            )
            raise Exception(
                f"could not get status of {workflow_name}, workflow does not exist"
            )

    def workflow_submission(self, request_body: Dict, auth_header: str):
        workflow = WorkflowFactory._get_workflow(
            ARGO_NAMESPACE, request_body, auth_header, WORKFLOW.GWAS
        )
        workflow_yaml = workflow._to_dict()
        logger.debug(workflow_yaml)
        try:
            response = self.api_instance.create_workflow(
                namespace=ARGO_NAMESPACE,
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
