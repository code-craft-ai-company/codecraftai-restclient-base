# Design

## Overview

`TaskHandle` is the reusable REST-polling implementation of
`ITaskHandle` (defined in `automojo-interfaces/task-handle-protocol`).
It encapsulates the "GET this URL until the state field reaches a
terminal value" pattern that vSphere, Proxmox, Nutanix, and other
async-API venues use uniformly.

The class is configured by injecting small extractor callables —
`state_extractor`, `progress_extractor`, `payload_extractor`,
`error_extractor` — so the same loop works for any vendor's JSON
shape. Pacing is controlled entirely by the caller's `AspectsRest`
instance (per §6.6 commitment).

**See Also:** [task-handle-protocol](../../../automojo-interfaces/specs/task-handle-protocol/design.md),
[restapigroup-enhancements](../restapigroup-enhancements/design.md).

---

## Architecture

```
+---------------------------------------------------------+
| Long-running api call (e.g. VmGroup.clone)              |
|   returns TaskHandle(task_id=..., status_url=..., ...)  |
+--------------------------+------------------------------+
                           |
                           v
+---------------------------------------------------------+
| TaskHandle                                              |
|   wait(aspects)  --> poll status_url every              |
|                      aspects.completion_interval        |
|                      until terminal or timeout          |
|   cancel(aspects)--> POST cancel_url, or raise          |
|                      NotImplementedError                |
|   is_done()      --> based on _last_observed_state      |
|   task_id()      --> the constructor's task_id          |
+--------------------------+------------------------------+
                           |
                           v
+---------------------------------------------------------+
| RestClientBase._session.get(status_url, timeout=...)    |
+---------------------------------------------------------+
```

---

## Data Model

```python
from typing import Callable, Optional
import time

from automojo.errors.exceptions import SemanticError
from automojo.interfaces.itaskhandle import (
    ITaskHandle,
    TaskResult,
    TaskState,
)
from automojo.restclient.base.aspectsrest import AspectsRest
from automojo.restclient.base.restclientbase import RestClientBase


TERMINAL_STATES = (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED)


class TaskHandle(ITaskHandle):
    """
        Reusable REST-polling implementation of ITaskHandle.
    """

    def __init__(
        self,
        *,
        task_id: str,
        client: RestClientBase,
        status_url: str,
        cancel_url: Optional[str],
        state_extractor: Callable[[dict], TaskState],
        progress_extractor: Optional[Callable[[dict], int]] = None,
        payload_extractor: Optional[Callable[[dict], dict]] = None,
        error_extractor: Optional[Callable[[dict], Optional[str]]] = None,
    ) -> None:
        self._task_id = task_id
        self._client = client
        self._status_url = status_url
        self._cancel_url = cancel_url
        self._state_extractor = state_extractor
        self._progress_extractor = progress_extractor
        self._payload_extractor = payload_extractor
        self._error_extractor = error_extractor
        self._last_observed_state: Optional[TaskState] = None
        return

    def task_id(self) -> str:
        rtnval = self._task_id
        return rtnval

    def is_done(self) -> bool:
        rtnval = False
        if self._last_observed_state in TERMINAL_STATES:
            rtnval = True
        return rtnval

    def wait(self, *, aspects: AspectsRest) -> TaskResult:
        interval = aspects.completion_interval
        timeout = aspects.completion_timeout
        if interval <= 0:
            raise SemanticError("TaskHandle.wait requires completion_interval > 0.")
        if timeout <= 0:
            raise SemanticError("TaskHandle.wait requires completion_timeout > 0.")
        deadline = time.monotonic() + timeout

        rtnval: Optional[TaskResult] = None
        while True:
            payload = self._fetch_status()
            state = self._state_extractor(payload)
            self._last_observed_state = state
            if state in TERMINAL_STATES:
                rtnval = self._assemble_result(state=state, payload=payload)
                break
            if time.monotonic() >= deadline:
                err = (
                    f"TaskHandle.wait timed out after {timeout}s for task "
                    f"{self._task_id!r} (last state {state!r})."
                )
                raise TimeoutError(err)
            time.sleep(interval)

        return rtnval

    def cancel(self, *, aspects: AspectsRest) -> None:
        if self._last_observed_state in TERMINAL_STATES:
            return None
        if self._cancel_url is None:
            err = f"TaskHandle for task {self._task_id!r} is not cancellable."
            raise NotImplementedError(err)
        session = self._client._session
        session.post(url=self._cancel_url, timeout=aspects.completion_timeout)
        return None

    # ---- internals ----

    def _fetch_status(self) -> dict:
        session = self._client._session
        response = session.get(url=self._status_url)
        rtnval = response.json()
        return rtnval

    def _assemble_result(self, *, state: TaskState, payload: dict) -> TaskResult:
        progress = 0
        if self._progress_extractor is not None:
            progress = self._progress_extractor(payload)
        error: Optional[str] = None
        if self._error_extractor is not None:
            error = self._error_extractor(payload)
        sub_payload: Optional[dict] = None
        if self._payload_extractor is not None:
            sub_payload = self._payload_extractor(payload)
        rtnval = TaskResult(
            task_id=self._task_id,
            state=state,
            progress=progress,
            error=error,
            payload=sub_payload,
        )
        return rtnval
```

---

## Module Layout

```
automojo-restclient-base/source/packages/automojo/restclient/base/
  taskhandle.py        <-- TaskHandle, TERMINAL_STATES
  aspectsrest.py       (existing — supplies AspectsRest)
  restclientbase.py    (existing — supplies the _session)
```

---

## See Also

- [task-handle-protocol](../../../automojo-interfaces/specs/task-handle-protocol/design.md)
  — the interface this class implements.
- [restapigroup-enhancements](../restapigroup-enhancements/design.md)
  — the other reusable building block landing in the same milestone.
- [vpn-control-plane-protocol](../../../automojo-interfaces/specs/vpn-control-plane-protocol/design.md)
  — control planes that surface async ACL applies may return a
  `TaskHandle` from `apply_acl`.

---

## Testing Strategy

- **Construction tests.** All constructor parameters captured;
  `task_id()` returns the supplied id; `is_done()` returns `False`
  before any `wait()` call.
- **`wait` success.** Programmed mock cycle
  `[PENDING, RUNNING, SUCCEEDED]` returns a `TaskResult` with state
  `SUCCEEDED`; `is_done()` returns `True` afterwards.
- **`wait` failure.** Programmed cycle ending in `FAILED` returns a
  `TaskResult` with state `FAILED` and the error message extracted.
- **`wait` cancelled.** Programmed cycle ending in `CANCELLED`
  returns a `TaskResult` with state `CANCELLED`.
- **`wait` timeout.** Programmed cycle that never reaches a terminal
  state raises `TimeoutError` with the task id and last state in the
  message; total elapsed is bounded by
  `timeout + interval` (allows one straddling poll).
- **`wait` bad aspects.** `completion_interval <= 0` or
  `completion_timeout <= 0` raises `SemanticError`.
- **`cancel`.** With `cancel_url` set, POSTs the URL and returns
  `None`. With `cancel_url=None`, raises `NotImplementedError`. With
  task already in a terminal state, returns `None` without calling
  the network.
- **No property tests required at the base layer** — the poll loop
  is small and deterministic with a mock clock. Property tests for
  the pipelines that compose `TaskHandle` (provisioning
  apply / destroy) live in higher-level specs.
