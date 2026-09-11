"""
    .. module:: test_restclientbase_wire
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Wire-level tests for :meth:`RestClientBase.perform_call`
        driven through the shared :class:`FakeSession`: what the client puts
        on the wire (method, path, query, body, headers, timeouts) and how it
        maps error statuses back to ``ccai.errors`` exceptions.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Union

from http import HTTPStatus

from requests import Response

from ccai import testbase

from ccai.errors.exceptions import (
    HttpForbiddenError,
    HttpNotFoundError,
    HttpUnprocessableContentError,
)

from ccai.restclient.base.aspectsrest import AspectsRest
from ccai.restclient.base.restclientbase import RestClientBase

from ccai.testshared.restclient.fakesession import FakeSession, assert_call


HOST = "api.example.test"


class _CredentialStub:
    def __init__(self, username: str = "user", password: str = "pass"):
        self.username = username
        self.password = password
        return


class _ReauthenticatingClient(RestClientBase):
    """
        Client whose ``authenticate`` installs a fresh :class:`FakeSession`
        and counts how often it was asked to do so.
    """

    def __init__(self, *args, **kwargs):
        self.auth_calls = 0
        self.replacement_session: Optional[FakeSession] = None
        super().__init__(*args, **kwargs)
        return

    def authenticate(self):
        self.auth_calls = self.auth_calls + 1
        self._session = self.replacement_session
        return


def _make_client(session: FakeSession) -> RestClientBase:
    """
        Builds a client whose session is the given :class:`FakeSession`,
        bypassing ``authenticate``.
    """
    client = RestClientBase(host=HOST, credential=_CredentialStub(), scheme="https")
    client._session = session
    return client


def _perform(client: RestClientBase, *, leaf: str, method: str = "GET",
             params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None,
             exp_status: Union[int, List[int]] = HTTPStatus.OK,
             headers: Optional[Dict[str, str]] = None, aspects: Optional[AspectsRest] = None) -> Response:
    """
        Calls ``perform_call`` with the keyword surface generated group
        methods use.
    """
    rtnval = client.perform_call(
        leaf=leaf,
        method=method,
        params=params,
        body=body,
        exp_status=exp_status,
        headers=headers,
        context_msg=None,
        aspects=aspects,
    )
    return rtnval


def test_perform_call_records_method_and_path():
    session = FakeSession([(200, {"id": 1}, {})])
    client = _make_client(session)

    _perform(client, leaf="/repos/octo/hello", method="GET")

    testbase.assert_equal(len(session.calls), 1)
    extracted = assert_call(
        session.last_call,
        method="GET",
        template="/repos/{owner}/{repo}",
        path_params={"owner": "octo", "repo": "hello"},
    )
    testbase.assert_equal(extracted, {"owner": "octo", "repo": "hello"})
    testbase.assert_equal(session.last_call.url, "https://api.example.test/repos/octo/hello")
    return


def test_perform_call_encodes_query_params_into_url():
    session = FakeSession([(200, [], {})])
    client = _make_client(session)

    _perform(client, leaf="/orgs/octo/repos", params={"per_page": 2, "page": 3})

    call = session.last_call
    testbase.assert_equal(call.params, {"per_page": 2, "page": 3})
    testbase.assert_equal(call.query, {"per_page": "2", "page": "3"})
    testbase.assert_equal(call.url, "https://api.example.test/orgs/octo/repos?per_page=2&page=3")
    return


def test_perform_call_sends_json_body():
    session = FakeSession([(201, {"id": 7, "name": "hello"}, {})])
    client = _make_client(session)
    body = {"name": "hello", "private": True}

    resp = _perform(client, leaf="/orgs/octo/repos", method="POST", body=body, exp_status=201)

    assert_call(session.last_call, method="POST", template="/orgs/{org}/repos", path_params={"org": "octo"}, body=body)
    testbase.assert_equal(resp.status_code, 201)
    return


def test_perform_call_passes_headers_and_timeouts():
    session = FakeSession([(200, {}, {})])
    client = _make_client(session)
    headers = {"Accept": "application/vnd.github+json"}
    aspects = AspectsRest(connection_timeout=3, inactivity_timeout=7)

    _perform(client, leaf="/rate_limit", headers=headers, aspects=aspects)

    call = session.last_call
    testbase.assert_equal(call.headers, headers)
    testbase.assert_equal(call.timeout, (3, 7))
    testbase.assert_equal(call.verify, True)
    return


def test_perform_call_returns_response_with_parsed_json():
    session = FakeSession([(200, {"id": 1, "name": "hello"}, {"X-Trace": "abc"})])
    client = _make_client(session)

    resp = _perform(client, leaf="/repos/octo/hello")

    testbase.assert_equal(resp.status_code, 200)
    testbase.assert_equal(resp.json(), {"id": 1, "name": "hello"})
    testbase.assert_equal(resp.headers["X-Trace"], "abc")
    return


def test_perform_call_accepts_any_listed_expected_status():
    session = FakeSession([(204, None, {})])
    client = _make_client(session)

    resp = _perform(client, leaf="/repos/octo/hello/topics", method="PUT", body={"names": []}, exp_status=[200, 204])

    testbase.assert_equal(resp.status_code, 204)
    testbase.assert_equal(resp.content, b"")
    return


def test_perform_call_prefers_aspects_session_over_client_session():
    client_session = FakeSession([])
    aspects_session = FakeSession([(200, {}, {})])
    client = _make_client(client_session)
    aspects = AspectsRest(session=aspects_session)

    _perform(client, leaf="/user", aspects=aspects)

    testbase.assert_equal(len(aspects_session.calls), 1)
    testbase.assert_equal(len(client_session.calls), 0)
    return


def test_perform_call_reauthenticates_once_after_forbidden_send():
    expired = FakeSession([HttpForbiddenError("token expired")])
    fresh = FakeSession([(200, {"ok": True}, {})])
    client = _ReauthenticatingClient(host=HOST, credential=_CredentialStub(), scheme="https")
    client._session = expired
    client.replacement_session = fresh

    resp = _perform(client, leaf="/user")

    testbase.assert_equal(client.auth_calls, 1)
    testbase.assert_equal(resp.json(), {"ok": True})
    testbase.assert_equal(len(expired.calls), 1)
    testbase.assert_equal(len(fresh.calls), 1)
    return


def test_perform_call_maps_404_to_not_found_with_body_in_message():
    session = FakeSession([(404, {"message": "Not Found", "documentation_url": "https://docs.example.test"}, {})])
    client = _make_client(session)

    error: Optional[BaseException] = None
    try:
        _perform(client, leaf="/repos/octo/missing")
    except HttpNotFoundError as nferr:
        error = nferr

    testbase.assert_equal(error is not None, True)
    message = str(error)
    testbase.assert_equal("code=404" in message, True)
    testbase.assert_equal("Not Found" in message, True)
    testbase.assert_equal("https://api.example.test/repos/octo/missing" in message, True)
    return


def test_perform_call_maps_422_to_unprocessable_content_with_validation_body():
    validation_body = {
        "message": "Validation Failed",
        "errors": [
            {"resource": "Repository", "code": "custom", "field": "name", "message": "name already exists on this account"}
        ],
    }
    session = FakeSession([(422, validation_body, {})])
    client = _make_client(session)

    error: Optional[BaseException] = None
    try:
        _perform(client, leaf="/orgs/octo/repos", method="POST", body={"name": "dup"}, exp_status=201)
    except HttpUnprocessableContentError as uperr:
        error = uperr

    testbase.assert_equal(error is not None, True)
    message = str(error)
    testbase.assert_equal("Validation Failed" in message, True)
    testbase.assert_equal("name already exists on this account" in message, True)
    return


def test_perform_call_maps_403_rate_limit_to_forbidden():
    rate_limit_body = {"message": "API rate limit exceeded for 203.0.113.7."}
    rate_limit_headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"}
    session = FakeSession([(403, rate_limit_body, rate_limit_headers)])
    client = _make_client(session)

    error: Optional[BaseException] = None
    try:
        _perform(client, leaf="/repos/octo/hello")
    except HttpForbiddenError as fberr:
        error = fberr

    testbase.assert_equal(error is not None, True)
    testbase.assert_equal("API rate limit exceeded" in str(error), True)
    return
