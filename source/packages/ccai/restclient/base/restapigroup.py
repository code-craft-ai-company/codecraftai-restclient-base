"""
    .. module:: restapigroup
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Contains the :class:`RestApiGroup` base class and helpers
        for composing REST API operation groups.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    TypeVar,
)

import weakref

from ccai.errors.exceptions import SemanticError


if TYPE_CHECKING:
    from requests import Response

    from ccai.restclient.base.aspectsrest import AspectsRest
    from ccai.restclient.base.restclientbase import RestClientBase


T = TypeVar('T')


class RestApiGroup:
    """
        Base class for REST API operation groups.

        Subclasses MAY set :data:`BASE_LEAF` to a path prefix
        (e.g. ``"/vcenter/vm"``) and call :meth:`build_leaf` to compose
        per-call sub-paths.  The class provides additive helpers for
        content-type negotiation, multipart upload, and paged iteration
        without changing the original construction surface.
    """

    BASE_LEAF: str = ""

    def __init__(self, client: "RestClientBase"):
        """
            Initializes the api group with a weak reference to the
            owning rest client.

            :param client: The owning :class:`RestClientBase` instance.
        """
        self._client_ref = weakref.ref(client)
        return

    @property
    def client(self) -> "RestClientBase":
        """
            Returns the owning rest client instance, or ``None`` when the
            owning client has been garbage collected.

            :returns: The owning rest client.
        """
        rtnval = self._client_ref()
        return rtnval

    def _parse_item(self, data: Dict[str, Any], item_type: type) -> Any:
        """
            Parse a dictionary into a SchemaObject instance.

            :param data: Raw dictionary data.
            :param item_type: Target SchemaObject type.

            :returns: Parsed SchemaObject instance, or the raw dictionary
                when parsing fails.
        """
        try:
            # Use from_dict if available (SchemaObject types)
            if hasattr(item_type, 'from_dict'):
                rtnval = item_type.from_dict(data)
            else:
                rtnval = item_type(**data)
        except SemanticError:
            # API-misuse errors must never be silently absorbed; let them
            # bubble so the calling code is fixed rather than masked.
            raise
        except (TypeError, ValueError, KeyError, AttributeError):
            # Fallback: return the raw dict when the payload does not fit
            # the target schema (shape mismatch / missing keys).
            rtnval = data
        return rtnval

    # ------------------------------------------------------------------
    # build_leaf
    # ------------------------------------------------------------------

    def build_leaf(self, *, parts: List[str]) -> str:
        """
            Builds a path leaf by joining :data:`BASE_LEAF` with the
            provided parts using single ``/`` separators.  Collapses any
            accidental double-slash runs and trims leading slashes that
            would clash with :data:`BASE_LEAF`.

            :param parts: Non-empty string segments to append.  Each
                part is required to be a non-empty string; segments are
                allowed to contain ``/`` characters so pre-built
                sub-paths may be passed directly.

            :returns: The composed leaf path.
            :raises: SemanticError
        """
        if parts is None:
            raise SemanticError("RestApiGroup.build_leaf requires a non-None parts list.")

        for part in parts:
            if not isinstance(part, str):
                raise SemanticError(
                    "RestApiGroup.build_leaf parts must all be strings."
                )
            if len(part) == 0:
                raise SemanticError(
                    "RestApiGroup.build_leaf parts must all be non-empty strings."
                )

        base = self.BASE_LEAF
        joined = "/".join(parts)

        if base.endswith("/"):
            base = base[:-1]

        if joined.startswith("/"):
            joined = joined[1:]

        if len(base) == 0:
            rtnval = joined
        else:
            rtnval = base + "/" + joined

        # Collapse accidental double slashes (the api group does not deal
        # with scheme-bearing URLs so no exception is required).
        while "//" in rtnval:
            rtnval = rtnval.replace("//", "/")

        return rtnval

    # ------------------------------------------------------------------
    # negotiate_content_type
    # ------------------------------------------------------------------

    def negotiate_content_type(
        self,
        *,
        request: str = "application/json",
        accept: str = "application/json",
    ) -> Dict[str, str]:
        """
            Builds a header dictionary expressing the request body and
            response content types.

            :param request: Value for the ``Content-Type`` header.
            :param accept: Value for the ``Accept`` header.

            :returns: A header dictionary.
        """
        rtnval = {"Content-Type": request, "Accept": accept}
        return rtnval

    # ------------------------------------------------------------------
    # post_multipart
    # ------------------------------------------------------------------

    def post_multipart(
        self,
        *,
        url: str,
        fields: Dict[str, str],
        files: Dict[str, IO[bytes]],
        aspects: "AspectsRest",
    ) -> "Response":
        """
            Streams a ``multipart/form-data`` POST built from `fields`
            and `files`.

            :param url: Fully-qualified URL of the upload endpoint.
            :param fields: Mapping of form field name to scalar value.
            :param files: Mapping of form field name to an open binary
                file-like object.  Streams are not closed by this
                method; callers retain ownership.
            :param aspects: Behaviour controls.  ``completion_timeout``
                is used as the upload timeout.

            :returns: The raw :class:`requests.Response`.
        """
        owning_client = self.client
        if owning_client is None:
            raise SemanticError(
                "RestApiGroup.post_multipart called after the owning "
                "RestClientBase was garbage collected."
            )
        session = owning_client._session
        timeout = aspects.completion_timeout

        rtnval = session.post(
            url=url,
            data=fields,
            files=files,
            timeout=timeout,
            stream=True,
        )
        return rtnval

    # ------------------------------------------------------------------
    # iter_pages_cursor
    # ------------------------------------------------------------------

    def iter_pages_cursor(
        self,
        *,
        fetch_page: Callable[[Optional[str]], dict],
        cursor_field: str = "next",
        items_field: str = "items",
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        """
            Iterates a cursor-paginated endpoint, yielding items in
            order across pages.

            :param fetch_page: Callable accepting the current cursor
                token (``None`` on the first call) and returning a page
                dictionary.
            :param cursor_field: Name of the field on each page payload
                holding the next cursor token (``None`` indicates the
                final page).
            :param items_field: Name of the field on each page payload
                holding the list of items.
            :param aspects: Behaviour controls (reserved for future use
                by sub-classes; required for interface uniformity).

            :returns: An iterator over the items.
            :raises: ValueError
        """
        # `aspects` is accepted to keep the interface uniform across all
        # paging helpers; it is currently consumed only when callers
        # extend `fetch_page` to honour it.
        _ = aspects

        cursor: Optional[str] = None
        while True:
            page = fetch_page(cursor)
            if items_field not in page:
                err_msg = (
                    "iter_pages_cursor: response page missing required items "
                    "field {0!r}.".format(items_field)
                )
                raise ValueError(err_msg)

            items = page[items_field]
            for item in items:
                yield item

            cursor = page.get(cursor_field)
            if cursor is None:
                break
        return

    # ------------------------------------------------------------------
    # iter_pages_offset
    # ------------------------------------------------------------------

    def iter_pages_offset(
        self,
        *,
        fetch_page: Callable[[int, int], dict],
        page_size: int,
        items_field: str = "items",
        max_pages: int = 10000,
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        """
            Iterates an offset/limit-paginated endpoint, yielding items
            in order until a page returns fewer items than `page_size`.

            :param fetch_page: Callable accepting ``(offset, page_size)``
                and returning a page dictionary.
            :param page_size: Maximum item count per page.
            :param items_field: Name of the field on each page payload
                holding the list of items.
            :param max_pages: Hard upper bound on the number of pages
                fetched. Guards against a misbehaving endpoint that always
                returns a full page, which would otherwise loop forever.
            :param aspects: Behaviour controls (reserved for future use).

            :returns: An iterator over the items.
            :raises: SemanticError, ValueError
        """
        _ = aspects

        if page_size <= 0:
            raise SemanticError(
                "iter_pages_offset requires page_size > 0."
            )
        if max_pages <= 0:
            raise SemanticError(
                "iter_pages_offset requires max_pages > 0."
            )

        offset = 0
        pages_fetched = 0
        while True:
            page = fetch_page(offset, page_size)
            pages_fetched = pages_fetched + 1
            if items_field not in page:
                err_msg = (
                    "iter_pages_offset: response page missing required items "
                    "field {0!r}.".format(items_field)
                )
                raise ValueError(err_msg)

            items = page[items_field]
            for item in items:
                yield item

            if len(items) < page_size:
                break
            if pages_fetched >= max_pages:
                err_msg = (
                    "iter_pages_offset exceeded max_pages={0}; the endpoint "
                    "never returned a short final page.".format(max_pages)
                )
                raise ValueError(err_msg)
            offset = offset + page_size
        return

    # ------------------------------------------------------------------
    # iter_pages_link_header
    # ------------------------------------------------------------------

    def iter_pages_link_header(
        self,
        *,
        initial_url: str,
        items_field: str = "items",
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        """
            Iterates a ``Link``-header-paginated endpoint, following the
            ``rel="next"`` URL until no such relation is present.

            :param initial_url: URL of the first page.
            :param items_field: Name of the field on each page payload
                holding the list of items.
            :param aspects: Behaviour controls.  ``completion_timeout``
                is used as the per-request timeout.

            :returns: An iterator over the items.
            :raises: ValueError
        """
        owning_client = self.client
        if owning_client is None:
            raise SemanticError(
                "RestApiGroup.iter_pages_link_header called after the "
                "owning RestClientBase was garbage collected."
            )
        session = owning_client._session

        next_url: Optional[str] = initial_url
        while next_url is not None:
            response = session.get(url=next_url, timeout=aspects.completion_timeout)
            payload = response.json()

            if items_field not in payload:
                err_msg = (
                    "iter_pages_link_header: response page missing required "
                    "items field {0!r}.".format(items_field)
                )
                raise ValueError(err_msg)

            items = payload[items_field]
            for item in items:
                yield item

            link_header = response.headers.get("Link", "")
            next_url = _parse_next_link(link_header=link_header)
        return


def _parse_next_link(*, link_header: str) -> Optional[str]:
    """
        Extracts the ``rel="next"`` URL from an HTTP ``Link`` header.

        :param link_header: The raw ``Link`` header value, possibly
            empty.

        :returns: The next-page URL, or ``None`` when no ``rel="next"``
            relation is present.
    """
    rtnval: Optional[str] = None

    if link_header is not None and len(link_header) > 0:
        for part in link_header.split(","):
            segment = part.strip()
            if 'rel="next"' in segment:
                url_start = segment.find("<")
                url_end = segment.find(">")
                if url_start >= 0 and url_end > url_start:
                    rtnval = segment[url_start + 1:url_end]
                    break

    return rtnval
