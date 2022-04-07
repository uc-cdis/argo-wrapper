import string
import re
from typing import Dict
import random
import json
from argowrapper import logger
import jwt

from argowrapper.constants import ARGO_CONFIG_PATH
from argowrapper.auth import Auth

auth = Auth()


def generate_workflow_name() -> str:
    ending_id = "".join(random.choices(string.digits, k=10))
    return "argo-wrapper-workflow-" + ending_id


def add_parameters_to_gwas_workflow(
    request_body: Dict[str, any], workflow: Dict
) -> None:
    parameters = _convert_request_body_to_parameter_dict(request_body)
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

    special_characters = re.escape(string.punctuation)
    regex = f"[{special_characters}]"
    logger.debug((label := re.sub(regex, _convert_to_hex, username)))
    return f"user-{label}"


def _convert_to_label(special_character_match: str) -> str:
    if (match := special_character_match.group()) :
        match = match.strip("-")
        byte_array = bytearray.fromhex(match)
        return byte_array.decode()


def convert_username_label_to_gen3username(label: str) -> str:
    """this function will reverse the conversion of a username to label as
    defined by the convert_gen3username_to_label function. eg "user--21" -> "!"

    Args:
        label (str): _description_

    Returns:
        : _description_
    """
    label = label.replace("user-", "", 1)
    regex = r"-[0-9A-Za-z]{2}"
    logger.debug((username := re.sub(regex, _convert_to_label, label)))
    return username


def add_gen3user_label(username: str, workflow: Dict) -> None:
    workflow["spec"]["pod_metadata"]["labels"][
        "gen3username"
    ] = convert_gen3username_to_label(username)

    workflow["spec"]["podMetadata"] = workflow["spec"].pop("pod_metadata")
    workflow["metadata"]["labels"]["gen3username"] = convert_gen3username_to_label(
        username
    )


def get_username_from_token(header: str) -> str:
    """

    Args:
        jwt_token (str): user jwt token

    Returns:
        str: username
    """
    jwt_token = auth._parse_jwt(header)
    decoded = jwt.decode(jwt_token, options={"verify_signature": False})
    username = decoded.get("context", {}).get("user", {}).get("name")
    logger.info(f"{username} is submitting a workflow")
    return username


def _convert_request_body_to_parameter_dict(body: Dict) -> Dict:
    logger.info(f'here is the type for is_binary {type(body["outcome_is_binary"])}')
    return {
        "n_pcs": body.get("n_pcs"),
        "covariates": (covariates := " ".join(body.get("covariates"))),
        "outcome": (outcome := body.get("outcome")),
        "out_prefix": body.get("out_prefix"),
        "outcome_is_binary": "TRUE" if body.get("outcome_is_binary") else "FALSE",
        "maf_threshold": body.get("maf_threshold"),
        "imputation_score_cutoff": body.get("imputation_score_cutoff"),
    }
