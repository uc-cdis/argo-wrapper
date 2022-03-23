from argowrapper.auth import Auth
import unittest.mock as mock


def test_parse_token_suceed():
    auth = Auth()

    token = "Bearer something.something.something"
    jwt = auth._parse_jwt(token)
    assert jwt == "something.something.something"

    token = "bearer something_else.s.s"
    jwt = auth._parse_jwt(token)
    assert jwt == "something_else.s.s"


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