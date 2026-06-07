# Requirements

## Introduction

The `task-handle-base` feature adds a reusable `TaskHandle` class to
`codecraftai-restclient-base` that implements `ITaskHandle` (from
`codecraftai-interfaces/task-handle-protocol`) for REST-polling APIs.
vSphere, Proxmox, Nutanix, and any other venue whose long-running
operations are surfaced as polling URLs reuse this class instead of
hand-rolling their own poll loops. Vendors whose tasks are not REST-
polled (libvirt, native bindings) implement `ITaskHandle` directly.

Per the §6.6 commitment "Async-task model → sync `TaskHandle.wait(aspects)`
only," the implementation is synchronous, with all pacing
(`completion_interval`, `completion_timeout`) controlled by the
`AspectsRest` instance.

**See Also:** [task-handle-protocol](../../../codecraftai-interfaces/specs/task-handle-protocol/design.md),
[restapigroup-enhancements](../restapigroup-enhancements/design.md).

---

## Requirements

### Requirement 1: TaskHandle Class Implements ITaskHandle

**User Story:** As an interop client implementer, I want a ready-
made `ITaskHandle` implementation so I do not write a poll loop
per venue.

#### Acceptance Criteria

1. THE SYSTEM SHALL define `TaskHandle` implementing `ITaskHandle`
   in `codecraftai-restclient-base/source/packages/ccai/restclient/base/taskhandle.py`.
2. THE SYSTEM SHALL accept the following constructor parameters:
   - `task_id: str`
   - `client: RestClientBase`
   - `status_url: str` (URL to GET for current state)
   - `cancel_url: Optional[str]` (URL to POST/DELETE to cancel, or None)
   - `state_extractor: Callable[[dict], TaskState]`
   - `progress_extractor: Optional[Callable[[dict], int]] = None`
   - `payload_extractor: Optional[Callable[[dict], dict]] = None`
   - `error_extractor: Optional[Callable[[dict], Optional[str]]] = None`
3. THE SYSTEM SHALL store these parameters and expose `task_id()`
   returning the constructor's `task_id`.

---

### Requirement 2: Synchronous Wait with Aspects-Controlled Pacing

**User Story:** As a caller, I want `wait` to block until the task
reaches a terminal state, with poll interval and timeout from my
`AspectsRest` instance.

#### Acceptance Criteria

1. THE SYSTEM SHALL implement `wait(*, aspects: AspectsRest)`
   polling `status_url` every `aspects.completion_interval`
   seconds.
2. WHEN the extracted `TaskState` is `SUCCEEDED`, `FAILED`, or
   `CANCELLED` THE SYSTEM SHALL return the assembled `TaskResult`.
3. WHEN `aspects.completion_timeout` elapses without reaching a
   terminal state THE SYSTEM SHALL raise `TimeoutError` with a
   message containing the `task_id` and the last observed state.
4. THE SYSTEM SHALL update an internal `_last_observed_state`
   each poll so `is_done()` returns accurately without an extra
   poll.

---

### Requirement 3: Cancel

**User Story:** As a destroy/cleanup coordinator, I want to cancel
in-flight tasks.

#### Acceptance Criteria

1. WHEN `cancel_url is not None` THE SYSTEM SHALL implement
   `cancel(*, aspects: AspectsRest)` issuing the cancel request and
   returning `None`.
2. WHEN `cancel_url is None` THE SYSTEM SHALL raise
   `NotImplementedError` with a message identifying the task as
   non-cancellable.
3. WHEN the task is already in a terminal state THE SYSTEM SHALL
   treat `cancel` as a no-op and return `None`.

---

### Requirement 4: is_done Without Side Effects

**User Story:** As a caller polling externally, I want a cheap
`is_done()` accessor that reflects the most recent observation
without issuing a network call.

#### Acceptance Criteria

1. THE SYSTEM SHALL implement `is_done()` returning `True` when
   `_last_observed_state` is in `{SUCCEEDED, FAILED, CANCELLED}`,
   else `False`.
2. THE SYSTEM SHALL NOT poll the network in `is_done()`.
3. WHEN `_last_observed_state` has never been set (no prior
   `wait()` call) THE SYSTEM SHALL return `False`.

---

### Requirement 5: Aspects on Every Behaviour-Bearing Call

**User Story:** As a caller, I want every behaviour-bearing call
to take Aspects.

#### Acceptance Criteria

1. THE SYSTEM SHALL require `aspects: AspectsRest` on `wait` and
   `cancel` as keyword-only.
2. IF a `@retry` or behaviour-modifying decorator is added to
   `wait` or `cancel` THEN THE SYSTEM SHALL be considered non-
   conformant.

---

### Requirement 6: Polling Loop Correctness

**User Story:** As an implementer, I want strong guarantees on the
poll-loop math so timeouts are honoured precisely.

#### Acceptance Criteria

1. THE SYSTEM SHALL drive the loop with a monotonic clock
   (`time.monotonic()`).
2. THE SYSTEM SHALL not exceed `completion_timeout` by more than
   `completion_interval` (i.e. one in-flight poll is allowed to
   straddle the deadline, after which the next iteration raises
   `TimeoutError`).
3. WHEN `completion_interval <= 0` THE SYSTEM SHALL raise
   `SemanticError`.
4. WHEN `completion_timeout <= 0` THE SYSTEM SHALL raise
   `SemanticError`.
