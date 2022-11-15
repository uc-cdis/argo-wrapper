import json
import random
import re
import string
from typing import Dict, List

import jwt

from argowrapper import logger
from argowrapper.auth import Auth
from argowrapper.constants import ARGO_CONFIG_PATH

auth = Auth()


def generate_workflow_name() -> str:
    ending_id = "".join(random.choices(string.digits, k=10))
    return "gwas-workflow-" + ending_id


def _get_internal_api_env() -> str:
    return _get_argo_config_dict().get("environment", "default")


def _convert_request_body_to_parameter_dict(request_body: Dict) -> Dict:
    """Basically returns a copy of the given dict, but with complex values stringified"""
    dict_with_stringified_items = {}
    for key, value in request_body.items():
        if isinstance(value, (float, str, int)):
            dict_with_stringified_items[key] = value
        else:
            dict_with_stringified_items[key] = json.dumps(value, indent=0)
    return dict_with_stringified_items


def parse_status(status_dict: Dict[str, any]) -> Dict[str, any]:
    phase = status_dict["status"].get("phase")
    shutdown = status_dict["spec"].get("shutdown")
    if shutdown == "Terminate":
        if phase == "Running":
            phase = "Canceling"
        if phase == "Failed":
            phase = "Canceled"

    return {
        "name": status_dict["metadata"].get("name"),
        "wf_name": status_dict["metadata"].get("annotations", {}).get("workflow_name"),
        "arguments": status_dict["spec"].get("arguments"),
        "phase": phase,
        "progress": status_dict["status"].get("progress"),
        "startedAt": status_dict["status"].get("startedAt"),
        "finishedAt": status_dict["status"].get("finishedAt"),
        "outputs": status_dict["status"].get("outputs", {}),
    }


def _get_argo_config_dict() -> Dict:
    with open(ARGO_CONFIG_PATH, encoding="utf-8") as file_stream:
        data = json.load(file_stream)
        return data


def add_scaling_groups(gen3_user_name: str, workflow: Dict) -> None:
    if "qa_scaling_groups" in _get_argo_config_dict():
        del workflow["spec"]["nodeSelector"]
        logger.info("we are in qa, removing node selector from header")
        return

    user_to_scaling_groups = _get_argo_config_dict().get("scaling_groups", {})
    scaling_group = user_to_scaling_groups.get(gen3_user_name)
    if not scaling_group:
        logger.error(
            f"user {gen3_user_name} is not a part of any scaling group, setting group to automatically be workflow"
        )
        scaling_group = "workflow"

    # Note: when nodeSelector is returned from argo template, it becomes node_selector
    workflow["spec"]["nodeSelector"]["role"] = scaling_group
    workflow["spec"]["tolerations"][0]["value"] = scaling_group


def _convert_to_hex(special_character_match: str) -> str:
    if match := special_character_match.group():
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


def get_username_from_token(auth_header: str) -> str:
    """

    Args:
        header (str): authorization header that contains a jwt token

    Returns:
        str: username
    """
    jwt_token = auth._parse_jwt(auth_header)
    decoded = jwt.decode(jwt_token, options={"verify_signature": False})
    username = decoded.get("context", {}).get("user", {}).get("name")
    logger.info(f"{username} is submitting a workflow")
    return username
