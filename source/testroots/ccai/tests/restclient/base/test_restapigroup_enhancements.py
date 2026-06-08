"""
    .. module:: test_restapigroup_enhancements
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit tests covering the additive helpers on
        :class:`RestApiGroup` (build_leaf, negotiate_content_type,
        post_multipart, iter_pages_*).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


import io
import unittest

from typing import List, Optional, Tuple

from unittest.mock import MagicMock

from ccai.errors.exceptions import SemanticError

from ccai.restclient.base.aspectsrest import AspectsRest
from ccai.restclient.base.restapigroup import RestApiGroup, _parse_next_link


class _ClientStub:
    """
        Minimal stand-in for :class:`RestClientBase` carrying just the
        attributes used by :class:`RestApiGroup`.
    """

    def __init__(self, session: object = None) -> None:
        self._session = session
        return


class _GroupNoBase(RestApiGroup):
    BASE_LEAF = ""


class _GroupSimpleBase(RestApiGroup):
    BASE_LEAF = "/vcenter/vm"


class _GroupTrailingSlashBase(RestApiGroup):
    BASE_LEAF = "/vcenter/vm/"


class TestBuildLeaf(unittest.TestCase):

    def test_build_leaf_simple_join(self) -> None:
        client = _ClientStub()
        group = _GroupSimpleBase(client)
        result = group.build_leaf(parts=["vm-42"])
        self.assertEqual(result, "/vcenter/vm/vm-42")
        return

    def test_build_leaf_multi_part(self) -> None:
        client = _ClientStub()
        group = _GroupSimpleBase(client)
        result = group.build_leaf(parts=["vm-42", "power"])
        self.assertEqual(result, "/vcenter/vm/vm-42/power")
        return

    def test_build_leaf_collapses_double_slash(self) -> None:
        client = _ClientStub()
        group = _GroupSimpleBase(client)
        result = group.build_leaf(parts=["/vm-42/", "/power"])
        self.assertEqual(result, "/vcenter/vm/vm-42/power")
        return

    def test_build_leaf_trailing_slash_base(self) -> None:
        client = _ClientStub()
        group = _GroupTrailingSlashBase(client)
        result = group.build_leaf(parts=["vm-42", "power"])
        self.assertEqual(result, "/vcenter/vm/vm-42/power")
        return

    def test_build_leaf_empty_base_acts_as_path_joiner(self) -> None:
        client = _ClientStub()
        group = _GroupNoBase(client)
        result = group.build_leaf(parts=["a", "b", "c"])
        self.assertEqual(result, "a/b/c")
        return

    def test_build_leaf_empty_part_raises(self) -> None:
        client = _ClientStub()
        group = _GroupSimpleBase(client)
        with self.assertRaises(SemanticError):
            group.build_leaf(parts=["vm-42", ""])
        return

    def test_build_leaf_preserves_slashes_in_parts(self) -> None:
        client = _ClientStub()
        group = _GroupSimpleBase(client)
        result = group.build_leaf(parts=["vm-42/snapshots", "current"])
        self.assertEqual(result, "/vcenter/vm/vm-42/snapshots/current")
        return


class TestNegotiateContentType(unittest.TestCase):

    def test_defaults(self) -> None:
        group = _GroupNoBase(_ClientStub())
        result = group.negotiate_content_type()
        self.assertEqual(
            result, {"Content-Type": "application/json", "Accept": "application/json"}
        )
        return

    def test_overrides(self) -> None:
        group = _GroupNoBase(_ClientStub())
        result = group.negotiate_content_type(
            request="multipart/form-data", accept="application/xml"
        )
        self.assertEqual(
            result,
            {"Content-Type": "multipart/form-data", "Accept": "application/xml"},
        )
        return


class TestPostMultipart(unittest.TestCase):

    def test_uses_aspect_timeout_and_streams(self) -> None:
        session = MagicMock()
        session.post.return_value = MagicMock()

        client = _ClientStub(session=session)
        group = _GroupSimpleBase(client)

        aspects = AspectsRest(completion_timeout=42)
        fields = {"spec": "abc"}
        stream = io.BytesIO(b"payload-bytes")
        files = {"ovf": stream}

        group.post_multipart(
            url="https://host/upload",
            fields=fields,
            files=files,
            aspects=aspects,
        )

        session.post.assert_called_once()
        kwargs = session.post.call_args.kwargs
        self.assertEqual(kwargs["url"], "https://host/upload")
        self.assertEqual(kwargs["data"], fields)
        self.assertEqual(kwargs["files"], files)
        self.assertEqual(kwargs["timeout"], 42)
        self.assertEqual(kwargs["stream"], True)
        return


class TestIterPagesCursor(unittest.TestCase):

    def test_yields_all_items_in_order(self) -> None:
        pages = [
            {"items": [1, 2, 3], "next": "c1"},
            {"items": [4, 5], "next": "c2"},
            {"items": [6], "next": None},
        ]
        calls: List[Optional[str]] = []

        def fetch_page(cursor: Optional[str]) -> dict:
            calls.append(cursor)
            page = pages[len(calls) - 1]
            return page

        group = _GroupNoBase(_ClientStub())
        aspects = AspectsRest()

        gathered = list(
            group.iter_pages_cursor(fetch_page=fetch_page, aspects=aspects)
        )

        self.assertEqual(gathered, [1, 2, 3, 4, 5, 6])
        self.assertEqual(calls, [None, "c1", "c2"])
        return

    def test_missing_items_field_raises(self) -> None:
        def fetch_page(cursor: Optional[str]) -> dict:
            page = {"things": [], "next": None}
            return page

        group = _GroupNoBase(_ClientStub())
        aspects = AspectsRest()

        with self.assertRaises(ValueError):
            list(group.iter_pages_cursor(fetch_page=fetch_page, aspects=aspects))
        return


class TestIterPagesOffset(unittest.TestCase):

    def test_terminates_on_short_page(self) -> None:
        pages = {
            (0, 3): {"items": [1, 2, 3]},
            (3, 3): {"items": [4, 5]},
        }
        calls: List[Tuple[int, int]] = []

        def fetch_page(offset: int, page_size: int) -> dict:
            calls.append((offset, page_size))
            page = pages[(offset, page_size)]
            return page

        group = _GroupNoBase(_ClientStub())
        aspects = AspectsRest()

        gathered = list(
            group.iter_pages_offset(
                fetch_page=fetch_page, page_size=3, aspects=aspects
            )
        )

        self.assertEqual(gathered, [1, 2, 3, 4, 5])
        self.assertEqual(calls, [(0, 3), (3, 3)])
        return

    def test_missing_items_field_raises(self) -> None:
        def fetch_page(offset: int, page_size: int) -> dict:
            page = {"records": []}
            return page

        group = _GroupNoBase(_ClientStub())
        aspects = AspectsRest()

        with self.assertRaises(ValueError):
            list(
                group.iter_pages_offset(
                    fetch_page=fetch_page, page_size=3, aspects=aspects
                )
            )
        return

    def test_non_positive_page_size_raises(self) -> None:
        def fetch_page(offset: int, page_size: int) -> dict:
            page = {"items": []}
            return page

        group = _GroupNoBase(_ClientStub())
        aspects = AspectsRest()

        with self.assertRaises(SemanticError):
            list(
                group.iter_pages_offset(
                    fetch_page=fetch_page, page_size=0, aspects=aspects
                )
            )
        return


class TestIterPagesLinkHeader(unittest.TestCase):

    def test_walks_chain(self) -> None:
        first_response = MagicMock()
        first_response.json.return_value = {"items": [1, 2]}
        first_response.headers = {
            "Link": '<https://host/p2>; rel="next", <https://host/last>; rel="last"'
        }

        second_response = MagicMock()
        second_response.json.return_value = {"items": [3]}
        second_response.headers = {"Link": ""}

        session = MagicMock()
        session.get.side_effect = [first_response, second_response]

        client = _ClientStub(session=session)
        group = _GroupNoBase(client)
        aspects = AspectsRest(completion_timeout=11)

        gathered = list(
            group.iter_pages_link_header(
                initial_url="https://host/p1", aspects=aspects
            )
        )

        self.assertEqual(gathered, [1, 2, 3])
        self.assertEqual(session.get.call_count, 2)
        first_call_kwargs = session.get.call_args_list[0].kwargs
        self.assertEqual(first_call_kwargs["url"], "https://host/p1")
        self.assertEqual(first_call_kwargs["timeout"], 11)
        second_call_kwargs = session.get.call_args_list[1].kwargs
        self.assertEqual(second_call_kwargs["url"], "https://host/p2")
        return

    def test_terminates_when_header_absent(self) -> None:
        response = MagicMock()
        response.json.return_value = {"items": [9]}
        response.headers = {}

        session = MagicMock()
        session.get.return_value = response

        client = _ClientStub(session=session)
        group = _GroupNoBase(client)
        aspects = AspectsRest()

        gathered = list(
            group.iter_pages_link_header(
                initial_url="https://host/only", aspects=aspects
            )
        )

        self.assertEqual(gathered, [9])
        self.assertEqual(session.get.call_count, 1)
        return

    def test_missing_items_field_raises(self) -> None:
        response = MagicMock()
        response.json.return_value = {"things": []}
        response.headers = {}

        session = MagicMock()
        session.get.return_value = response

        client = _ClientStub(session=session)
        group = _GroupNoBase(client)
        aspects = AspectsRest()

        with self.assertRaises(ValueError):
            list(
                group.iter_pages_link_header(
                    initial_url="https://host/only", aspects=aspects
                )
            )
        return


class TestParseNextLink(unittest.TestCase):

    def test_empty_header(self) -> None:
        self.assertIsNone(_parse_next_link(link_header=""))
        return

    def test_extracts_next(self) -> None:
        header = '<https://host/p2>; rel="next", <https://host/last>; rel="last"'
        self.assertEqual(_parse_next_link(link_header=header), "https://host/p2")
        return

    def test_no_next_relation(self) -> None:
        header = '<https://host/last>; rel="last"'
        self.assertIsNone(_parse_next_link(link_header=header))
        return


class TestBackwardCompatibility(unittest.TestCase):

    def test_existing_apigroup_subclasses_still_construct(self) -> None:
        client = _ClientStub()
        group = RestApiGroup(client)
        self.assertIs(group.client, client)
        return

    def test_default_base_leaf_is_empty_string(self) -> None:
        self.assertEqual(RestApiGroup.BASE_LEAF, "")
        return


if __name__ == "__main__":
    unittest.main()
