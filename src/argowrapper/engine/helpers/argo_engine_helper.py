import string
import re
from typing import Dict
import random
import json
from argowrapper import logger
import jwt
import requests

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
        logger.error(
            f"user {gen3_user_name} is not a part of any scaling group, setting it automatically to workflow"
        )
        scaling_group = "workflow"

    # Note: when nodeSelector is returned from argo template, it becomes node_selector
    workflow["spec"]["nodeSelector"]["role"] = scaling_group
    workflow["spec"]["tolerations"][0]["value"] = scaling_group


def add_argo_template(template_version: str, workflow: Dict) -> None:
    workflow["spec"]["workflowTemplateRef"]["name"] = template_version


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


def add_gen3user_label_and_annotation(username: str, workflow: Dict) -> None:
    workflow["spec"]["podMetadata"]["labels"][
        "gen3username"
    ] = convert_gen3username_to_label(username)

    workflow["spec"]["podMetadata"]["annotations"]["gen3username"] = username

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


def _convert_request_body_to_parameter_dict(request_body: Dict) -> Dict:
    return {
        "n_pcs": request_body.get("n_pcs"),
        "covariates": " ".join(request_body.get("covariates")),
        "outcome": request_body.get("outcome"),
        "out_prefix": request_body.get("out_prefix"),
        "outcome_is_binary": "TRUE"
        if request_body.get("outcome_is_binary")
        else "FALSE",
        "maf_threshold": request_body.get("maf_threshold"),
        "imputation_score_cutoff": request_body.get("imputation_score_cutoff"),
        "cohort_definition_id": request_body.get("cohort_definition_id"),
    }


def add_cohort_middleware_request(request_body: Dict, workflow: Dict) -> None:
    for dict in workflow["spec"]["arguments"]["parameters"]:
        if dict.get("name") == "cohort_middleware_url":
            dict["value"] = _build_cohort_middleware_url(request_body)
        if dict.get("name") == "cohort_middleware_body":
            dict["value"] = _build_cohort_middleware_body(request_body)


def _build_cohort_middleware_body(request_body: Dict) -> str:
    prefixed_concept_ids = request_body.get("covariates") + [
        request_body.get("outcome")
    ]
    prefixed_concept_ids = [f'"{concept_id}"' for concept_id in prefixed_concept_ids]

    formatted_prefixed_concept_ids = f'[{", ".join(prefixed_concept_ids)}]'
    return f'{{"PrefixedConceptIds": {formatted_prefixed_concept_ids}}}'


def _build_cohort_middleware_url(request_body: Dict) -> str:
    environment = _get_argo_config_dict().get("environment", "default")
    return f'http://cohort-middleware-service.{environment}/cohort-data/by-source-id/{request_body.get("source_id")}/by-cohort-definition-id/{request_body.get("cohort_definition_id")}'


def setup_workspace_token_service(header: str) -> bool:
    jwt_token = auth._parse_jwt(header)
    environment = _get_argo_config_dict().get("environment", "default")
    logger.info(_get_argo_config_dict())
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}",
    }

    try:
        connected_res = requests.get(
            f"http://workspace-token-service.{environment}/oauth2/connected?idp=default",
            headers=headers,
        )
        logger.info(connected_res)
        if connected_res.status_code == 400:
            logger.error(
                f"calling connected url for workspace token service failed with error {connected_res.content}"
            )
            return False

        if connected_res.status_code == 403:
            logger.info(
                "refresh token expired or user not logged in, fetching new refresh token"
            )
            authorization_res = requests.get(
                f"http://workspace-token-service.{environment}/oauth2/authorization_url?idp=default"
            )
            if authorization_res.status_code == 400:
                logger.error(
                    f"calling authorization_url endpoint in workspace token service failed with error {authorization_res.content}"
                )
                return False

        return True

    except Exception as exception:
        logger.error(f"workspace token service setup failed with error {exception}")

    return False
