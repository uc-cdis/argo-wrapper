import re
from gen3authz.client.arborist.client import ArboristClient
from gen3authz.client.arborist.errors import ArboristError
from argowrapper import logger
from argowrapper.constants import (
    TOKEN_REGEX,
    ARGO_ACCESS_SERVICE,
    ARGO_ACCESS_RESOURCES,
    ARGO_ACCESS_METHOD,
)


class Auth:
    """

    A class to interact with arborist for authentication

    """

    def __init__(self):
        self.arborist_client = ArboristClient(logger=logger)

    def _parse_jwt(self, token: str) -> str:

        parsed_token = re.sub(TOKEN_REGEX, "", token)
        parsed_token = parsed_token.replace(" ", "")
        if len(parsed_token.split(".")) != 3:
            logger.error("malformed token")
            return ""

        logger.info(parsed_token)
        return parsed_token

    def authenticate(self, token: str) -> bool:
        """

        jwt token authentication for mariner access

        Args:
            token (str): authorization token

        Returns:
            bool: is user authorized to access resources in argo
        """
        jwt = self._parse_jwt(token)

        try:
            authorized = self.arborist_client.auth_request(
                jwt,
                ARGO_ACCESS_SERVICE,
                ARGO_ACCESS_METHOD,
                resources=ARGO_ACCESS_RESOURCES,
            )

        except ArboristError as exception:
            logger.error(f"error while talking to arborist with error {exception}")
            authorized = False

        logger.info(f"here is the authorized {authorized}")
        return authorized