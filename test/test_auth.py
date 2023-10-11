from re import A
import pytest
import unittest.mock as mock
from unittest.mock import patch
from argowrapper.constants import ARGO_ACCESS_SERVICE

from argowrapper.auth import Auth
from gen3authz.client.arborist.errors import ArboristError


def test_parse_token_suceed():
    auth = Auth()

    token = "Bearer something.something.something"
    jwt = auth._parse_jwt(token)
    assert jwt == "something.something.something"

    token = "bearer something_else.s.s"
    jwt = auth._parse_jwt(token)
    assert jwt == "something_else.s.s"

    token = "beAReR test.test.test"
    jwt = auth._parse_jwt(token)
    assert jwt == "test.test.test"


def test_parse_token_failed():
    auth = Auth()

    token = "basomasdfpomasopdfma"
    jwt = auth._parse_jwt(token)
    assert jwt == ""

    token = "bearer sdf.sdf"
    jwt = auth._parse_jwt(token)
    assert jwt == ""


def test_authenticate_suceed():
    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(return_value=True)
    token = "Bearer test.test.test"

    authorized = auth.authenticate(token)
    assert authorized == True


def test_authenticate_failed():
    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(return_value=False)
    token = "Bearer fail"

    authorized = auth.authenticate(token)
    assert authorized == False


def test_authenticate_failed2():
    auth = Auth()
    token = None

    authorized = auth.authenticate(token)
    assert authorized == False


def test_authenticate_failed3():
    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(
        side_effect=ArboristError("Arborist Error", "error code")
    )
    token = "Bearer test.test.test"

    authorized = auth.authenticate(token)
    assert authorized == False


def test_authenticate_failed4():
    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(
        side_effect=Exception("Arborist Error")
    )
    authorized = None
    token = "Bearer test.test.test"
    with pytest.raises(Exception) as exception:
        authorized = auth.authenticate(token)

    assert authorized is None


def test_should_fail_if_only_one_of_authorizations_fails1():
    def mock_auth_request(jwt, service, method, resources):
        """dummy implementation that fails only for argo auth"""
        if service == ARGO_ACCESS_SERVICE:
            return False
        else:
            return True

    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(side_effect=mock_auth_request)
    token = "Bearer test.test.test"

    authorized = auth.authenticate(token)
    assert authorized == False

    authorized = auth.authenticate(token, team_project="test")
    assert authorized == False


def test_should_fail_if_only_one_of_authorizations_fails2():
    def mock_auth_request(jwt, service, method, resources):
        """dummy implementation that succeeds always for argo auth"""
        if service == ARGO_ACCESS_SERVICE:
            return True
        else:
            return False

    auth = Auth()
    auth.arborist_client.auth_request = mock.MagicMock(side_effect=mock_auth_request)
    token = "Bearer test.test.test"

    authorized = auth.authenticate(token)
    assert authorized == True

    authorized = auth.authenticate(token, team_project="test")
    assert authorized == False
