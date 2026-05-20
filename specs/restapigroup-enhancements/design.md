# Design

## Overview

The current `RestApiGroup` exposes a constructor, a `client`
property, and a `_parse_item` helper. The VSphere extraction needs
more: composed sub-paths, content-type negotiation, multipart upload,
and paged iteration. Per the §6.6 commitment that `RestApiGroup` is
the *single* base, those capabilities land here rather than as a
vendor fork.

The enhancements are additive: existing api-group subclasses
continue to work unchanged. The new methods follow project standards
(named-only parameters, Aspects-driven behaviour, Sphinx docstrings,
no decorators, explicit returns assigned to locals).

**See Also:** [task-handle-base](../task-handle-base/design.md),
[task-handle-protocol](../../../automojo-interfaces/specs/task-handle-protocol/design.md),
[vpn-control-plane-protocol](../../../automojo-interfaces/specs/vpn-control-plane-protocol/design.md).

---

## Architecture

```
+----------------------------------------------------------+
| RestApiGroup (enhanced)                                  |
|                                                          |
|  CLASS ATTRS:                                            |
|    BASE_LEAF: str = ""                                   |
|                                                          |
|  EXISTING:                                               |
|    __init__(client)                                      |
|    client                                                |
|    _parse_item(data, item_type)                          |
|                                                          |
|  NEW:                                                    |
|    build_leaf(parts) -> str                              |
|    negotiate_content_type(request, accept) -> Dict       |
|    post_multipart(url, fields, files, aspects) -> Resp   |
|    iter_pages_cursor(fetch_page, cursor_field, ...)      |
|    iter_pages_offset(fetch_page, page_size, ...)         |
|    iter_pages_link_header(initial_url, ...)              |
+----------------------------+-----------------------------+
                             ^
                             |
                +------------+-------------+
                | Subclasses               |
                |  VmGroup, ClusterGroup,  |
                |  DatastoreGroup, ...     |
                |  (automojo-interop-      |
                |   vsphere/apigroups/)    |
                +--------------------------+
```

---

## Data Model

```python
from typing import IO, Callable, Dict, Iterator, List, Optional, TYPE_CHECKING

import weakref

from automojo.errors.exceptions import SemanticError

if TYPE_CHECKING:
    from requests import Response
    from automojo.restclient.base.restclientbase import RestClientBase
    from automojo.restclient.base.aspectsrest import AspectsRest


class RestApiGroup:
    """
        Base class for REST API operation groups.

        Subclasses MAY set BASE_LEAF to a path prefix (e.g. "/vcenter/vm")
        and use build_leaf(...) to compose per-call sub-paths.
    """

    BASE_LEAF: str = ""

    def __init__(self, client: "RestClientBase") -> None:
        self._client_ref = weakref.ref(client)
        return

    @property
    def client(self) -> "RestClientBase":
        rtnval = self._client_ref()
        return rtnval

    # ---- existing helper kept verbatim ----
    def _parse_item(self, data: dict, item_type: type):
        ...

    # ---- new helpers ----

    def build_leaf(self, *, parts: List[str]) -> str:
        """
            Builds a path leaf by joining BASE_LEAF with the provided parts.

            :param parts: Non-empty string segments to append.

            :returns: Composed leaf path.
            :raises: SemanticError when any part is empty.
        """
        if any(len(p) == 0 for p in parts):
            raise SemanticError("RestApiGroup.build_leaf parts must be non-empty.")
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
        # collapse accidental double slashes other than the scheme separator
        while "//" in rtnval:
            rtnval = rtnval.replace("//", "/")
        return rtnval

    def negotiate_content_type(
        self,
        *,
        request: str = "application/json",
        accept: str = "application/json",
    ) -> Dict[str, str]:
        rtnval = {"Content-Type": request, "Accept": accept}
        return rtnval

    def post_multipart(
        self,
        *,
        url: str,
        fields: Dict[str, str],
        files: Dict[str, IO[bytes]],
        aspects: "AspectsRest",
    ) -> "Response":
        """
            Streams a multipart/form-data POST built from `fields` and `files`.

            :param url: Fully-qualified URL.
            :param fields: Form fields.
            :param files: Open binary streams keyed by form field name.
            :param aspects: Behaviour controls; completion_timeout is the
                upload timeout.

            :returns: requests.Response.
        """
        session = self.client._session
        timeout = aspects.completion_timeout
        rtnval = session.post(
            url=url,
            data=fields,
            files=files,
            timeout=timeout,
            stream=True,
        )
        return rtnval

    def iter_pages_cursor(
        self,
        *,
        fetch_page: Callable[[Optional[str]], dict],
        cursor_field: str = "next",
        items_field: str = "items",
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        cursor: Optional[str] = None
        while True:
            page = fetch_page(cursor)
            if items_field not in page:
                raise ValueError(
                    f"iter_pages_cursor: missing items field {items_field!r}"
                )
            for item in page[items_field]:
                yield item
            cursor = page.get(cursor_field)
            if cursor is None:
                break

    def iter_pages_offset(
        self,
        *,
        fetch_page: Callable[[int, int], dict],
        page_size: int,
        items_field: str = "items",
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        offset = 0
        while True:
            page = fetch_page(offset, page_size)
            if items_field not in page:
                raise ValueError(
                    f"iter_pages_offset: missing items field {items_field!r}"
                )
            items = page[items_field]
            for item in items:
                yield item
            if len(items) < page_size:
                break
            offset += page_size

    def iter_pages_link_header(
        self,
        *,
        initial_url: str,
        items_field: str = "items",
        aspects: "AspectsRest",
    ) -> Iterator[dict]:
        session = self.client._session
        next_url: Optional[str] = initial_url
        while next_url is not None:
            response = session.get(url=next_url, timeout=aspects.completion_timeout)
            payload = response.json()
            if items_field not in payload:
                raise ValueError(
                    f"iter_pages_link_header: missing items field {items_field!r}"
                )
            for item in payload[items_field]:
                yield item
            link_header = response.headers.get("Link", "")
            next_url = _parse_next_link(link_header=link_header)


def _parse_next_link(*, link_header: str) -> Optional[str]:
    """
        Extracts the rel="next" URL from a Link header, or None.
    """
    rtnval: Optional[str] = None
    if len(link_header) > 0:
        for part in link_header.split(","):
            segment = part.strip()
            if 'rel="next"' in segment:
                url_start = segment.find("<")
                url_end = segment.find(">")
                if url_start >= 0 and url_end > url_start:
                    rtnval = segment[url_start + 1:url_end]
                    break
    return rtnval
```

---

## Module Layout

```
automojo-restclient-base/source/packages/automojo/restclient/base/
  restapigroup.py     <-- extended in place
  restclientbase.py   (existing — used by post_multipart for session access)
  aspectsrest.py      (existing — supplies AspectsRest type)
```

---

## See Also

- [task-handle-base](../task-handle-base/design.md) — the second
  reusable building block landing in this milestone.
- [task-handle-protocol](../../../automojo-interfaces/specs/task-handle-protocol/design.md).
- [vpn-control-plane-protocol](../../../automojo-interfaces/specs/vpn-control-plane-protocol/design.md)
  — Tailscale/Twingate control planes consume `RestApiGroup`.

---

## Testing Strategy

- **`build_leaf` tests.** Joins single and multi-part inputs;
  collapses double slashes; raises on empty parts; handles
  trailing-slash `BASE_LEAF` correctly.
- **`negotiate_content_type` tests.** Defaults produce JSON/JSON;
  overrides are returned verbatim.
- **`post_multipart` tests.** Uses `responses` or `requests-mock` to
  capture the request; verify `Content-Type` is `multipart/form-data`
  and that `fields` and `files` are included; verify the timeout is
  the aspects' `completion_timeout`.
- **`iter_pages_cursor` tests.** Programmed three-page fixture
  yields all items in order; terminates when cursor is `None`;
  raises `ValueError` when `items` field is missing on any page.
- **`iter_pages_offset` tests.** Yields all items; terminates on
  short page; raises on missing items field.
- **`iter_pages_link_header` tests.** Walks `Link: <url>; rel="next"`
  chains; terminates when header is missing; raises on missing
  items field.
- **Back-compat tests.** Existing `RestApiGroup` consumers continue
  to construct and use `client` / `_parse_item` unchanged.
- **No property tests required at this layer** — every new helper is
  small and example-coverable. Property tests for the higher-level
  pipelines that compose these helpers live in
  `cloud-resource-model` and `provisioning-engine-pipeline`
  (out of scope here).
