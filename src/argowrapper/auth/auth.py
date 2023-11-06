import re

from gen3authz.client.arborist.client import ArboristClient
from gen3authz.client.arborist.errors import ArboristError

from argowrapper import logger
from argowrapper.constants import (
    ARGO_ACCESS_METHOD,
    ARGO_ACCESS_RESOURCES,
    ARGO_ACCESS_SERVICE,
    TEAM_PROJECT_ACCESS_SERVICE,
    TEAM_PROJECT_ACCESS_METHOD,
    TOKEN_REGEX,
)


class Auth:
    """

    A class to interact with arborist for authentication

    """

    def __init__(self):
        if ARGO_ACCESS_METHOD == "NONE":
            pass
        else:
            self.arborist_client = ArboristClient(logger=logger)

    def _parse_jwt(self, token: str) -> str:

        parsed_token = TOKEN_REGEX.sub("", token)
        parsed_token = parsed_token.replace(" ", "")
        if len(parsed_token.split(".")) != 3:
            logger.error("malformed token")
            return ""

        return parsed_token

    def authenticate(self, token: str, team_project=None) -> bool:
        """

        jwt token authentication for mariner access

        Args:
            token (str): authorization token

        Returns:
            bool: True if user is authorized to access resources in argo
        """
        if not token:
            logger.error("authentication token required.")
            return False

        jwt = self._parse_jwt(token)

        try:
            if ARGO_ACCESS_METHOD == "NONE":
                return True
            else:
                # check if user has been granted access to argo-wrapper itself:
                authorized_for_argo = self.arborist_client.auth_request(
                    jwt,
                    ARGO_ACCESS_SERVICE,
                    ARGO_ACCESS_METHOD,
                    resources=ARGO_ACCESS_RESOURCES,
                )
                logger.debug(f"authorized for argo-wrapper {authorized_for_argo}")
                if team_project:
                    # check if user has been granted access to this teamproject:
                    authorized_for_team_project = self.arborist_client.auth_request(
                        jwt,
                        TEAM_PROJECT_ACCESS_SERVICE,
                        TEAM_PROJECT_ACCESS_METHOD,
                        resources=team_project,
                    )
                    logger.debug(
                        f"authorized for team-project {authorized_for_team_project}"
                    )

        except ArboristError as exception:
            logger.error(f"error while talking to arborist with error {exception}")
            return False

        return authorized_for_argo and (
            (not team_project) or authorized_for_team_project
        )
