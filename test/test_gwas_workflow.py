from textwrap import indent
import unittest.mock as mock
import json

from argowrapper.constants import *
from argowrapper.workflows.argo_workflows.gwas import *
from test.constants import EXAMPLE_AUTH_HEADER

variables = [
    {"variable_type": "concept", "concept_id": "2000000324"},
    {"variable_type": "concept", "concept_id": "2000000123"},
    {"variable_type": "custom_dichotomous", "cohort_ids": [1, 3]},
]

request_body = {
    "n_pcs": 3,
    "variables": variables,
    "hare_population": "hare",
    "out_prefix": "vadc_genesis",
    "outcome": 1,
    "maf_threshold": 0.01,
    "imputation_score_cutoff": 0.3,
    "template_version": "gwas-template-latest",
    "source_id": 4,
    "case_cohort_definition_id": 70,
    "control_cohort_definition_id": -1,
    "workflow_name": "wf_name",
}

config = {"environment": "default", "scaling_groups": {"default": "group_1"}}
with mock.patch(
    "argowrapper.workflows.argo_workflows.gwas.argo_engine_helper._get_argo_config_dict"
) as mock_config_dict:
    mock_config_dict.return_value = config
    gwas = GWAS(ARGO_NAMESPACE, request_body, EXAMPLE_AUTH_HEADER)
    gwas_yaml = gwas._to_dict()
    gwas_metadata = gwas_yaml.get("metadata")
    gwas_spec = gwas_yaml.get("spec")
    print(gwas_spec)


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
        == POD_COMPLETION_STRATEGY.ONPODCOMPLETION.value
    )


def test_gwas_yaml_spec_nodeSelector():
    node_selector = gwas_spec.get("nodeSelector")
    assert node_selector.get("role") == "group_1"

    tolerations = gwas_spec.get("tolerations")
    assert tolerations[0].get("value") == "group_1"

    local_config = {"environment": "default", "scaling_groups": {}}
    with mock.patch(
        "argowrapper.workflows.argo_workflows.gwas.argo_engine_helper._get_argo_config_dict"
    ) as local_mock_config_dict:
        local_mock_config_dict.return_value = local_config
        loc_gwas = GWAS(ARGO_NAMESPACE, request_body, EXAMPLE_AUTH_HEADER)
        loc_gwas_yaml = loc_gwas._to_dict()
        loc_gwas_metadata = loc_gwas_yaml.get("metadata")
        loc_gwas_spec = loc_gwas_yaml.get("spec")

        assert "nodeSelector" not in loc_gwas_spec
        assert "tolerations" not in loc_gwas_spec

    local_config = {
        "environment": "default",
        "scaling_groups": {"default": "blah", "custom": {"test user": "group_10"}},
    }
    with mock.patch(
        "argowrapper.workflows.argo_workflows.gwas.argo_engine_helper._get_argo_config_dict"
    ) as local_mock_config_dict:
        local_mock_config_dict.return_value = local_config
        loc_gwas = GWAS(ARGO_NAMESPACE, request_body, EXAMPLE_AUTH_HEADER)
        loc_gwas_yaml = loc_gwas._to_dict()
        loc_gwas_metadata = loc_gwas_yaml.get("metadata")
        loc_gwas_spec = loc_gwas_yaml.get("spec")

        node_selector = loc_gwas_spec.get("nodeSelector")
        assert node_selector.get("role") == "group_10"

        tolerations = loc_gwas_spec.get("tolerations")
        assert tolerations[0].get("value") == "group_10"


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
        "variables": variables,
        "out_prefix": "vadc_genesis",
        "variables": variables,
        "maf_threshold": 0.01,
        "imputation_score_cutoff": 0.3,
    }

    for param_name, param_val in user_params.items():
        if param_name == "variables":
            for _, variable in enumerate(param_val):
                result = parameters[param_name].replace("\n", "")
                for key in variable:
                    assert str(key) in result

        elif param_name == "outcome":
            assert json.dumps(param_val, indent=0) == parameters[param_name]
        else:
            assert param_val == parameters[param_name]

    hardcoded_params = {
        "pca_file": "/commons-data/pcs.RData",
        "relatedness_matrix_file": "/commons-data/KINGmatDeg3.RData",
        "segment_length": 2000,
        "variant_block_size": 100,
        "mac_threshold": 0,
    }

    for param_name, param_val in hardcoded_params.items():
        assert param_val == parameters[param_name]
