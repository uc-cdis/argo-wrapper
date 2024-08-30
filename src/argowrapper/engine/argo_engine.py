import string
import traceback
from datetime import datetime
from typing import Dict, List, Literal

import argo_workflows
from argo_workflows.api import (
    archived_workflow_service_api,
    artifact_service_api,
    workflow_service_api,
)
from argo_workflows.exceptions import NotFoundException
from argo_workflows.model.io_argoproj_workflow_v1alpha1_retry_archived_workflow_request import (
    IoArgoprojWorkflowV1alpha1RetryArchivedWorkflowRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_create_request import (
    IoArgoprojWorkflowV1alpha1WorkflowCreateRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_retry_request import (
    IoArgoprojWorkflowV1alpha1WorkflowRetryRequest,
)
from argo_workflows.model.io_argoproj_workflow_v1alpha1_workflow_terminate_request import (
    IoArgoprojWorkflowV1alpha1WorkflowTerminateRequest,
)

from argowrapper import logger
from argowrapper.constants import (
    ARGO_HOST,
    ARGO_NAMESPACE,
    GEN3_SUBMIT_TIMESTAMP_LABEL,
    GEN3_TEAM_PROJECT_METADATA_LABEL,
    GEN3_USER_METADATA_LABEL,
    GEN3_WORKFLOW_PHASE_LABEL,
    WORKFLOW,
    GEN3_NON_VA_WORKFLOW_MONTHLY_CAP,
    GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP,
    EXCEED_WORKFLOW_LIMIT_ERROR,
)
from argowrapper.engine.helpers import argo_engine_helper
from argowrapper.engine.helpers.workflow_factory import WorkflowFactory
from argowrapper.workflows.argo_workflows.gwas import GWAS
import requests


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

    def _get_workflow_details_dict(self, workflow_name: str) -> Dict:
        return self.api_instance.get_workflow(
            namespace=ARGO_NAMESPACE,
            name=workflow_name,
            fields="metadata.name,metadata.annotations,metadata.creationTimestamp,metadata.labels,spec.arguments,spec.shutdown,status.phase,status.progress,status.startedAt,status.finishedAt,status.outputs",
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

    def _get_workflow_node_artifact(self, uid: str, node_id: str) -> str:
        return (
            self.artifact_api_instance.get_output_artifact_by_uid(
                uid=uid,
                node_id=node_id,
                artifact_name="main-logs",
                _check_return_type=False,
            )
            .read()
            .decode()
        )

    def _get_log_errors(self, uid: str, status_nodes_dict: Dict) -> List[Dict]:
        errors = []
        for node_id, step in status_nodes_dict.items():
            if step.get("phase") in ("Failed", "Error") and step.get("type") == "Retry":
                message = (
                    step["message"] if step.get("message") else "No message provided"
                )
                node_type = step.get("type")
                node_step = step.get("displayName")
                node_step_template = step.get("templateName")
                node_phase = step.get("phase")
                node_outputs_mainlog = self._get_workflow_node_artifact(
                    uid=uid, node_id=node_id
                )
                node_log_interpreted = GWAS.interpret_gwas_workflow_error(
                    step_name=node_step, step_log=node_outputs_mainlog
                )
                errors.append(
                    {
                        "name": step.get("name"),
                        "node_id": node_id,
                        "node_type": node_type,
                        "node_phase": node_phase,
                        "step_name": node_step,
                        "step_template": node_step_template,
                        "error_message": message,
                        "error_interpreted": node_log_interpreted,
                    }
                )
            else:
                pass
        return errors

    def get_workflow_details(
        self, workflow_name: str, uid: str = None
    ) -> Dict[str, any]:
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

    def _get_archived_workflow_wf_name_and_team_project(
        self, archived_workflow_uid
    ) -> (str, str, str):
        """
        Gets the name and team project details for the given archived workflow

        It tries to get it from cache first. If not in cache, it will query the
        argo endpoint for archived workflows and parse out the 'workflow_name'
        from the annotations section (aka 'workflow given name' or
        'workflow name given by the user').

        **Only for archived workflows**: active workflows return in the /workflows
        list with their annotations, so this method of getting the annotations
        via a second request is really only needed as a workaround for archived
        workflows.

        Returns:
            str, str: the custom, user given, workflow name found in the annotations
                 section of the workflow AND the "team project" label
        """
        if archived_workflow_uid in self.workflow_given_names_cache:
            return self.workflow_given_names_cache[archived_workflow_uid]
        # call workflow details endpoint:
        workflow_details = self.get_workflow_details(None, archived_workflow_uid)
        #  get the workflow given name from the parsed details:
        given_name = workflow_details["wf_name"]
        team_project = workflow_details[GEN3_TEAM_PROJECT_METADATA_LABEL]
        gen3username = workflow_details[GEN3_USER_METADATA_LABEL]
        self.workflow_given_names_cache[archived_workflow_uid] = (
            given_name,
            team_project,
            gen3username,
        )
        return given_name, team_project, gen3username

    def get_workflows_for_team_projects_and_user(
        self, team_projects: List[str], auth_header: str
    ) -> List[Dict]:
        team_project_workflows = self.get_workflows_for_team_projects(team_projects)
        user_workflows = self.get_workflows_for_user(auth_header)

        uniq_workflows = argo_engine_helper.remove_list_duplicate(
            team_project_workflows, user_workflows
        )
        return uniq_workflows

    def get_workflows_for_team_projects(self, team_projects: List[str]) -> List[Dict]:
        result = []
        for team_project in team_projects:
            result.extend(self.get_workflows_for_team_project(team_project))
        return result

    def get_workflows_for_team_project(self, team_project: str) -> List[Dict]:
        """
        Get the list of all workflows for the given team_project. Each item in the list
        contains the workflow name, its status, start and end time.

        Args:
            team_project: team project name

        Returns:
            List[Dict]: List of workflow dictionaries.

        Raises:
            raises Exception in case of any error.
        """
        team_project_label = argo_engine_helper.convert_gen3teamproject_to_pod_label(
            team_project
        )
        label_selector = f"{GEN3_TEAM_PROJECT_METADATA_LABEL}={team_project_label}"
        workflows = self.get_workflows_for_label_selector(label_selector=label_selector)
        return workflows

    def get_workflows_for_user(self, auth_header: str) -> List[Dict]:
        """
        Get the list of all workflows for the current user. Each item in the list
        contains the workflow name, its status, start and end time.
        Considers solely the workflows that are labelled with ONLY the user name (so no
        team project label)

        Args:
            auth_header: authorization header that contains the user's jwt token

        Returns:
            List[Dict]: List of workflow dictionaries with details of workflows
            that the user has ran.

        Raises:
            raises Exception in case of any error.
        """
        username = argo_engine_helper.get_username_from_token(auth_header)
        user_label = argo_engine_helper.convert_gen3username_to_pod_label(username)
        label_selector = f"{GEN3_USER_METADATA_LABEL}={user_label}"
        all_user_workflows = self.get_workflows_for_label_selector(
            label_selector=label_selector
        )  # TODO - this part would benefit from a system test
        user_only_workflows = []
        for workflow in all_user_workflows:
            # keep only workflows that have an empty team project:
            if not workflow[GEN3_TEAM_PROJECT_METADATA_LABEL]:
                user_only_workflows.append(workflow)
        return user_only_workflows

    def get_user_workflows_for_current_month(self, auth_header: str) -> List[Dict]:
        """
        Get the list of all succeeded and running workflows the current user owns in the current month.
        Each item in the list contains the workflow name, its status, start and end time.

        Args:
            auth_header: authorization header that contains the user's jwt token

        Returns:
            List[Dict]: List of workflow dictionaries with details of workflows
            that the user has ran.

        Raises:
            raises Exception in case of any error.
        """
        username = argo_engine_helper.get_username_from_token(auth_header)
        user_label = argo_engine_helper.convert_gen3username_to_pod_label(username)
        label_selector = f"{GEN3_USER_METADATA_LABEL}={user_label}"
        all_user_workflows = self.get_workflows_for_label_selector(
            label_selector=label_selector
        )
        user_monthly_workflows = []
        for workflow in all_user_workflows:
            if workflow[GEN3_WORKFLOW_PHASE_LABEL] in {
                "Running",
                "Succeeded",
                "Failed",
            }:
                submitted_time_str = workflow[GEN3_SUBMIT_TIMESTAMP_LABEL]
                submitted_time = datetime.strptime(
                    submitted_time_str, "%Y-%m-%dT%H:%M:%SZ"
                )
                first_day_of_month = datetime.today().replace(day=1)
                if submitted_time.date() >= first_day_of_month.date():
                    user_monthly_workflows.append(workflow)

        return user_monthly_workflows

    def get_workflows_for_label_selector(self, label_selector: str) -> List[Dict]:
        try:
            workflow_list_return = self.api_instance.list_workflows(
                namespace=ARGO_NAMESPACE,
                list_options_label_selector=label_selector,
                _check_return_type=False,
                fields="items.metadata.name,items.metadata.namespace,items.metadata.annotations,items.metadata.uid,items.metadata.creationTimestamp,items.metadata.labels,items.spec.arguments,items.spec.shutdown,items.status.phase,items.status.startedAt,items.status.finishedAt",
            )
            archived_workflow_list_return = (
                self.archive_api_instance.list_archived_workflows(
                    namespace=ARGO_NAMESPACE,
                    list_options_label_selector=label_selector,
                    _check_return_type=False,
                )
            )

            if not (workflow_list_return.items or archived_workflow_list_return.items):
                logger.info(
                    f"no active workflows or archived workflow exist for label_selector {label_selector}"
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
                        get_archived_workflow_wf_name_and_team_project=self._get_archived_workflow_wf_name_and_team_project,
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
                f"could not get workflows for label_selector={label_selector}, failed with error {exception}"
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
                    "nodes"
                )
                archived_workflow_errors = self._get_log_errors(
                    uid=uid, status_nodes_dict=archived_workflow_details_nodes
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
                active_workflow_details_nodes = active_workflow_log_return[
                    "status"
                ].get("nodes")
                active_workflow_errors = self._get_log_errors(
                    uid=uid, status_nodes_dict=active_workflow_details_nodes
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

        reached_monthly_cap = False

        # check if user has a billing id tag:
        (
            billing_id,
            workflow_limit,
        ) = self.check_user_info_for_billing_id_and_workflow_limit(auth_header)

        # If billing_id exists for user, add it to workflow label and pod metadata
        # remove gen3-username from pod metadata
        if billing_id:
            workflow_yaml["metadata"]["labels"]["billing_id"] = billing_id
            pod_labels = workflow_yaml["spec"]["podMetadata"]["labels"]
            pod_labels["billing_id"] = billing_id
            pod_labels["gen3username"] = ""

        # if user has billing_id (non-VA user), check if they already reached the monthly cap
        workflow_run, workflow_limit = self.check_user_monthly_workflow_cap(
            auth_header, billing_id, workflow_limit
        )

        reached_monthly_cap = workflow_run >= workflow_limit

        # submit workflow:
        if not reached_monthly_cap:
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
                logger.error(
                    f"could not submit workflow, failed with error {exception}"
                )
                raise exception
        else:
            logger.warning(EXCEED_WORKFLOW_LIMIT_ERROR)
            raise Exception(EXCEED_WORKFLOW_LIMIT_ERROR)

        return workflow.wf_name

    def check_user_info_for_billing_id_and_workflow_limit(self, request_token):
        """
        Check whether user is non-VA user
        if user is VA-user, do nothing and proceed
        if user is non-VA user () billing id tag exists in fence user info)
        add billing Id to argo metadata and pod metadata
        remove gen3 username from pod metadata
        """

        header = {"Authorization": request_token}
        # TODO: Make this configurable
        url = "http://fence-service/user"
        try:
            r = requests.get(url=url, headers=header)
            r.raise_for_status()
            user_info = r.json()
        except Exception as e:
            exception = Exception("Could not determine user billing info from fence", e)
            logger.error(exception)
            traceback.print_exc()
            raise exception
        logger.info("Got user info successfully. Checking for billing id..")

        if "tags" in user_info:
            if "billing_id" in user_info["tags"]:
                billing_id = user_info["tags"]["billing_id"]
                logger.info("billing id found in user tags: " + billing_id)
            else:
                billing_id = None

            if "workflow_limit" in user_info["tags"]:
                workflow_limit = user_info["tags"]["workflow_limit"]
                logger.info(f"Workflow limit found in user tags: {workflow_limit}")
            else:
                workflow_limit = None

            return billing_id, workflow_limit
        else:
            logger.info("User info does not have tags")
            return None, None

    def check_user_monthly_workflow_cap(self, request_token, billing_id, custom_limit):
        """
        Query Argo service to see how many workflow runs user already
        have in the current calendar month. Return number of workflow runs and limit
        """

        try:
            current_month_workflows = self.get_user_workflows_for_current_month(
                request_token
            )
            username = argo_engine_helper.get_username_from_token(request_token)
            if custom_limit:
                limit = custom_limit
            else:
                if billing_id:
                    limit = GEN3_NON_VA_WORKFLOW_MONTHLY_CAP
                else:
                    limit = GEN3_DEFAULT_WORKFLOW_MONTHLY_CAP
            return len(current_month_workflows), limit
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
            raise e
