"""
    .. module:: test_pagedlist_paged
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for :class:`PagedList` link parsing over the ``Link``
        headers the shared ``paged`` builder emits, including a property
        check that walking the pages visits every item exactly once.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Any, List

from ccai import testbase

from ccai.testbase.properties import run_property
from ccai.testbase.properties import strategies as st

from ccai.restclient.base.pagedlist import PagedList

from ccai.testshared.restclient.fakesession import paged


def test_pagedlist_first_page_of_paged_has_next_first_and_last():
    responses = paged([1, 2, 3, 4, 5], 2)
    status, body, headers = responses[0]
    page = PagedList(body, headers)

    testbase.assert_equal(status, 200)
    testbase.assert_equal(page.items, [1, 2])
    testbase.assert_equal(page.has_next, True)
    testbase.assert_equal(page.has_prev, False)
    testbase.assert_equal(page.next_page, 2)
    testbase.assert_equal(page.first_page, 1)
    testbase.assert_equal(page.last_page, 3)
    return


def test_pagedlist_middle_page_of_paged_links_both_ways():
    responses = paged([1, 2, 3, 4, 5], 2)
    status, body, headers = responses[1]
    page = PagedList(body, headers)

    testbase.assert_equal(page.items, [3, 4])
    testbase.assert_equal(page.next_page, 3)
    testbase.assert_equal(page.prev_page, 1)
    return


def test_pagedlist_last_page_of_paged_has_no_next():
    responses = paged([1, 2, 3, 4, 5], 2)
    status, body, headers = responses[-1]
    page = PagedList(body, headers)

    testbase.assert_equal(page.items, [5])
    testbase.assert_equal(page.has_next, False)
    testbase.assert_equal(page.next_page, None)
    testbase.assert_equal(page.has_prev, True)
    testbase.assert_equal(page.prev_page, 2)
    return


def test_pagedlist_single_page_of_paged_has_no_links():
    responses = paged([1], 5)
    testbase.assert_equal(len(responses), 1)
    status, body, headers = responses[0]
    page = PagedList(body, headers)

    testbase.assert_equal(page.links, {})
    testbase.assert_equal(page.has_next, False)
    testbase.assert_equal(page.has_prev, False)
    return


def test_pagedlist_keeps_page_numbers_when_url_has_a_query_string():
    responses = paged([1, 2, 3], 1, url="https://api.example.test/things?per_page=1")
    status, body, headers = responses[0]
    page = PagedList(body, headers)

    testbase.assert_equal(page.next_page, 2)
    testbase.assert_equal(page.last_page, 3)
    testbase.assert_equal(page.links["next"].url, "https://api.example.test/things?per_page=1&page=2")
    return


def _check_walk_visits_every_item_once(count: int, page_size: int) -> None:
    """
        Walking ``paged(items, page_size)`` through :class:`PagedList`
        ``next_page`` links visits every item exactly once, in order, and
        the walk ends on a page with no next link.
    """
    items = list(range(count))
    responses = paged(items, page_size)

    expected_pages = max(1, (count + page_size - 1) // page_size)
    assert len(responses) == expected_pages, "page count {} != expected {}".format(len(responses), expected_pages)

    visited: List[Any] = []
    number = 1
    while True:
        status, body, headers = responses[number - 1]
        page = PagedList(body, headers)
        visited.extend(page.items)
        assert len(page) <= page_size
        if not page.has_next:
            assert number == expected_pages, "walk ended on page {} of {}".format(number, expected_pages)
            break
        assert page.next_page == number + 1, "next_page {} on page {}".format(page.next_page, number)
        number = page.next_page

    assert visited == items
    return


def test_pagedlist_walk_visits_every_item_exactly_once():
    examples = run_property(
        _check_walk_visits_every_item_once,
        max_examples=60,
        count=st.integers(min_value=0, max_value=40),
        page_size=st.integers(min_value=1, max_value=10),
    )
    testbase.assert_equal(examples, 60)
    return
