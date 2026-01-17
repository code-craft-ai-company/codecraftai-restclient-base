import testbase

from automojo.restclient.base.pagedlist import LinkInfo, PagedList


def test_pagedlist_sequence_behavior():
    items = ["alpha", "beta", "gamma"]
    paged = PagedList(items, headers={})

    testbase.assert_equal(paged.items, items)
    testbase.assert_equal(len(paged), 3)
    testbase.assert_equal(paged[1], "beta")
    testbase.assert_equal(list(iter(paged)), items)
    return


def test_pagedlist_parses_link_header_with_pages():
    header = (
        '<https://example/api?page=2>; rel="next", '
        '<https://example/api?page=0>; rel="prev", '
        '<https://example/api?page=1>; rel="first", '
        '<https://example/api?page=5>; rel="last"'
    )
    paged = PagedList([], headers={"Link": header})
    links = paged.links

    testbase.assert_equal(isinstance(links.get("next"), LinkInfo), True)
    testbase.assert_equal(links["next"].page, 2)
    testbase.assert_equal(links["prev"].page, 0)
    testbase.assert_equal(links["first"].page, 1)
    testbase.assert_equal(links["last"].page, 5)
    testbase.assert_equal(paged.has_next, True)
    testbase.assert_equal(paged.has_prev, True)
    testbase.assert_equal(paged.next_page, 2)
    testbase.assert_equal(paged.prev_page, 0)
    testbase.assert_equal(paged.first_page, 1)
    testbase.assert_equal(paged.last_page, 5)
    return


def test_pagedlist_parses_lowercase_link_header():
    header = '<https://example/api?page=3>; rel="next"'
    paged = PagedList([], headers={"link": header})
    testbase.assert_equal(paged.has_next, True)
    testbase.assert_equal(paged.next_page, 3)
    return


def test_pagedlist_no_link_header_returns_empty():
    paged = PagedList([], headers={})
    testbase.assert_equal(paged.links, {})
    testbase.assert_equal(paged.has_next, False)
    testbase.assert_equal(paged.has_prev, False)
    return


def test_pagedlist_link_without_page_sets_none():
    header = '<https://example/api?limit=20>; rel="next"'
    paged = PagedList([], headers={"Link": header})
    testbase.assert_equal(paged.has_next, True)
    testbase.assert_equal(paged.next_page, None)
    return
