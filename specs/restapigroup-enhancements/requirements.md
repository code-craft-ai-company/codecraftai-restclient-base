# Requirements

## Introduction

The `restapigroup-enhancements` feature audits and extends
`RestApiGroup` in
`automojo-restclient-base/source/packages/automojo/restclient/base/restapigroup.py`
so that the VSphere extraction (`automojo-interop-vsphere`) and every
future REST-shaped interop client can build on a single base class
rather than forking. Per §6.6 decision in
`PLAN-VPN-AND-CLOUD-PROVISIONING.md` — "API-group base → RestApiGroup
is the single source" — anything the existing VSphere `ext/*` classes
do that the current `RestApiGroup` does not must be absorbed here.

The known gaps to close are:

- composed sub-paths (an api group rooted at a parent leaf plus a
  per-call sub-leaf, used heavily by vSphere's `vcenter/vm/{id}/...`
  shapes)
- content-type negotiation (JSON default, XML / multipart override)
- multipart upload (OVF deploy from local file)
- response paging variants (cursor token, offset/limit, link header)

This spec defines the *enhancements to the base class only*. Specific
api groups in venue packages consume the new surface.

**See Also:** [task-handle-base](../task-handle-base/design.md),
[task-handle-protocol](../../../automojo-interfaces/specs/task-handle-protocol/design.md).

---

## Requirements

### Requirement 1: Composed Sub-Path Helpers

**User Story:** As a vSphere api-group implementer, I want a single
helper that builds `<BASE_LEAF>/<id>/<sub_leaf>` URLs so I do not
write `f"{self.BASE_LEAF}/{vm}/power"` strings everywhere.

#### Acceptance Criteria

1. THE SYSTEM SHALL declare `BASE_LEAF: str = ""` as a class
   attribute on `RestApiGroup`.
2. THE SYSTEM SHALL provide a method
   `build_leaf(*, parts: List[str]) -> str` that joins
   `BASE_LEAF` with the provided parts using single `/` separators,
   collapsing any duplicates, and trimming a leading `/` from the
   result when `BASE_LEAF` already supplies one.
3. THE SYSTEM SHALL require every part to be a non-empty string;
   raise `SemanticError` on empty input.
4. WHEN parts contain `/` characters THE SYSTEM SHALL preserve them
   (callers may pass pre-built sub-paths).

---

### Requirement 2: Content-Type Negotiation Helper

**User Story:** As an api-group implementer, I want a single way to
indicate the request and accept content types so I do not assemble
headers manually.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide a helper
   `negotiate_content_type(*, request: str = "application/json",
   accept: str = "application/json") -> Dict[str, str]` returning a
   header dict suitable for use with the parent client's `Session`.
2. THE SYSTEM SHALL leave existing call sites unchanged — the
   helper is additive.

---

### Requirement 3: Multipart Upload Support

**User Story:** As an OVF-deploy implementer, I want a helper that
posts a `multipart/form-data` body composed of file streams plus
named fields so I can upload large OVF files without writing the
request shape by hand.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide
   `post_multipart(*, url: str, fields: Dict[str, str],
   files: Dict[str, IO[bytes]], aspects: AspectsRest) -> Response`.
2. THE SYSTEM SHALL stream file uploads (no full-payload buffering)
   when the underlying transport supports it.
3. THE SYSTEM SHALL honour `aspects.completion_timeout` as the
   upload timeout.

---

### Requirement 4: Response Paging Helpers

**User Story:** As an api-group implementer, I want a uniform way
to iterate paged responses so callers receive a single list rather
than reassembling pages.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide `iter_pages_cursor(*, fetch_page,
   cursor_field: str = "next", items_field: str = "items",
   aspects: AspectsRest) -> Iterator[dict]` for cursor-token APIs.
2. THE SYSTEM SHALL provide `iter_pages_offset(*, fetch_page,
   page_size: int, items_field: str = "items", aspects: AspectsRest)
   -> Iterator[dict]` for offset/limit APIs.
3. THE SYSTEM SHALL provide `iter_pages_link_header(*, initial_url,
   items_field: str = "items", aspects: AspectsRest) -> Iterator[dict]`
   for `Link: <url>; rel="next"` APIs.
4. WHEN a paging response is malformed THE SYSTEM SHALL raise
   `ValueError` with a message identifying the missing field, not
   silently terminate the iterator.

---

### Requirement 5: Aspects Required on Every New Method

**User Story:** As a caller, I want timeouts and retries to be
controllable from the outside on every new method.

#### Acceptance Criteria

1. THE SYSTEM SHALL require `aspects: AspectsRest` (keyword-only)
   on `post_multipart`, `iter_pages_cursor`, `iter_pages_offset`,
   `iter_pages_link_header`.
2. THE SYSTEM SHALL NOT add `@retry` or any behaviour-modifying
   decorator to any of the new methods.

---

### Requirement 6: Backward Compatibility

**User Story:** As an existing api-group implementer, I want my
code to keep working without changes.

#### Acceptance Criteria

1. THE SYSTEM SHALL preserve the current `RestApiGroup.__init__`
   signature and the `client` property.
2. THE SYSTEM SHALL preserve the current `_parse_item` helper
   unchanged.
3. WHEN `BASE_LEAF` is left as the default empty string THE SYSTEM
   SHALL make `build_leaf` behave as a plain path joiner with no
   prefix.
