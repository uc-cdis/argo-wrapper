import string
from typing import Dict
import random
import json
from argowrapper import logger

from argowrapper.constants import ARGO_CONFIG_PATH


def generate_workflow_name() -> str:
    ending_id = "".join(random.choices(string.digits, k=10))
    return "argo-wrapper-workflow-" + ending_id


def add_parameters_to_gwas_workflow(parameters: Dict[str, any], workflow: Dict) -> None:
    for dict in workflow["spec"]["arguments"]["parameters"]:
        if (param_name := dict["name"]) in parameters:
            dict["value"] = parameters[param_name]


def add_name_to_workflow(workflow: Dict) -> str:
    workflow_name = generate_workflow_name()
    workflow["metadata"].pop("generateName", None)
    workflow["metadata"]["name"] = workflow_name
    return workflow_name


def parse_status(status_dict: Dict[str, any]) -> Dict[str, any]:
    return {
        "name": status_dict["metadata"].get("name"),
        "arguments": status_dict["spec"].get("arguments"),
        "phase": status_dict["status"].get("phase"),
        "progress": status_dict["status"].get("progress"),
        "startedAt": status_dict["status"].get("startedAt"),
        "finishedAt": status_dict["status"].get("finishedAt"),
        "outputs": status_dict["status"].get("outputs", {}),
    }


def _get_argo_config_dict() -> Dict:
    with open(ARGO_CONFIG_PATH, encoding="utf-8") as file_stream:
        data = json.load(file_stream)
        logger.debug(data)
        return data


def add_scaling_groups(gen3_user_name: str, workflow: Dict) -> None:
    user_to_scaling_groups = _get_argo_config_dict().get("scaling_groups", {})
    scaling_group = user_to_scaling_groups.get(gen3_user_name)
    if not scaling_group:
        raise Exception(f"user {gen3_user_name} is not a part of any scaling group")

    # Note: when nodeSelector is returned from argo template, it becomes node_selector
    workflow["spec"]["nodeSelector"]["role"] = scaling_group
    workflow["spec"]["tolerations"][0]["value"] = scaling_group


def add_argo_template(template_version: str, workflow: Dict) -> None:
    workflow["spec"]["workflowTemplateRef"]["name"] = template_version
