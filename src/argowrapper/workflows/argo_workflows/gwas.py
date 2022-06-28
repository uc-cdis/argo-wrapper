from typing import Dict

import argowrapper.engine.helpers.argo_engine_helper as argo_engine_helper
from argowrapper import logger
from argowrapper.constants import POD_COMPLETION_STRATEGY, PVC_NAME, WORKFLOW_ENTRYPOINT
from argowrapper.workflows.workflow_base import WorkflowBase


class GWAS(WorkflowBase):
    """A class to represent the gwas workflow

    Attributes:
        dry_run (bool): is dry run
        username (string): username of person who submitted workflow
        gen3username_label (string): k8 label converted from username
        _request_body (Dict): a dictionary of request parameters from the user
    """

    def __create_gds_files() -> str:
        gds_files = [
            f'"/commons-data/gds/chr{chrom_num}.merged.vcf.gz.gds"'
            for chrom_num in range(1, 23)
        ]
        return f'[{", ".join(gds_files)}]'

    HARD_CODED_PARAMETERS = {
        "genome_build": "hg19",
        "pca_file": "/commons-data/pcs.RData",
        "relatedness_matrix_file": "/commons-data/KINGmatDeg3.RData",
        "n_segments": 0,
        "segment_length": 2000,
        "variant_block_size": 100,
        "mac_threshold": 0,
        "gds_files": __create_gds_files(),
    }

    PARAMETER_TO_DEFAULT_VALS = {
        "n_pcs": 0,
        "internal_api_env": "default",
        "control_cohort_definition_id": -1,
        "out_prefix": "genesis_vadc",
        "genome_build": "hg19",
        "segment_length": 2000,
        "variant_block_size": 1024,
        "prefixed_hare_concept_id": "ID_2000007027",
    }

    ENUM_PARAMETERS_TO_ENUM_VALS = {
        "genome_build": ["hg38", "hg19"],
    }

    METADATA_ANNOTATIONS = {
        "workflows.argoproj.io/version": ">= 3.1.0",
    }

    METADATA_LABELS = {"workflows.argoproj.io/archive-strategy": "true"}

    def __init__(
        self, namespace: str, request_body: Dict, auth_header: str, dry_run=False
    ):
        self.username = argo_engine_helper.get_username_from_token(auth_header)
        self.gen3username_label = argo_engine_helper.convert_gen3username_to_label(
            self.username
        )
        self._request_body = request_body

        super().__init__(namespace, WORKFLOW_ENTRYPOINT.GWAS_ENTRYPOINT, dry_run)

    def _add_metadata_annotations(self):
        super()._add_metadata_annotations()
        self.metadata.add_metadata_annotation(
            "workflow_name", self._request_body.get("workflow_name")
        )

    def _add_metadata_labels(self):
        super()._add_metadata_labels()
        self.metadata.add_metadata_label("gen3username", self.gen3username_label)

    def _add_spec_scaling_group(self):
        if "qa_scaling_groups" in argo_engine_helper._get_argo_config_dict():
            return

        user_to_scaling_groups = argo_engine_helper._get_argo_config_dict().get(
            "scaling_groups", {}
        )
        scaling_group = user_to_scaling_groups.get(self.username)
        if not scaling_group:
            logger.error(
                f"user {self.username} is not a part of any scaling group, setting group to automatically be workflow"
            )
            scaling_group = "workflow"

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
        spec_parameters = argo_engine_helper._convert_request_body_to_parameter_dict(
            self._request_body
        )
        self._add_param_helper(spec_parameters)

    def _add_hard_coded_spec_parameters(self):
        self._add_param_helper(self.HARD_CODED_PARAMETERS)

    def _add_spec_parameters(self):
        """spec parameter ordering matters and must aline with input parameter order
        in the self.template_ref. Thus we setup the user defined parameters then
        hard coded ones.

        Args:
            spec_parameters (Dict): _description_
        """
        self._add_user_defined_spec_parameters()
        self._add_hard_coded_spec_parameters()

    def _add_spec_volumes(self):
        self.spec.add_persistent_volume_claim("gateway", PVC_NAME)
        self.spec.add_empty_dir("workdir", "10Gi")

    def _add_spec_podMetadata_annotations(self):
        self.spec.add_pod_metadata_annotation("gen3username", self.username)

    def _add_spec_podMetadata_labels(self):
        self.spec.add_pod_metadata_label("gen3username", self.gen3username_label)

    def setup_spec(self):
        super().setup_spec()
        self.spec.set_podGC_strategy(POD_COMPLETION_STRATEGY.ONWORKFLOWSUCCESS.value)
        self._add_spec_scaling_group()
        self._add_spec_podMetadata_annotations()
        self._add_spec_podMetadata_labels()
        self._add_spec_parameters()
        self._add_spec_volumes()
        self.spec.set_workflow_template_ref(self._request_body.get("template_version"))

    def generate_argo_workflow(self):
        return super()._to_dict()
