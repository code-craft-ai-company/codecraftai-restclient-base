from http import HTTPStatus

from automojo import testbase

from automojo.errors.exceptions import HttpForbiddenError
from automojo.restclient.base.aspectsrest import ActionPattern, AspectsRest
from automojo.restclient.base.restclientbase import RestClientBase


class _CredentialStub:
    def __init__(self, username: str = "user", password: str = "pass"):
        self.username = username
        self.password = password
        return


class _ResponseStub:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code = status_code
        self.content = content
        return


class _SessionStub:
    def __init__(self, actions):
        self._actions = list(actions)
        self.prepared_requests = []
        return

    def prepare_request(self, req):
        self.prepared_requests.append(req)
        return req

    def send(self, prepared_req, timeout=None, verify=None):
        if len(self._actions) == 0:
            raise RuntimeError("No actions configured.")
        action = self._actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


class _ClientWithAuthTracking(RestClientBase):
    def __init__(self, *args, **kwargs):
        self.auth_calls = 0
        super().__init__(*args, **kwargs)
        return

    def authenticate(self):
        self.auth_calls += 1
        self._session = _SessionStub([])
        return


class _DispatchClient(RestClientBase):
    def __init__(self, *args, **kwargs):
        self.last_call = None
        super().__init__(*args, **kwargs)
        return

    def _perform_single_call(self, *args, **kwargs):
        self.last_call = "single_call"
        return self.last_call

    def _perform_single_connected_call(self, *args, **kwargs):
        self.last_call = "single_connected_call"
        return self.last_call

    def _perform_call_until_connection_failure(self, *args, **kwargs):
        self.last_call = "until_connection_failure"
        return self.last_call

    def _perform_call_until_success(self, *args, **kwargs):
        self.last_call = "until_success"
        return self.last_call

    def _perform_call_while_success(self, *args, **kwargs):
        self.last_call = "while_success"
        return self.last_call


def test_restclientbase_format_call_url_includes_port():
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        port=8080,
        scheme="http"
    )
    result = client._format_call_url("/api")
    testbase.assert_equal(result, "http://example:8080/api")
    return


def test_restclientbase_get_session_prefers_aspects_session():
    session = _SessionStub([])
    aspects = AspectsRest(session=session)
    client = _ClientWithAuthTracking(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client._get_session(aspects)
    testbase.assert_equal(result, session)
    testbase.assert_equal(client.auth_calls, 0)
    return


def test_restclientbase_get_session_authenticates_when_needed():
    aspects = AspectsRest(session=None)
    client = _ClientWithAuthTracking(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client._get_session(aspects)
    testbase.assert_equal(result, client._session)
    testbase.assert_equal(client.auth_calls, 1)
    return


def test_restclientbase_perform_call_routes_single_call():
    aspects = AspectsRest(action_pattern=ActionPattern.SINGLE_CALL)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client.perform_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(result, "single_call")
    testbase.assert_equal(client.last_call, "single_call")
    return


def test_restclientbase_perform_call_routes_single_connected_call():
    aspects = AspectsRest(action_pattern=ActionPattern.SINGLE_CONNECTED_CALL)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client.perform_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(result, "single_connected_call")
    testbase.assert_equal(client.last_call, "single_connected_call")
    return


def test_restclientbase_perform_call_routes_until_connection_failure():
    aspects = AspectsRest(action_pattern=ActionPattern.DO_UNTIL_CONNECTION_FAILURE)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client.perform_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(result, "until_connection_failure")
    testbase.assert_equal(client.last_call, "until_connection_failure")
    return


def test_restclientbase_perform_call_routes_until_success():
    aspects = AspectsRest(action_pattern=ActionPattern.DO_UNTIL_SUCCESS)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client.perform_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(result, "until_success")
    testbase.assert_equal(client.last_call, "until_success")
    return


def test_restclientbase_perform_call_routes_while_success():
    aspects = AspectsRest(action_pattern=ActionPattern.DO_WHILE_SUCCESS)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    result = client.perform_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(result, "while_success")
    testbase.assert_equal(client.last_call, "while_success")
    return


def test_restclientbase_perform_call_rejects_unknown_pattern():
    aspects = AspectsRest(action_pattern=99)
    client = _DispatchClient(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )

    error = None
    try:
        client.perform_call(
            leaf="/api",
            method="GET",
            params=None,
            body=None,
            exp_status=HTTPStatus.OK,
            headers=None,
            context_msg=None,
            aspects=aspects
        )
    except RuntimeError as err:
        error = err

    testbase.assert_equal(error is not None, True)
    return


def test_restclientbase_single_call_retries_auth_failure_once():
    session = _SessionStub([
        HttpForbiddenError("auth"),
        _ResponseStub(HTTPStatus.OK, b"ok")
    ])
    aspects = AspectsRest(session=session, connection_timeout=0, inactivity_timeout=0)
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    resp = client._perform_single_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(resp.status_code, HTTPStatus.OK)
    return


def test_restclientbase_single_call_raises_for_unexpected_status():
    session = _SessionStub([_ResponseStub(HTTPStatus.INTERNAL_SERVER_ERROR, b"fail")])
    aspects = AspectsRest(session=session, connection_timeout=0, inactivity_timeout=0)
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )

    error = None
    try:
        client._perform_single_call(
            leaf="/api",
            method="GET",
            params=None,
            body=None,
            exp_status=HTTPStatus.OK,
            headers=None,
            context_msg="context",
            aspects=aspects
        )
    except Exception as err:
        error = err

    testbase.assert_equal(error is not None, True)
    return


def test_restclientbase_single_connected_call_retries_until_success():
    session = _SessionStub([
        RuntimeError("connect fail"),
        _ResponseStub(HTTPStatus.OK, b"ok")
    ])
    aspects = AspectsRest(
        session=session,
        completion_timeout=1,
        completion_interval=0,
        connection_timeout=0,
        inactivity_timeout=0,
        retry_logging_interval=1
    )
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    resp = client._perform_single_connected_call(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(resp.status_code, HTTPStatus.OK)
    return


def test_restclientbase_call_until_success_returns_on_expected_status():
    session = _SessionStub([
        _ResponseStub(HTTPStatus.INTERNAL_SERVER_ERROR, b"fail"),
        _ResponseStub(HTTPStatus.OK, b"ok")
    ])
    aspects = AspectsRest(
        session=session,
        completion_timeout=1,
        completion_interval=0,
        connection_timeout=0,
        inactivity_timeout=0,
        allowed_error_codes=(HTTPStatus.INTERNAL_SERVER_ERROR,)
    )
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    resp = client._perform_call_until_success(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(resp.status_code, HTTPStatus.OK)
    return


def test_restclientbase_call_until_connection_failure_returns_last_response():
    session = _SessionStub([
        _ResponseStub(HTTPStatus.OK, b"ok"),
        RuntimeError("disconnect")
    ])
    aspects = AspectsRest(
        session=session,
        completion_timeout=1,
        completion_interval=0,
        connection_timeout=0,
        inactivity_timeout=0
    )
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    resp = client._perform_call_until_connection_failure(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(resp.status_code, HTTPStatus.OK)
    return


def test_restclientbase_call_while_success_returns_last_success():
    session = _SessionStub([
        _ResponseStub(HTTPStatus.OK, b"ok"),
        _ResponseStub(HTTPStatus.INTERNAL_SERVER_ERROR, b"fail")
    ])
    aspects = AspectsRest(
        session=session,
        completion_timeout=1,
        completion_interval=0,
        connection_timeout=0,
        inactivity_timeout=0,
        allowed_error_codes=(HTTPStatus.INTERNAL_SERVER_ERROR,)
    )
    client = RestClientBase(
        host="example",
        credential=_CredentialStub(),
        scheme="http"
    )
    resp = client._perform_call_while_success(
        leaf="/api",
        method="GET",
        params=None,
        body=None,
        exp_status=HTTPStatus.OK,
        headers=None,
        context_msg=None,
        aspects=aspects
    )
    testbase.assert_equal(resp.status_code, HTTPStatus.OK)
    return
