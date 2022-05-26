import unittest.mock as mock

from argowrapper.constants import *
from argowrapper.workflows.argo_workflows.gwas import *
from test.constants import EXAMPLE_AUTH_HEADER

request_body = {
    "n_pcs": 3,
    "covariates": ["ID_2000006886", "ID_2000000324"],
    "out_prefix": "vadc_genesis",
    "outcome": "ID_2000006885",
    "outcome_is_binary": "false",
    "maf_threshold": 0.01,
    "imputation_score_cutoff": 0.3,
    "template_version": "gwas-template-6226080403eb62585981d9782aec0f3a82a7e906",
    "source_id": 4,
    "cohort_definition_id": 70,
    "workflow_name": "wf_name",
}

config = {"environment": "default", "scaling_groups": {"gen3user": "group_1"}}
with mock.patch(
    "argowrapper.workflows.argo_workflows.gwas.argo_engine_helper._get_argo_config_dict"
) as mock_config_dict:
    mock_config_dict.return_value = config
    gwas = GWAS(ARGO_NAMESPACE, request_body, EXAMPLE_AUTH_HEADER)
    gwas_yaml = gwas._to_dict()
    gwas_metadata = gwas_yaml.get("metadata")
    gwas_spec = gwas_yaml.get("spec")


def test_gwas_yaml_apiVersion_and_kind():
    assert gwas_yaml.get("apiVersion") == API_VERSION
    assert gwas_yaml.get("kind") == WORKFLOW_KIND


def test_gwas_yaml_metadata():
    assert gwas_metadata.get("namespace") == ARGO_NAMESPACE

    gwas_metadata_annotations = gwas_metadata.get("annotations")
    assert gwas_metadata_annotations.get("workflows.argoproj.io/version") == ">= 3.1.0"
    assert gwas_metadata_annotations.get("workflow_name") == "wf_name"

    gwas_metadata_labels = gwas_metadata.get("labels")
    assert gwas_metadata_labels.get("workflows.argoproj.io/archive-strategy") == "true"
    assert gwas_metadata_labels.get("gen3username") == "user-test user"


def test_gwas_yaml_spec_entrypoint():
    assert gwas_spec.get("entrypoint") == WORKFLOW_ENTRYPOINT.GWAS_ENTRYPOINT.value


def test_gwas_yaml_spec_podGC():
    assert (
        gwas_spec.get("podGC").get("strategy")
        == POD_COMPLETION_STRATEGY.ONWORKFLOWSUCCESS.value
    )


def test_gwas_yaml_spec_nodeSelector():
    node_selector = gwas_spec.get("nodeSelector")
    assert node_selector.get("role") == "workflow"

    tolerations = gwas_spec.get("tolerations")
    assert tolerations[0].get("value") == "workflow"


def test_gwas_yaml_spec_podMetadata():
    podMetadata = gwas_spec.get("podMetadata")
    assert podMetadata.get("annotations").get("gen3username") == "test user"
    assert podMetadata.get("labels").get("gen3username") == "user-test user"


def _convert_parameters_to_dict(parameters: Dict):
    parameter_dict = {}
    for elem in parameters:
        parameter_dict[elem.get("name")] = elem.get("value")

    return parameter_dict


def test_gwas_yaml_spec_arguments():
    parameters = _convert_parameters_to_dict(
        gwas_spec.get("arguments").get("parameters")
    )
    user_params = {
        "n_pcs": 3,
        "covariates": "ID_2000006886 ID_2000000324",
        "out_prefix": "vadc_genesis",
        "outcome": "ID_2000006885",
        "outcome_is_binary": "FALSE",
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
        "cohort_definition_id": 70,
    }

    for param_name, param_val in user_params.items():
        assert param_val == parameters[param_name]

    hardcoded_params = {
        "pca_file": "/commons-data/pcs.RData",
        "relatedness_matrix_file": "/commons-data/KINGmatDeg3.RData",
        "genome_build": "hg19",
        "segment_length": 2000,
        "variant_block_size": 100,
        "mac_threshold": 0,
    }

    for param_name, param_val in hardcoded_params.items():
        assert param_val == parameters[param_name]