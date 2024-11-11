import json
import random
import re
import string
from typing import Any, Callable, Dict, List, Optional

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
    workflow_details: Dict[str, Any], workflow_type: str
) -> Dict[str, Any]:
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

    user_name_str = ""
    if workflow_details["metadata"].get("labels"):
        user_name_str = convert_username_label_to_gen3username(
            workflow_details["metadata"].get("labels").get(GEN3_USER_METADATA_LABEL)
        )

    return {
        "name": workflow_details["metadata"].get("name"),
        "phase": phase,
        GEN3_USER_METADATA_LABEL: user_name_str,
        "submittedAt": workflow_details["metadata"].get("creationTimestamp"),
        "startedAt": workflow_details["status"].get("startedAt"),
        "finishedAt": workflow_details["status"].get("finishedAt"),
    }


def parse_details(
    workflow_details: Dict[str, Any], workflow_type: str
) -> Dict[str, Any]:
    result = parse_common_details(
        workflow_details=workflow_details, workflow_type=workflow_type
    )
    result["wf_name"] = (
        workflow_details["metadata"].get("annotations", {}).get("workflow_name")
    )
    result["arguments"] = workflow_details["spec"].get("arguments")
    result["progress"] = workflow_details["status"].get("progress")
    result["outputs"] = workflow_details["status"].get("outputs", {})
    if workflow_details["metadata"].get("labels"):
        result[GEN3_USER_METADATA_LABEL] = convert_username_label_to_gen3username(
            workflow_details["metadata"].get("labels").get(GEN3_USER_METADATA_LABEL)
        )
        result[GEN3_TEAM_PROJECT_METADATA_LABEL] = convert_pod_label_to_gen3teamproject(
            workflow_details["metadata"]
            .get("labels")
            .get(GEN3_TEAM_PROJECT_METADATA_LABEL)
        )
    else:
        result[GEN3_USER_METADATA_LABEL] = None
        result[GEN3_TEAM_PROJECT_METADATA_LABEL] = None
    return result


def parse_list_item(
    workflow_details: Dict[str, Any],
    workflow_type: str,
    get_archived_workflow_wf_name_and_team_project: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Parse the return of workflow list view"""
    result = parse_common_details(
        workflow_details=workflow_details, workflow_type=workflow_type
    )
    if get_archived_workflow_wf_name_and_team_project is None:
        result["wf_name"] = (
            workflow_details["metadata"].get("annotations", {}).get("workflow_name")
        )
        result[GEN3_TEAM_PROJECT_METADATA_LABEL] = convert_pod_label_to_gen3teamproject(
            workflow_details["metadata"]
            .get("labels")
            .get(GEN3_TEAM_PROJECT_METADATA_LABEL)
        )
    else:
        # this is needed because archived list items do not have metadata.annotations or meta.labels
        # returned by the list service...so we need to call another service to get it:
        (
            wf_name,
            team_project,
            gen3username,
        ) = get_archived_workflow_wf_name_and_team_project(
            workflow_details["metadata"].get("uid")
        )
        result["wf_name"] = wf_name
        result[GEN3_TEAM_PROJECT_METADATA_LABEL] = team_project
        result[GEN3_USER_METADATA_LABEL] = gen3username

    result["uid"] = workflow_details["metadata"].get("uid")
    return result


def remove_list_duplicate(
    workflow_list1: List[Dict], workflow_list2: List[Dict]
) -> List[Dict]:
    """Remove any overlap between workflow_list1 and workflow_list2 using 'uid' field"""
    if len(workflow_list1) == 0 and len(workflow_list2) == 0:
        uniq_list = []
        return uniq_list
    elif len(workflow_list1) == 0 and len(workflow_list2) >= 1:
        uniq_list = workflow_list2[:]
        return uniq_list
    elif len(workflow_list2) == 0 and len(workflow_list1) >= 1:
        uniq_list = workflow_list1[:]
        return uniq_list
    else:
        uniq_list = workflow_list1[:]
        uid_list = tuple(
            [single_workflow.get("uid") for single_workflow in workflow_list1]
        )
        for workflow in workflow_list2:
            workflow_uid = workflow.get("uid")
            if workflow_uid not in uid_list:
                uniq_list.append(workflow)
            else:
                pass
        return uniq_list


def _get_argo_config_dict() -> Dict:
    with open(ARGO_CONFIG_PATH, encoding="utf-8") as file_stream:
        data = json.load(file_stream)
        return data


def _convert_to_hex(special_character_match: str) -> Optional[str]:
    if match := special_character_match.group():
        hex_val = match.encode("utf-8").hex()
        return f"-{hex_val}"


def convert_gen3username_to_pod_label(username: str) -> str:
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
    label = convert_string_to_pod_label(username)
    return f"user-{label}"


def convert_gen3teamproject_to_pod_label(team_project: str) -> str:
    """
    here we do a conversion of all to hex, as we need to be able to decode later on as well
    """
    label = team_project.encode("utf-8").hex()
    return label


def convert_pod_label_to_gen3teamproject(pod_label: str) -> Optional[str]:
    """
    Reverse the conversion gen3teamproject to pod_label.
    """
    if pod_label:
        team_project = bytes.fromhex(pod_label).decode("utf-8")
        return team_project
    else:
        return None


def convert_string_to_pod_label(value: str) -> str:
    """
    pod labels can only have '-', '_' or '.'. This function will convert
    at least all of the string.punctuation characters to a hex_value representation.
    """
    special_characters = re.escape(string.punctuation)
    regex = f"[{special_characters}]"
    logger.debug((label := re.sub(regex, _convert_to_hex, value)))
    return label


def get_username_from_token(header_and_or_token: Optional[str]) -> str:
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


def convert_username_label_to_gen3username(label: str) -> str:
    """this function will reverse the conversion of a username to label as
    defined by the convert_gen3username_to_pod_label function. eg "user--21" -> "!"

    Args:
        label (str): _description_

    Returns:
        : _description_
    """
    if label:
        label = label.replace("user-", "", 1)
        regex = r"-[0-9A-Za-z]{2}"
        return re.sub(regex, _convert_to_label, label)
    else:
        return ""


def _convert_to_label(special_character_match: str) -> Optional[str]:
    if match := special_character_match.group():
        match = match.strip("-")
        try:
            byte_array = bytearray.fromhex(match)
            return byte_array.decode()
        except:
            logger.info("match is not hex value, return original")
            return "-" + match
