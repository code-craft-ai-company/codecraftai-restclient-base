"""
    .. module:: taskhandle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Reusable REST-polling implementation of the
        :class:`ITaskHandle` protocol.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


from typing import TYPE_CHECKING, Callable, Optional

import os
import time

from automojo.errors.exceptions import SemanticError

# ---------------------------------------------------------------------------
# Cross-repository type imports.
#
# ``ITaskHandle`` / ``TaskResult`` / ``TaskState`` are core types owned by
# ``automojo-interfaces``. They are imported hard so a missing or mis-pathed
# core dependency fails loudly at import time. A previous ImportError fallback
# defined ``TaskState`` as a string ``Enum`` while the canonical type is an
# ``IntEnum`` -- a value-incompatible silent divergence.
# ---------------------------------------------------------------------------

from automojo.interfaces.itaskhandle import (
    ITaskHandle as _ITaskHandleBase,
    TaskResult,
    TaskState,
)


if TYPE_CHECKING:
    from automojo.restclient.base.aspectsrest import AspectsRest
    from automojo.restclient.base.restclientbase import RestClientBase


TERMINAL_STATES = (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED)


class TaskHandle(_ITaskHandleBase):
    """
        Reusable REST-polling implementation of
        :class:`ITaskHandle`.  Polls a status URL with a monotonic-clock
        loop whose pacing is controlled entirely by the supplied
        :class:`AspectsRest` instance.
    """

    def __init__(
        self,
        *,
        task_id: str,
        client: "RestClientBase",
        status_url: str,
        cancel_url: Optional[str],
        state_extractor: Callable[[dict], "TaskState"],
        progress_extractor: Optional[Callable[[dict], int]] = None,
        payload_extractor: Optional[Callable[[dict], dict]] = None,
        error_extractor: Optional[Callable[[dict], Optional[str]]] = None,
    ) -> None:
        """
            Initializes the task handle.

            :param task_id: Vendor task identifier.
            :param client: Owning rest client; supplies the underlying
                :class:`requests.Session`.
            :param status_url: URL returning the task status payload.
            :param cancel_url: URL accepting a cancel request, or
                ``None`` when the task is not cancellable.
            :param state_extractor: Callable mapping a status payload
                to a :class:`TaskState`.
            :param progress_extractor: Optional callable returning a
                progress percentage from the status payload.
            :param payload_extractor: Optional callable returning the
                vendor sub-payload (e.g. created resource id) from the
                status payload.
            :param error_extractor: Optional callable returning an error
                message from the status payload, or ``None`` when no
                error is present.
        """
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
        """
            Returns the vendor task identifier captured at construction.

            :returns: The task identifier.
        """
        rtnval = self._task_id
        return rtnval

    def is_done(self) -> bool:
        """
            Returns whether the most recently observed state is a
            terminal one.  Does not poll the network.

            :returns: ``True`` when the last observed state is in
                :data:`TERMINAL_STATES`; ``False`` otherwise (including
                the case where no observation has yet been made).
        """
        rtnval = False
        if self._last_observed_state is not None:
            if self._last_observed_state in TERMINAL_STATES:
                rtnval = True
        return rtnval

    def wait(self, *, aspects: "AspectsRest") -> "TaskResult":
        """
            Polls :attr:`status_url` every
            ``aspects.completion_interval`` seconds until the task
            reaches a terminal state or ``aspects.completion_timeout``
            elapses.

            :param aspects: Behaviour controls.

            :returns: A :class:`TaskResult` describing the terminal
                state.
            :raises: SemanticError, TimeoutError
        """
        interval = aspects.completion_interval
        timeout = aspects.completion_timeout

        if interval <= 0:
            raise SemanticError(
                "TaskHandle.wait requires aspects.completion_interval > 0."
            )
        if timeout <= 0:
            raise SemanticError(
                "TaskHandle.wait requires aspects.completion_timeout > 0."
            )

        start = time.monotonic()
        deadline = start + timeout

        rtnval: Optional[TaskResult] = None
        while True:
            payload = self._fetch_status(aspects=aspects)
            state = self._state_extractor(payload)
            self._last_observed_state = state

            if state in TERMINAL_STATES:
                rtnval = self._assemble_result(state=state, payload=payload)
                break

            now = time.monotonic()
            if now >= deadline:
                err_msg = (
                    "TaskHandle.wait timed out after {0}s for task "
                    "{1!r} (last observed state {2!r}).".format(
                        timeout, self._task_id, state,
                    )
                )
                raise TimeoutError(err_msg)

            time.sleep(interval)

        return rtnval

    def cancel(self, *, aspects: "AspectsRest") -> None:
        """
            Cancels the task by POSTing to :attr:`cancel_url`.

            When the task has already reached a terminal state this
            method is a no-op.  When the task was constructed without a
            cancel URL this method raises :class:`NotImplementedError`.

            :param aspects: Behaviour controls.  ``completion_timeout``
                is used as the request timeout.

            :returns: ``None``.
            :raises: NotImplementedError
        """
        if self._last_observed_state is not None:
            if self._last_observed_state in TERMINAL_STATES:
                return None

        if self._cancel_url is None:
            err_msg = (
                "TaskHandle for task {0!r} is not cancellable "
                "(no cancel_url provided).".format(self._task_id)
            )
            raise NotImplementedError(err_msg)

        session = self._client._session
        response = session.post(
            url=self._cancel_url, timeout=aspects.completion_timeout
        )
        status_code = response.status_code
        if status_code < 200 or status_code >= 300:
            err_msg_lines = [
                "TaskHandle.cancel received a non-success response.",
                "    task_id: {0!r}".format(self._task_id),
                "    cancel_url: {0!r}".format(self._cancel_url),
                "    status_code: {0}".format(status_code),
            ]
            err_msg = os.linesep.join(err_msg_lines)
            raise RuntimeError(err_msg)
        return None

    # ---- internals ----

    def _fetch_status(self, *, aspects: "AspectsRest") -> dict:
        """
            Fetches the current status payload from :attr:`status_url`.

            The request is bounded by ``aspects.connection_timeout`` so a
            hung status endpoint cannot block :meth:`wait` indefinitely
            and defeat ``aspects.completion_timeout``.

            :param aspects: Behaviour controls; ``connection_timeout`` is
                used as the per-request timeout.

            :returns: The parsed JSON payload.
        """
        session = self._client._session
        response = session.get(
            url=self._status_url, timeout=aspects.connection_timeout
        )
        rtnval = response.json()
        return rtnval

    def _assemble_result(self, *, state: "TaskState", payload: dict) -> "TaskResult":
        """
            Builds a :class:`TaskResult` from a terminal status payload
            using the configured extractors.

            :param state: Terminal task state.
            :param payload: Status payload returned by the vendor.

            :returns: The assembled :class:`TaskResult`.
        """
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
