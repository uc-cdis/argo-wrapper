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


def parse_status(status_dict: Dict[str, any], workflow_type: str) -> Dict[str, any]:
    phase = status_dict["status"].get("phase")
    if workflow_type == "active_workflow":
        shutdown = status_dict["spec"].get("shutdown")
        if shutdown == "Terminate":
            if phase == "Running":
                phase = "Canceling"
            if phase == "Failed":
                phase = "Canceled"
    elif workflow_type == "archived_workflow":
        pass

    return {
        "name": status_dict["metadata"].get("name"),
        "wf_name": status_dict["metadata"].get("annotations", {}).get("workflow_name"),
        "arguments": status_dict["spec"].get("arguments"),
        "phase": phase,
        "progress": status_dict["status"].get("progress"),
        "submittedAt": status_dict["metadata"].get("creationTimestamp"),
        "startedAt": status_dict["status"].get("startedAt"),
        "finishedAt": status_dict["status"].get("finishedAt"),
        "outputs": status_dict["status"].get("outputs", {}),
    }


def parse_list_item(list_dict: Dict[str, any], workflow_type: str) -> Dict[str, any]:
    """Parse the return of workflow list view"""
    phase = list_dict["status"].get("phase")
    if workflow_type == "active_workflow":
        shutdown = list_dict["spec"].get("shutdown")
        if shutdown == "Terminate":
            if phase == "Running":
                phase = "Canceling"
            if phase == "Failed":
                phase = "Canceled"
    elif workflow_type == "archived_workflow":
        pass

    return {
        "name": list_dict["metadata"].get("name"),
        "wf_name": list_dict["metadata"].get("annotations", {}).get("workflow_name")
        if workflow_type == "active_workflow"
        else "",
        "uid": list_dict["metadata"].get("uid"),
        "phase": phase,
        "submittedAt": list_dict["metadata"].get("creationTimestamp"),
        "startedAt": list_dict["status"].get("startedAt"),
        "finishedAt": list_dict["status"].get("finishedAt"),
    }


def remove_list_duplicate(
    workflow_list: List[Dict], archived_workflow_list: List[Dict]
) -> List[Dict]:
    """Remove any overlap between active workflow list and archived workflow list"""
    if len(workflow_list) == 0 and len(archived_workflow_list) == 0:
        uniq_list = []
        return uniq_list
    elif len(workflow_list) == 0 and len(archived_workflow_list) >= 1:
        uniq_list = archived_workflow_list[:]
        return uniq_list
    elif len(archived_workflow_list) == 0 and len(workflow_list) >= 1:
        uniq_list = workflow_list[:]
        return uniq_list
    else:
        uniq_list = workflow_list[:]
        uid_list = tuple(
            [single_workflow.get("uid") for single_workflow in workflow_list]
        )
        for archive_workflow in archived_workflow_list:
            archive_workflow_uid = archive_workflow.get("uid")
            if archive_workflow_uid not in uid_list:
                uniq_list.append(archive_workflow)
            else:
                pass
        return uniq_list


def _get_argo_config_dict() -> Dict:
    with open(ARGO_CONFIG_PATH, encoding="utf-8") as file_stream:
        data = json.load(file_stream)
        return data


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
