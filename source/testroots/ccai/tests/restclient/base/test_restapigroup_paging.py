"""
    .. module:: test_restapigroup_paging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the :class:`RestApiGroup` paging and upload helpers
        driven through the shared :class:`FakeSession` and its ``paged`` /
        ``paged_cursor`` builders.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional

import io

from ccai import testbase

from ccai.restclient.base.aspectsrest import AspectsRest
from ccai.restclient.base.restapigroup import RestApiGroup

from ccai.testshared.restclient.fakesession import FakeSession, paged, paged_cursor


ITEMS_URL = "https://api.example.test/things"


class _ClientStub:
    """
        Client stand-in exposing the ``_get_session`` hook the group helpers
        resolve their session through.
    """

    def __init__(self, session: FakeSession):
        self._session = session
        return

    def _get_session(self, aspects: AspectsRest) -> FakeSession:
        rtnval = self._session
        return rtnval


def _make_group(session: FakeSession) -> RestApiGroup:
    client = _ClientStub(session)
    group = RestApiGroup(client)
    # The group holds its client weakly; keep it alive on the group for the test.
    group._keepalive_client = client
    return group


def test_iter_pages_link_header_follows_next_until_exhausted():
    session = FakeSession(paged([1, 2, 3, 4, 5], 2, url=ITEMS_URL, items_field="items"))
    group = _make_group(session)
    aspects = AspectsRest(completion_timeout=9)

    found = list(group.iter_pages_link_header(initial_url=ITEMS_URL, items_field="items", aspects=aspects))

    testbase.assert_equal(found, [1, 2, 3, 4, 5])
    testbase.assert_equal(len(session.calls), 3)
    urls = [call.url for call in session.calls]
    testbase.assert_equal(urls, [ITEMS_URL, ITEMS_URL + "?page=2", ITEMS_URL + "?page=3"])
    session.assert_exhausted()
    return


def test_iter_pages_link_header_passes_completion_timeout_to_every_get():
    session = FakeSession(paged([1, 2, 3], 2, url=ITEMS_URL, items_field="items"))
    group = _make_group(session)
    aspects = AspectsRest(completion_timeout=11)

    list(group.iter_pages_link_header(initial_url=ITEMS_URL, items_field="items", aspects=aspects))

    timeouts = [call.timeout for call in session.calls]
    testbase.assert_equal(timeouts, [11, 11])
    methods = [call.method for call in session.calls]
    testbase.assert_equal(methods, ["GET", "GET"])
    return


def test_iter_pages_link_header_single_page_makes_one_call():
    session = FakeSession(paged(["only"], 10, url=ITEMS_URL, items_field="items"))
    group = _make_group(session)

    found = list(group.iter_pages_link_header(initial_url=ITEMS_URL, items_field="items", aspects=AspectsRest()))

    testbase.assert_equal(found, ["only"])
    testbase.assert_equal(len(session.calls), 1)
    return


def test_iter_pages_link_header_empty_page_yields_nothing():
    session = FakeSession(paged([], 10, url=ITEMS_URL, items_field="items"))
    group = _make_group(session)

    found = list(group.iter_pages_link_header(initial_url=ITEMS_URL, items_field="items", aspects=AspectsRest()))

    testbase.assert_equal(found, [])
    testbase.assert_equal(len(session.calls), 1)
    return


def test_iter_pages_link_header_missing_items_field_raises():
    session = FakeSession([(200, {"data": [1]}, {})])
    group = _make_group(session)

    with testbase.raises(ValueError):
        list(group.iter_pages_link_header(initial_url=ITEMS_URL, items_field="items", aspects=AspectsRest()))
    return


def test_iter_pages_cursor_follows_tokens_until_none():
    session = FakeSession(paged_cursor(["a", "b", "c", "d", "e"], 2))
    group = _make_group(session)

    def fetch_page(cursor: Optional[str]) -> Dict[str, Any]:
        params = None
        if cursor is not None:
            params = {"cursor": cursor}
        response = session.get(ITEMS_URL, params=params)
        rtnval = response.json()
        return rtnval

    found = list(group.iter_pages_cursor(fetch_page=fetch_page, aspects=AspectsRest()))

    testbase.assert_equal(found, ["a", "b", "c", "d", "e"])
    cursors = [call.params.get("cursor") for call in session.calls]
    testbase.assert_equal(cursors, [None, "cursor-2", "cursor-3"])
    session.assert_exhausted()
    return


def test_iter_pages_offset_stops_on_short_page():
    session = FakeSession([
        (200, {"items": [1, 2]}, {}),
        (200, {"items": [3]}, {}),
    ])
    group = _make_group(session)

    def fetch_page(offset: int, page_size: int) -> Dict[str, Any]:
        response = session.get(ITEMS_URL, params={"offset": offset, "limit": page_size})
        rtnval = response.json()
        return rtnval

    found = list(group.iter_pages_offset(fetch_page=fetch_page, page_size=2, aspects=AspectsRest()))

    testbase.assert_equal(found, [1, 2, 3])
    offsets = [call.params["offset"] for call in session.calls]
    testbase.assert_equal(offsets, [0, 2])
    return


def test_post_multipart_streams_fields_and_files_with_completion_timeout():
    session = FakeSession([(201, {"id": "upload-1"}, {})])
    group = _make_group(session)
    aspects = AspectsRest(completion_timeout=42)
    fields = {"name": "artifact"}
    files = {"file": io.BytesIO(b"payload")}

    response = group.post_multipart(url=ITEMS_URL + "/upload", fields=fields, files=files, aspects=aspects)

    testbase.assert_equal(response.status_code, 201)
    call = session.last_call
    testbase.assert_equal(call.method, "POST")
    testbase.assert_equal(call.url, ITEMS_URL + "/upload")
    testbase.assert_equal(call.body, fields)
    testbase.assert_equal(call.extra["files"] is files, True)
    testbase.assert_equal(call.extra["stream"], True)
    testbase.assert_equal(call.timeout, 42)
    return
