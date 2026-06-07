# Implementation Plan — Task Handle Base

## Module and Models

- [x] 1. Create `codecraftai-restclient-base/source/packages/ccai/restclient/base/taskhandle.py`.
- [x] 2. Add `TERMINAL_STATES = (TaskState.SUCCEEDED, TaskState.FAILED,
  TaskState.CANCELLED)` module constant.
- [x] 3. Add Sphinx-style module and class docstrings.

## TaskHandle — To Implement

- [x] 4. Implement `__init__` capturing every constructor parameter
  listed in the design; initialise
  `_last_observed_state: Optional[TaskState] = None`.
- [x] 5. Implement `task_id()` returning `self._task_id`.
- [x] 6. Implement `is_done()` returning `True` when
  `_last_observed_state in TERMINAL_STATES`.
- [x] 7. Implement `wait(*, aspects)` with monotonic-clock poll loop,
  honouring `completion_interval` / `completion_timeout`, raising
  `SemanticError` on non-positive aspects values, raising
  `TimeoutError` on deadline overrun.
- [x] 8. Implement `cancel(*, aspects)` with terminal-state no-op,
  `NotImplementedError` when no `cancel_url`, POST otherwise.
- [x] 9. Implement `_fetch_status()` and `_assemble_result()`
  internals using injected extractors.

## Testing

- [x] 10. `test_construction_and_task_id`.
- [x] 11. `test_is_done_false_before_wait`.
- [x] 12. `test_wait_succeeded_cycle`.
- [x] 13. `test_wait_failed_cycle_returns_taskresult_with_error`.
- [x] 14. `test_wait_cancelled_cycle`.
- [x] 15. `test_wait_timeout_raises_with_task_id_and_state_in_message`.
- [x] 16. `test_wait_negative_interval_raises_semanticerror`.
- [x] 17. `test_wait_negative_timeout_raises_semanticerror`.
- [x] 18. `test_is_done_true_after_terminal_wait`.
- [x] 19. `test_cancel_with_url_posts_and_returns_none`.
- [x] 20. `test_cancel_without_url_raises_notimplemented`.
- [x] 21. `test_cancel_after_terminal_state_is_noop`.
- [x] 22. `test_wait_uses_monotonic_clock` — mock `time.monotonic`
  to assert deterministic deadline behaviour.

## Property Tests (hypothesis)

- [x] 23. `test_wait_converges_on_first_terminal` — for any sequence
  of non-terminal states followed by a terminal one, `wait` converges
  on the first terminal state.
- [x] 24. `test_wait_times_out_on_all_non_terminal_sequence` — when
  no terminal state is observed, the loop raises `TimeoutError`.
- [x] 25. `test_is_done_matches_terminal_set_after_wait` — `is_done`
  matches the terminal-set membership of the last observed state.
