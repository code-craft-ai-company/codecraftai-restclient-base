import testbase

from automojo.restclient.base.itemsresult import ItemsResult, Paging, PreCannedRequest


class _ResponseStub:
    pass


def test_precannedrequest_perform_call_packages_response():
    calls = {"perform": 0, "package": 0}

    def perform_call(**kwargs):
        calls["perform"] += 1
        return _ResponseStub()

    def package_result(resp):
        calls["package"] += 1
        testbase.assert_equal(isinstance(resp, _ResponseStub), True)
        return ItemsResult(["alpha"])

    request = PreCannedRequest(
        leaf="/items",
        method="GET",
        params=None,
        body=None,
        exp_status=200,
        aspects=None,
        perform_call=perform_call,
        package_result=package_result,
    )
    result = request.perform_call()

    testbase.assert_equal(calls["perform"], 1)
    testbase.assert_equal(calls["package"], 1)
    testbase.assert_equal(isinstance(result, ItemsResult), True)
    testbase.assert_equal(result.items, ["alpha"])
    return


def test_paging_properties_expose_values():
    paging = Paging(
        page=2,
        count=5,
        total_count=15,
        per_page=5,
        first_page=1,
        last_page=3,
    )

    testbase.assert_equal(paging.page, 2)
    testbase.assert_equal(paging.count, 5)
    testbase.assert_equal(paging.total_count, 15)
    testbase.assert_equal(paging.per_page, 5)
    testbase.assert_equal(paging.first_page, 1)
    testbase.assert_equal(paging.last_page, 3)
    testbase.assert_equal(paging.request_next, None)
    testbase.assert_equal(paging.request_prev, None)
    return


def test_itemsresult_is_paged_and_items():
    result = ItemsResult(["alpha", "beta"])
    testbase.assert_equal(result.is_paged, False)
    testbase.assert_equal(result.items, ["alpha", "beta"])

    paging = Paging(
        page=1,
        count=2,
        total_count=4,
        per_page=2,
        first_page=1,
        last_page=2,
    )
    paged_result = ItemsResult(["alpha", "beta"], paging=paging)
    testbase.assert_equal(paged_result.is_paged, True)
    testbase.assert_equal(paged_result.paging is paging, True)
    return


def test_itemsresult_next_prev_page_result():
    next_called = {"count": 0}
    prev_called = {"count": 0}

    def perform_next(**kwargs):
        next_called["count"] += 1
        return _ResponseStub()

    def perform_prev(**kwargs):
        prev_called["count"] += 1
        return _ResponseStub()

    def package_result(resp):
        return ItemsResult(["next"]) if next_called["count"] else ItemsResult(["prev"])

    request_next = PreCannedRequest(
        leaf="/items?page=2",
        method="GET",
        params=None,
        body=None,
        exp_status=200,
        aspects=None,
        perform_call=perform_next,
        package_result=package_result,
    )
    request_prev = PreCannedRequest(
        leaf="/items?page=0",
        method="GET",
        params=None,
        body=None,
        exp_status=200,
        aspects=None,
        perform_call=perform_prev,
        package_result=package_result,
    )
    paging = Paging(
        page=1,
        count=1,
        total_count=2,
        per_page=1,
        first_page=1,
        last_page=2,
        request_next=request_next,
        request_prev=request_prev,
    )

    result = ItemsResult(["current"], paging=paging)

    next_result = result.next_page_result()
    prev_result = result.prev_page_result()

    testbase.assert_equal(next_called["count"], 1)
    testbase.assert_equal(prev_called["count"], 1)
    testbase.assert_equal(next_result.items, ["next"])
    testbase.assert_equal(prev_result.items, ["prev"])
    return


def test_itemsresult_next_prev_none_when_unpaged():
    result = ItemsResult(["alpha"])
    testbase.assert_equal(result.next_page_result(), None)
    testbase.assert_equal(result.prev_page_result(), None)
    return
