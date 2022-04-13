import string
import re
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
    workflow["spec"]["node_selector"]["role"] = scaling_group
    workflow["spec"]["tolerations"][0]["value"] = scaling_group

    # Here we convert back node_selector to original syntax nodeSelector
    workflow["spec"]["nodeSelector"] = workflow["spec"].pop("node_selector")


def _convert_to_hex(special_character_match: str) -> str:
    if (match := special_character_match.group()) :
        hex_val = match.encode("utf-8").hex()
        return f"-{hex_val}"


def convert_gen3username_to_label(username: str) -> str:
    """a gen3username is an email and a label is a k8 pod label
       core issue this causes is that email can have special characters but
       pod labels can only have '-', '_' or '.'. This function will convert
       all special characters to "-{hex_value}" and prepend "user-" to the label.
       eg "!" -> "user--21"

    Args:
        username (str): email address of the user that can contain special characters

    Returns:
        str: converted string where all special characters are replaced with "-{hex_value}"
    """

    # TODO: please not that there are more special characteres than this https://stackoverflow.com/questions/2049502/what-characters-are-allowed-in-an-email-address/2071250#2071250
    # in order to address this have a list of accepted characters and regex match everything that is not accepted
    special_characters = re.escape(string.punctuation)
    regex = f"[{special_characters}]"
    logger.debug((label := re.sub(regex, _convert_to_hex, username)))
    return f"user-{label}"


def add_gen3user_label(username: str, workflow: Dict) -> None:
    workflow["spec"]["pod_metadata"]["labels"][
        "gen3username"
    ] = convert_gen3username_to_label(username)

    workflow["spec"]["podMetadata"] = workflow["spec"].pop("pod_metadata")
