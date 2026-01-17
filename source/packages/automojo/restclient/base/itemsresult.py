"""
    .. module:: itemsresult
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: itemsresult module.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from requests import Response

from automojo.restclient.base.aspectsrest import AspectsRest


CT = TypeVar("CT")


class PreCannedRequest(Generic[CT]):
    """
        Container for REST call details used to generate an :class:`ItemsResult` later.
    """

    def __init__(
        self,
        *,
        leaf: str,
        method: str,
        params: Union[Dict[str, str], None],
        body: Union[Dict[str, Any], None],
        exp_status: Union[int, List[int]],
        aspects: Union[AspectsRest, None],
        perform_call: Callable,
        package_result: Callable
    ):
        """
            Stores call details for later execution.

            :param leaf: API leaf path.
            :param method: HTTP method name.
            :param params: Query parameters for the call.
            :param body: Body payload for the call.
            :param exp_status: Expected HTTP status codes.
            :param aspects: Optional call aspects.
            :param perform_call: Callable used to perform the call.
            :param package_result: Callable used to package the response.

            :returns: None
        """

        self._leaf = leaf
        self._method = method
        self._params = params
        self._body = body
        self._exp_status = exp_status
        self._aspects = aspects
        self._perform_call = perform_call
        self._package_result = package_result
        return

    def perform_call(self) -> "ItemsResult[CT]":
        """
            Perform the pre-canned REST call stored on this instance and
            package the result into an :class:`ItemsResult` object.

            :returns: The result object created from the REST call.
        """

        resp: Response = self._perform_call(
            leaf=self.leaf,
            method=self._method,
            params=self._params,
            body=self._body,
            exp_status=self._exp_status,
            aspects=self._aspects,
        )
        result = self._package_result(resp)

        return result

    @property
    def leaf(self) -> str:
        """
            API leaf path for the stored call.

            :returns: Leaf path string.
        """
        return self._leaf


class Paging:
    """
        The :class:`Paging` object combines a the collection of parameters that are necessary to preform paging opertions
        on the results of a REST API call for a collection.
    """

    def __init__(
        self,
        *,
        page: int,
        count: int,
        total_count: int,
        per_page: int,
        first_page: int,
        last_page: int,
        request_next: Optional[PreCannedRequest] = None,
        request_prev: Optional[PreCannedRequest] = None
    ):
        """
            Construct a paging descriptor for REST collection results.

            :param page: Current page number.
            :param count: Number of items in this page.
            :param total_count: Total items across all pages.
            :param per_page: Maximum items per page.
            :param first_page: First page index available.
            :param last_page: Last page index available.
            :param request_next: Callable request for the next page.
            :param request_prev: Callable request for the previous page.
        """
        self._page = page
        self._count = count
        self._total_count = total_count
        self._per_page = per_page
        self._first_page = first_page
        self._last_page = last_page

        self._request_next = request_next
        self._request_prev = request_prev
        return

    @property
    def count(self) -> int:
        """
            Number of items returned in the current result.

            :returns: Count of items in this page.
        """
        return self._count

    @property
    def first_page(self) -> int:
        """
            First page number available in the result set.

            :returns: Integer index of the first page.
        """
        return self._first_page

    @property
    def last_page(self) -> int:
        """
            Last page number available in the result set.

            :returns: Integer index of the last page.
        """
        return self._last_page

    @property
    def page(self) -> int:
        """
            Current page number of the results.

            :returns: Page index beginning at ``1``.
        """
        return self._page

    @property
    def per_page(self) -> int:
        """
            Maximum number of items returned per page.

            :returns: Items per page value.
        """
        return self._per_page

    @property
    def request_next(self) -> Union[PreCannedRequest, None]:
        """
            Stored callable to retrieve the next page of results.

            :returns: A :class:`PreCannedRequest` for the next page or ``None``.
        """
        return self._request_next

    @property
    def request_prev(self) -> Union[PreCannedRequest, None]:
        """
            Stored callable to retrieve the previous page of results.

            :returns: A :class:`PreCannedRequest` for the previous page or ``None``.
        """
        return self._request_prev

    @property
    def total_count(self) -> int:
        """
            Total number of items available across all pages.

            :returns: Overall item count.
        """
        return self._total_count


class ItemsResult(Generic[CT]):
    """
        Holds a list of returned items and optional paging information.
    """

    def __init__(self, items: List[CT], paging: Optional[Paging] = None):
        """
            Container object for paged or unpaged collections.
        """
        self._items = items
        self._paging = paging
        return

    @property
    def is_paged(self):
        """
            Returns a value indicating if this items result is paged.

            :returns: ``True`` if paging information is present.
        """
        rtnval = True if self._paging is not None else False
        return rtnval

    @property
    def items(self) -> List[CT]:
        """
            Returns a list of items.  This could be a complete list of items or the items from a page depending
            on the results of the API call.

            :returns: The list of items for this result.
        """
        return self._items

    @property
    def paging(self) -> Union[Paging, None]:
        """
            Returns the paging details for this result.

            :returns: A :class:`Paging` object or ``None`` if the result is unpaged.
        """
        return self._paging

    def next_page_result(self) -> "ItemsResult[CT]":
        """
            Retrieve the next page of results if there is one.
        """

        result = None

        if self._paging is not None and self._paging.request_next is not None:
            result = self._paging.request_next.perform_call()

        return result

    def prev_page_result(self) -> "ItemsResult[CT]":
        """
            Retrieve the next page of results if there is one.
        """

        result = None

        if self._paging is not None and self._paging.request_prev is not None:
            result = self._paging.request_prev.perform_call()

        return result
