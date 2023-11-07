import json
import random
import re
import string
from typing import Callable, Dict, List

import jwt

from argowrapper import logger
from argowrapper.auth import Auth
from argowrapper.constants import (
    ARGO_CONFIG_PATH,
    GEN3_USER_METADATA_LABEL,
    GEN3_TEAM_PROJECT_METADATA_LABEL,
)

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


def parse_common_details(
    workflow_details: Dict[str, any], workflow_type: str
) -> Dict[str, any]:
    phase = workflow_details["status"].get("phase")
    if workflow_type == "active_workflow":
        shutdown = workflow_details["spec"].get("shutdown")
        if shutdown == "Terminate":
            if phase == "Running":
                phase = "Canceling"
            if phase == "Failed":
                phase = "Canceled"
    elif workflow_type == "archived_workflow":
        pass

    return {
        "name": workflow_details["metadata"].get("name"),
        "phase": phase,
        "submittedAt": workflow_details["metadata"].get("creationTimestamp"),
        "startedAt": workflow_details["status"].get("startedAt"),
        "finishedAt": workflow_details["status"].get("finishedAt"),
    }


def parse_details(
    workflow_details: Dict[str, any], workflow_type: str
) -> Dict[str, any]:
    result = parse_common_details(
        workflow_details=workflow_details, workflow_type=workflow_type
    )
    result["wf_name"] = (
        workflow_details["metadata"].get("annotations", {}).get("workflow_name")
    )
    result["arguments"] = workflow_details["spec"].get("arguments")
    result["progress"] = workflow_details["status"].get("progress")
    result["outputs"] = workflow_details["status"].get("outputs", {})
    result[GEN3_USER_METADATA_LABEL] = (
        workflow_details["metadata"].get("labels").get(GEN3_USER_METADATA_LABEL)
    )
    result[GEN3_TEAM_PROJECT_METADATA_LABEL] = (
        workflow_details["metadata"].get("labels").get(GEN3_TEAM_PROJECT_METADATA_LABEL)
    )
    return result


def parse_list_item(
    workflow_details: Dict[str, any],
    workflow_type: str,
    get_archived_workflow_given_name: Callable = None,
) -> Dict[str, any]:
    """Parse the return of workflow list view"""
    result = parse_common_details(
        workflow_details=workflow_details, workflow_type=workflow_type
    )
    if get_archived_workflow_given_name is None:
        result["wf_name"] = (
            workflow_details["metadata"].get("annotations", {}).get("workflow_name")
        )
    else:
        # this is needed because archived list items do not have metadata.annotations
        # returned by the list service...so we need to call another service to get it:
        result["wf_name"] = get_archived_workflow_given_name(
            workflow_details["metadata"].get("uid")
        )
    result["uid"] = workflow_details["metadata"].get("uid")
    return result


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


def get_username_from_token(header_and_or_token: str) -> str:
    """

    Args:
        header (str): authorization header that contains a jwt token, or just the jwt token

    Returns:
        str: username
    """
    jwt_token = auth._parse_jwt(header_and_or_token)
    decoded = jwt.decode(jwt_token, options={"verify_signature": False})
    username = decoded.get("context", {}).get("user", {}).get("name")
    logger.info(f"{username} is submitting a workflow")
    return username
