"""
    .. module:: fakesession
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A canned-response stand-in for :class:`requests.Session` that
        records every call a REST client makes, builders for paged responses
        in the shapes :class:`PagedList` and the :class:`RestApiGroup` paging
        helpers expect, and an assertion helper that reads a recorded call back
        against the path template the client generator emitted.

    This module is test-tree code shared by the REST client packages.  The
    repositories do not share test code, so each client package carries its
    own copy; keep the copies identical.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple

import json
import os
import re

from dataclasses import dataclass, field
from http import HTTPStatus
from urllib.parse import parse_qsl, urlsplit

from requests import PreparedRequest, Request, Response
from requests.structures import CaseInsensitiveDict


# A canned response is ``(status, json, headers)``.  ``json`` is serialised
# with :mod:`json` unless it is ``None`` (empty body), ``str`` or ``bytes``.
CannedResponse = Tuple[int, Any, Dict[str, str]]

DEFAULT_PAGED_URL = "https://api.example.test/items"

PATH_PARAMETER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_\-]*)\}")


@dataclass
class RecordedCall:
    """
        One request that product code handed to a :class:`FakeSession`.

        ``params`` is the query dictionary the product passed (empty when it
        passed ``None``); ``query`` is the query string parsed back out of the
        final URL, so both the dictionary the client built and the wire form
        can be asserted.
    """
    method: str
    url: str
    path: str
    query: Dict[str, str]
    params: Dict[str, Any]
    headers: Dict[str, str]
    body: Any
    timeout: Any = None
    verify: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)


class FakeSession:
    """
        Stand-in for :class:`requests.Session` that returns canned responses
        in order and records every call.

        It implements the two surfaces the REST client base uses:

        * ``prepare_request`` / ``send`` (:meth:`RestClientBase.perform_call`)
        * ``request`` and the ``get`` / ``post`` / ``put`` / ``patch`` /
          ``delete`` verbs (:class:`TaskHandle` polling and the
          :class:`RestApiGroup` paging helpers)

        Install it on a client with ``client._session = FakeSession(...)`` or
        pass it as ``AspectsRest(session=...)``.

        Each entry of ``responses`` is a ``(status, json, headers)`` tuple, a
        ``(status, json)`` tuple, a ready :class:`requests.Response`, or an
        exception instance that is raised instead of returning a response.
        Running out of responses raises :class:`AssertionError` naming the
        call that had nothing to answer it.
    """

    def __init__(self, responses: Optional[Sequence[Any]] = None):
        """
            Creates a session with an ordered list of canned responses.

            :param responses: The responses to hand out, in call order.
        """
        self.calls: List[RecordedCall] = []
        self.headers: Dict[str, str] = {}
        self.verify: bool = True
        self._responses: List[Any] = []
        if responses is not None:
            self._responses = list(responses)
        return

    @property
    def remaining(self) -> int:
        """
            The number of canned responses not yet consumed.
        """
        rtnval = len(self._responses)
        return rtnval

    @property
    def last_call(self) -> RecordedCall:
        """
            The most recently recorded call.

            :raises: AssertionError when no call has been recorded.
        """
        if len(self.calls) == 0:
            raise AssertionError("FakeSession.last_call: no call has been recorded yet.")
        rtnval = self.calls[-1]
        return rtnval

    def add_response(self, status: int, payload: Any = None, headers: Optional[Dict[str, str]] = None) -> None:
        """
            Appends a canned response to the queue.

            :param status: The HTTP status code.
            :param payload: The JSON-serialisable body, ``None`` for an empty body.
            :param headers: Optional response headers.
        """
        if headers is None:
            headers = {}
        self._responses.append((status, payload, headers))
        return

    def assert_exhausted(self) -> None:
        """
            Asserts that every canned response was consumed.

            :raises: AssertionError
        """
        if len(self._responses) > 0:
            errmsg = "FakeSession still holds {} unconsumed canned response(s).".format(len(self._responses))
            raise AssertionError(errmsg)
        return

    # ------------------------------------------------------------------
    # requests.Session surface used by RestClientBase.perform_call
    # ------------------------------------------------------------------

    def prepare_request(self, request: Request) -> PreparedRequest:
        """
            Records the request and prepares it exactly as
            :class:`requests.Session` would (query string encoded into the
            URL, JSON body serialised).

            :param request: The :class:`requests.Request` built by the client.

            :returns: The prepared request to pass to :meth:`send`.
        """
        prepared = request.prepare()
        self._record(request.method, prepared.url, request.params, request.headers, request.json)
        return prepared

    def send(self, request: PreparedRequest, **kwargs) -> Response:
        """
            Answers a prepared request with the next canned response.

            :param request: The prepared request from :meth:`prepare_request`.

            :returns: The canned :class:`requests.Response`.
        """
        call = self.last_call
        call.timeout = kwargs.get("timeout")
        call.verify = kwargs.get("verify")
        rtnval = self._next_response(request.method, request.url)
        return rtnval

    # ------------------------------------------------------------------
    # requests.Session verb surface used by TaskHandle and RestApiGroup
    # ------------------------------------------------------------------

    def request(self, method: str, url: str, *, params: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None, json: Any = None, data: Any = None,
                timeout: Any = None, verify: Any = None, **kwargs) -> Response:
        """
            Records a verb-style call and answers it with the next canned
            response.

            :param method: The HTTP method.
            :param url: The request URL.
            :param params: Optional query parameters.
            :param headers: Optional request headers.
            :param json: Optional JSON body.
            :param data: Optional form body, recorded as the body when ``json`` is ``None``.
            :param timeout: The timeout the product passed.
            :param verify: The verify flag the product passed.

            :returns: The canned :class:`requests.Response`.
        """
        body = json
        if body is None:
            body = data

        url_builder = PreparedRequest()
        url_builder.prepare_url(url, params)
        full_url = url_builder.url

        call = self._record(method, full_url, params, headers, body)
        call.timeout = timeout
        call.verify = verify
        call.extra = dict(kwargs)

        rtnval = self._next_response(method, full_url)
        return rtnval

    def get(self, url: str, **kwargs) -> Response:
        rtnval = self.request("GET", url, **kwargs)
        return rtnval

    def post(self, url: str, **kwargs) -> Response:
        rtnval = self.request("POST", url, **kwargs)
        return rtnval

    def put(self, url: str, **kwargs) -> Response:
        rtnval = self.request("PUT", url, **kwargs)
        return rtnval

    def patch(self, url: str, **kwargs) -> Response:
        rtnval = self.request("PATCH", url, **kwargs)
        return rtnval

    def delete(self, url: str, **kwargs) -> Response:
        rtnval = self.request("DELETE", url, **kwargs)
        return rtnval

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _record(self, method: str, url: str, params: Optional[Dict[str, Any]],
                headers: Optional[Dict[str, str]], body: Any) -> RecordedCall:
        """
            Appends a :class:`RecordedCall` for the given request data.

            :returns: The recorded call.
        """
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))

        recorded_params: Dict[str, Any] = {}
        if params is not None:
            recorded_params = dict(params)

        recorded_headers: Dict[str, str] = {}
        if headers is not None:
            recorded_headers = dict(headers)

        call = RecordedCall(
            method=method.upper(),
            url=url,
            path=parts.path,
            query=query,
            params=recorded_params,
            headers=recorded_headers,
            body=body,
        )
        self.calls.append(call)
        return call

    def _next_response(self, method: str, url: str) -> Response:
        """
            Pops the next canned response, raising it when it is an exception.

            :returns: A :class:`requests.Response`.
            :raises: AssertionError when the queue is empty.
        """
        if len(self._responses) == 0:
            errmsg_lines = [
                "FakeSession has no canned response left for {} {}.".format(method.upper(), url),
                "CALLS SO FAR: ({})".format(len(self.calls)),
            ]
            for call in self.calls:
                errmsg_lines.append("    {} {}".format(call.method, call.url))
            errmsg = os.linesep.join(errmsg_lines)
            raise AssertionError(errmsg)

        item = self._responses.pop(0)

        if isinstance(item, BaseException):
            raise item

        if isinstance(item, Response):
            return item

        if len(item) == 2:
            status, payload = item
            headers = None
        else:
            status, payload, headers = item

        rtnval = build_response(status, payload, headers=headers, url=url)
        return rtnval


def build_response(status: int, payload: Any = None, headers: Optional[Dict[str, str]] = None,
                   url: Optional[str] = None) -> Response:
    """
        Builds a real :class:`requests.Response` carrying a canned body, so
        product code sees ``status_code``, ``content``, ``headers`` and
        ``json()`` exactly as it would from the wire.

        :param status: The HTTP status code.
        :param payload: ``None`` for an empty body, ``str`` or ``bytes`` verbatim,
                        anything else serialised as JSON.
        :param headers: Optional response headers.
        :param url: The URL to stamp on the response.

        :returns: The response.
    """
    response = Response()
    response.status_code = int(status)

    reason = ""
    try:
        reason = HTTPStatus(int(status)).phrase
    except ValueError:
        reason = ""
    response.reason = reason

    response_headers: CaseInsensitiveDict = CaseInsensitiveDict()
    if headers is not None:
        response_headers.update(headers)

    content = b""
    if payload is not None:
        if isinstance(payload, (bytes, bytearray)):
            content = bytes(payload)
        elif isinstance(payload, str):
            content = payload.encode("utf-8")
        else:
            content = json.dumps(payload).encode("utf-8")
            if "Content-Type" not in response_headers:
                response_headers["Content-Type"] = "application/json"

    response._content = content
    response.headers = response_headers
    response.encoding = "utf-8"
    response.url = url
    return response


def paged(items: Sequence[Any], page_size: int, *, url: str = DEFAULT_PAGED_URL,
          items_field: Optional[str] = None, page_param: str = "page") -> List[CannedResponse]:
    """
        Splits ``items`` into pages and builds one canned ``200`` response per
        page with a ``Link`` header in the form :class:`PagedList` parses::

            <url?page=2>; rel="next", <url?page=1>; rel="first", <url?page=3>; rel="last"

        The last page carries no ``rel="next"``; a single page carries no
        ``Link`` header at all.  With ``items_field`` set the body is
        ``{items_field: [...]}`` (the shape ``iter_pages_link_header`` reads),
        otherwise the body is the bare list (the shape generated list
        operations read).

        :param items: The complete item sequence.
        :param page_size: Items per page, greater than zero.
        :param url: The URL the links point at; an existing query string is kept.
        :param items_field: Optional key to wrap each page's items under.
        :param page_param: The query parameter name carrying the page number.

        :returns: The canned responses, one per page, in page order.
        :raises: ValueError
    """
    if page_size <= 0:
        raise ValueError("paged() requires page_size > 0.")

    pages: List[List[Any]] = []
    position = 0
    while position < len(items):
        pages.append(list(items[position:position + page_size]))
        position = position + page_size
    if len(pages) == 0:
        pages.append([])

    last_number = len(pages)

    separator = "?"
    if "?" in url:
        separator = "&"

    responses: List[CannedResponse] = []
    for number, page_items in enumerate(pages, start=1):
        links: List[str] = []
        if number < last_number:
            links.append('<{}{}{}={}>; rel="next"'.format(url, separator, page_param, number + 1))
        if number > 1:
            links.append('<{}{}{}={}>; rel="prev"'.format(url, separator, page_param, number - 1))
        if last_number > 1:
            links.append('<{}{}{}={}>; rel="first"'.format(url, separator, page_param, 1))
            links.append('<{}{}{}={}>; rel="last"'.format(url, separator, page_param, last_number))

        headers: Dict[str, str] = {}
        if len(links) > 0:
            headers["Link"] = ", ".join(links)

        payload: Any = page_items
        if items_field is not None:
            payload = {items_field: page_items}

        responses.append((200, payload, headers))

    return responses


def paged_cursor(items: Sequence[Any], page_size: int, *, items_field: str = "items",
                 cursor_field: str = "next", cursor_prefix: str = "cursor-") -> List[CannedResponse]:
    """
        Splits ``items`` into pages and builds one canned ``200`` response per
        page carrying a page token, the shape ``iter_pages_cursor`` reads::

            {"items": [...], "next": "cursor-2"}

        The last page carries ``None`` as its token.

        :param items: The complete item sequence.
        :param page_size: Items per page, greater than zero.
        :param items_field: The key holding each page's items.
        :param cursor_field: The key holding the next-page token.
        :param cursor_prefix: Prefix for the generated tokens.

        :returns: The canned responses, one per page, in page order.
        :raises: ValueError
    """
    if page_size <= 0:
        raise ValueError("paged_cursor() requires page_size > 0.")

    pages: List[List[Any]] = []
    position = 0
    while position < len(items):
        pages.append(list(items[position:position + page_size]))
        position = position + page_size
    if len(pages) == 0:
        pages.append([])

    last_number = len(pages)

    responses: List[CannedResponse] = []
    for number, page_items in enumerate(pages, start=1):
        token: Optional[str] = None
        if number < last_number:
            token = "{}{}".format(cursor_prefix, number + 1)
        payload = {items_field: page_items, cursor_field: token}
        responses.append((200, payload, {}))

    return responses


def template_to_pattern(template: str) -> Pattern[str]:
    """
        Compiles a generator path template such as ``/repos/{owner}/{repo}``
        into a regular expression with one named group per path parameter.

        :param template: The template as it appears in the generated group module.

        :returns: The compiled pattern, anchored at both ends.
    """
    pattern_text = "^"
    position = 0
    for match in PATH_PARAMETER_PATTERN.finditer(template):
        pattern_text = pattern_text + re.escape(template[position:match.start()])
        group_name = match.group(1).replace("-", "_")
        pattern_text = pattern_text + "(?P<{}>[^/]+)".format(group_name)
        position = match.end()
    pattern_text = pattern_text + re.escape(template[position:]) + "$"

    rtnval = re.compile(pattern_text)
    return rtnval


def assert_call(call: RecordedCall, *, method: str, template: str,
                path_params: Optional[Dict[str, Any]] = None,
                params: Optional[Dict[str, Any]] = None,
                body: Any = None) -> Dict[str, str]:
    """
        Asserts that a recorded call hit ``method`` on a path matching the
        generator's ``template``, so a test reads as "calling
        ``repos.get(owner, repo)`` hits ``GET /repos/{owner}/{repo}``".

        :param call: The recorded call to check.
        :param method: The expected HTTP method.
        :param template: The path template from the generated group module.
        :param path_params: Optional expected path parameter values; each is
                            compared as a string against the matched segment.
        :param params: Optional expected query dictionary, compared to the
                       dictionary the product passed.
        :param body: Optional expected JSON body.

        :returns: The path parameter values extracted from the recorded path.
        :raises: AssertionError
    """
    problems: List[str] = []

    if call.method != method.upper():
        problems.append("METHOD: expected {} but recorded {}".format(method.upper(), call.method))

    pattern = template_to_pattern(template)
    match = pattern.match(call.path)
    extracted: Dict[str, str] = {}
    if match is None:
        problems.append("PATH: '{}' does not match template '{}'".format(call.path, template))
    else:
        extracted = dict(match.groupdict())

    if path_params is not None and match is not None:
        for name, expected in path_params.items():
            found = extracted.get(name.replace("-", "_"))
            if found != str(expected):
                problems.append("PATH PARAM '{}': expected {!r} but recorded {!r}".format(name, str(expected), found))

    if params is not None:
        if call.params != params:
            problems.append("PARAMS: expected {!r} but recorded {!r}".format(params, call.params))

    if body is not None:
        if call.body != body:
            problems.append("BODY: expected {!r} but recorded {!r}".format(body, call.body))

    if len(problems) > 0:
        errmsg_lines = [
            "Recorded call did not match the expected operation.",
            "EXPECTED: {} {}".format(method.upper(), template),
            "RECORDED: {} {}".format(call.method, call.url),
        ]
        for problem in problems:
            errmsg_lines.append("    {}".format(problem))
        errmsg = os.linesep.join(errmsg_lines)
        raise AssertionError(errmsg)

    return extracted
