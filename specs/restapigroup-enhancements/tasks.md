# Implementation Plan — RestApiGroup Enhancements

## Module and Models

- [x] 1. Open `automojo-restclient-base/source/packages/automojo/restclient/base/restapigroup.py`
  for in-place extension.
- [x] 2. Add `BASE_LEAF: str = ""` class attribute on `RestApiGroup`.
- [x] 3. Add Sphinx-style docstrings on every new method.

## build_leaf — To Implement

- [x] 4. Implement `build_leaf(*, parts: List[str]) -> str` joining
  `BASE_LEAF` with parts; raise `SemanticError` on any empty part.
- [x] 5. Collapse accidental `//` runs to single `/`.

## negotiate_content_type — To Implement

- [x] 6. Implement `negotiate_content_type(*, request, accept)`
  returning the header dict.

## post_multipart — To Implement

- [x] 7. Implement `post_multipart(*, url, fields, files, aspects)`
  using `requests` streaming and `aspects.completion_timeout`.

## Paging — To Implement

- [x] 8. Implement `iter_pages_cursor(*, fetch_page, cursor_field,
  items_field, aspects)`.
- [x] 9. Implement `iter_pages_offset(*, fetch_page, page_size,
  items_field, aspects)`.
- [x] 10. Implement `iter_pages_link_header(*, initial_url,
  items_field, aspects)` plus the helper
  `_parse_next_link(*, link_header)`.
- [x] 11. Every paging helper raises `ValueError` on missing
  `items_field` rather than silently terminating.

## Backward Compatibility

- [x] 12. Preserve existing `__init__`, `client`, `_parse_item`
  signatures verbatim.
- [x] 13. Confirm no existing api-group test in the repository
  needs to be updated.

## Testing

- [x] 14. `test_build_leaf_simple_join`.
- [x] 15. `test_build_leaf_collapses_double_slash`.
- [x] 16. `test_build_leaf_trailing_slash_base`.
- [x] 17. `test_build_leaf_empty_part_raises`.
- [x] 18. `test_negotiate_content_type_defaults`.
- [x] 19. `test_negotiate_content_type_overrides`.
- [x] 20. `test_post_multipart_uses_aspect_timeout`.
- [x] 21. `test_post_multipart_sends_fields_and_files`.
- [x] 22. `test_iter_pages_cursor_yields_all_items_in_order`.
- [x] 23. `test_iter_pages_cursor_missing_items_raises`.
- [x] 24. `test_iter_pages_offset_terminates_on_short_page`.
- [x] 25. `test_iter_pages_offset_missing_items_raises`.
- [x] 26. `test_iter_pages_link_header_walks_chain`.
- [x] 27. `test_iter_pages_link_header_terminates_when_header_absent`.
- [x] 28. `test_existing_apigroup_subclasses_still_construct`.
