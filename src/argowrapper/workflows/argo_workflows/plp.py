from typing import Dict, List, Optional

import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
from argowrapper import logger
from argowrapper.constants import (
    BACKUP_PVC_NAME,
    POD_COMPLETION_STRATEGY,
    WORKFLOW_ENTRYPOINT,
)
from argowrapper.workflows.workflow_base import WorkflowBase
from argowrapper.constants import (
    TEAM_PROJECT_FIELD_NAME,
    GEN3_USER_METADATA_LABEL,
    GEN3_TEAM_PROJECT_METADATA_LABEL,
)


class PLP(WorkflowBase):
    """A class to represent the Patient Level Prediction (PLP) workflow

    Attributes:
        dry_run (bool): is dry run
        username (string): username of person who submitted workflow
        gen3username_label (string): k8 label converted from username
        workflow_parameters (Dict): a dictionary of request parameters from the user, with complex parameters flattened as a string
    """

    HARD_CODED_PARAMETERS = {
        # e.g. "genome_build": "hg19",
    }

    PARAMETER_TO_DEFAULT_VALS = {
        "internal_api_env": "default",
        "out_prefix": "plp_out",
    }

    ENUM_PARAMETERS_TO_ENUM_VALS = {}

    METADATA_ANNOTATIONS = {
        "workflows.argoproj.io/version": ">= 3.1.0",
    }

    METADATA_LABELS = {"workflows.argoproj.io/archive-strategy": "true"}

    # TODO - move most of this to WorkflowBase ?
    def __init__(
        self,
        namespace: str,
        request_body: Dict,
        auth_header: Optional[str],
        dry_run=False,
    ):
        self.username = argo_engine_helper.get_username_from_token(auth_header)
        self.gen3username_label = argo_engine_helper.convert_gen3username_to_pod_label(
            self.username
        )
        team_project = request_body.get(TEAM_PROJECT_FIELD_NAME)
        if not team_project:
            raise Exception(
                "the '{}' field is required for this endpoint, but was not found in the request body".format(
                    TEAM_PROJECT_FIELD_NAME
                )
            )
        self.gen3teamproject_label = (
            argo_engine_helper.convert_gen3teamproject_to_pod_label(team_project)
        )
        self.workflow_parameters = request_body

        super().__init__(
            namespace, WORKFLOW_ENTRYPOINT.PLP_ENTRYPOINT, dry_run
        )  # TODO not clear yet what was meant with "entrypoint..."

    def _add_metadata_annotations(self):
        super()._add_metadata_annotations()
        self.metadata.add_metadata_annotation(
            "workflow_name", self.workflow_parameters.get("workflow_name")
        )

    def _add_metadata_labels(self):
        super()._add_metadata_labels()
        self.metadata.add_metadata_label(
            GEN3_USER_METADATA_LABEL, self.gen3username_label
        )
        self.metadata.add_metadata_label(
            GEN3_TEAM_PROJECT_METADATA_LABEL, self.gen3teamproject_label
        )

    def _add_spec_scaling_group(self):
        # Check if default or custom are confined
        scaling_group_config = argo_engine_helper._get_argo_config_dict().get(
            "scaling_groups", {}
        )

        # If not we are in QA
        if not scaling_group_config.get("default") and not scaling_group_config.get(
            "custom"
        ):
            return

        # First check if name in custom config, else use default
        if scaling_group_config.get("custom", {}).get(self.username):
            scaling_group = scaling_group_config["custom"][self.username]
        else:
            scaling_group = scaling_group_config["default"]

        self.spec.add_scaling_group(scaling_group)

    def _add_param_helper(self, parameters: Dict) -> None:
        for parameter_name, parameter_val in parameters.items():
            default_val = self.PARAMETER_TO_DEFAULT_VALS.get(parameter_name, "")
            if parameter_name in self.ENUM_PARAMETERS_TO_ENUM_VALS:
                self.spec.add_enum_parameter(
                    parameter_name,
                    parameter_val,
                    self.ENUM_PARAMETERS_TO_ENUM_VALS.get(parameter_name),
                    default_val,
                )
            else:
                self.spec.add_string_parameter(
                    parameter_name, parameter_val, default_val
                )

    def _add_user_defined_spec_parameters(self):
        self._add_param_helper(self.workflow_parameters)

    def _add_hard_coded_spec_parameters(self):
        self._add_param_helper(self.HARD_CODED_PARAMETERS)

    def _add_spec_parameters(self):
        """spec parameter ordering matters and must align with input parameter order
        in the self.template_ref. Thus we setup the user defined parameters then
        hard coded ones.

        Args:
            spec_parameters (Dict): _description_
        """
        self._add_user_defined_spec_parameters()
        self._add_hard_coded_spec_parameters()
        self._add_param_helper(
            {"internal_api_env": argo_engine_helper._get_internal_api_env()}
        )

    def _add_spec_volumes(self):
        pvc_name = argo_engine_helper._get_argo_config_dict().get(
            "pvc", BACKUP_PVC_NAME
        )
        logger.info(f"pvc {pvc_name} is used as storage gateway pvc")
        self.spec.add_persistent_volume_claim("gateway", pvc_name)
        self.spec.add_empty_dir("workdir", "20Gi")

    def _add_spec_podMetadata_annotations(self):
        self.spec.add_pod_metadata_annotation("gen3username", self.username)

    def _add_spec_podMetadata_labels(self):
        self.spec.add_pod_metadata_label("gen3username", self.gen3username_label)

    def setup_spec(self):
        super().setup_spec()
        self.spec.set_podGC_strategy(POD_COMPLETION_STRATEGY.ONPODCOMPLETION.value)
        self._add_spec_scaling_group()
        self._add_spec_podMetadata_annotations()
        self._add_spec_podMetadata_labels()
        self._add_spec_parameters()
        self._add_spec_volumes()
        self.spec.set_workflow_template_ref(self.workflow_parameters.get("template_version"))

    def generate_argo_workflow(self):
        return super()._to_dict()

    @staticmethod
    def interpret_plp_workflow_error(step_name: str, step_log: str) -> str:
        """Returns a clean error message without potentially sensitive log information. 
        """
        if step_name == "extract-data":
            show_error = "Error while retrieving data from DB. The DB is possibly down, or DB connection details are incorrect."
        elif step_name == "extract-data" and ("Timeout" in step_log or "timeout" in step_log):
            show_error = "A timeout occurred while fetching data. Please retry running your workflow."
        elif step_name == "downloadable-output":
            show_error = "An error occurred while trying to generate the workflow results. Please retry running your workflow."
        elif "indexd-record" in step_name and "HTTPError" in step_log:
            show_error = "An HTTP error occurred while creating an index record. Please retry running your workflow."
        else:
            show_error = "Error at step " + step_name + ". Please contact system admin for further troubleshooting."
        return show_error
