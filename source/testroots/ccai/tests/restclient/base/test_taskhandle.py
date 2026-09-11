"""
    .. module:: test_taskhandle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit and property tests for the reusable
        :class:`TaskHandle` polling base class.

    The tests are module-level ``test_*`` functions because the testbase
    collector only gathers functions; methods on a ``unittest.TestCase``
    are never run by this repository's merge gate.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Callable, List, Optional

import time

from enum import IntEnum
from unittest.mock import patch

from ccai import testbase

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.errors.exceptions import SemanticError

from ccai.interfaces.itaskhandle import TaskState as CanonicalTaskState

from ccai.restclient.base.aspectsrest import AspectsRest
from ccai.restclient.base.taskhandle import (
    TERMINAL_STATES,
    TaskHandle,
    TaskResult,
    TaskState,
)

from ccai.testshared.restclient.fakesession import FakeSession


STATUS_URL = "https://host/status"
CANCEL_URL = "https://host/cancel"


class _ClientStub:
    """
        Minimal client stand-in carrying just the ``_session`` attribute
        used by :class:`TaskHandle`.
    """

    def __init__(self, session: object = None) -> None:
        self._session = session
        return


def _make_status_session(states: List[TaskState], error_message: Optional[str] = None) -> FakeSession:
    """
        Builds a :class:`FakeSession` whose ``get`` returns a sequence of
        programmed status payloads.

        :param states: Sequence of states to return.
        :param error_message: Optional error string surfaced via the
            payload's ``"error"`` field.

        :returns: The configured session.
    """
    responses = []
    for state in states:
        payload = {"state": state.value}
        if error_message is not None and state == TaskState.FAILED:
            payload["error"] = error_message
        responses.append((200, payload, {}))

    session = FakeSession(responses)
    return session


def _state_extractor(payload: dict) -> TaskState:
    """
        Reference extractor mapping the ``state`` field on a payload to
        a :class:`TaskState`.
    """
    rtnval = TaskState(payload["state"])
    return rtnval


def _error_extractor(payload: dict) -> Optional[str]:
    """
        Reference extractor returning the ``error`` field on a payload,
        or ``None`` when absent.
    """
    rtnval = payload.get("error")
    return rtnval


def _make_handle(session: Optional[FakeSession], task_id: str = "task-1", cancel_url: Optional[str] = None,
                 error_extractor: Optional[Callable[[dict], Optional[str]]] = None) -> TaskHandle:
    """
        Builds a :class:`TaskHandle` over a stub client holding ``session``.
    """
    client = _ClientStub(session=session)
    handle = TaskHandle(
        task_id=task_id,
        client=client,
        status_url=STATUS_URL,
        cancel_url=cancel_url,
        state_extractor=_state_extractor,
        error_extractor=error_extractor,
    )
    return handle


# -------------------------------------------------------------------------
# Construction
# -------------------------------------------------------------------------


def test_taskhandle_construction_and_task_id():
    handle = _make_handle(None)
    testbase.assert_equal(handle.task_id(), "task-1")
    return


def test_taskhandle_is_done_false_before_wait():
    handle = _make_handle(None)
    testbase.assert_equal(handle.is_done(), False)
    return


# -------------------------------------------------------------------------
# wait
# -------------------------------------------------------------------------


def test_taskhandle_wait_succeeded_cycle():
    session = _make_status_session(
        [TaskState.PENDING, TaskState.RUNNING, TaskState.SUCCEEDED]
    )
    handle = _make_handle(session)
    aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

    with patch.object(time, "sleep", return_value=None):
        result = handle.wait(aspects=aspects)

    testbase.assert_equal(isinstance(result, TaskResult), True)
    testbase.assert_equal(result.state, TaskState.SUCCEEDED)
    testbase.assert_equal(result.task_id, "task-1")
    testbase.assert_equal(handle.is_done(), True)
    testbase.assert_equal(len(session.calls), 3)
    return


def test_taskhandle_wait_polls_status_url_with_get():
    session = _make_status_session([TaskState.SUCCEEDED])
    handle = _make_handle(session)
    aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

    with patch.object(time, "sleep", return_value=None):
        handle.wait(aspects=aspects)

    call = session.last_call
    testbase.assert_equal(call.method, "GET")
    testbase.assert_equal(call.url, STATUS_URL)
    return


def test_taskhandle_wait_failed_cycle_returns_taskresult_with_error():
    session = _make_status_session(
        [TaskState.RUNNING, TaskState.FAILED], error_message="boom"
    )
    handle = _make_handle(session, task_id="task-2", error_extractor=_error_extractor)
    aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

    with patch.object(time, "sleep", return_value=None):
        result = handle.wait(aspects=aspects)

    testbase.assert_equal(result.state, TaskState.FAILED)
    testbase.assert_equal(result.error, "boom")
    testbase.assert_equal(handle.is_done(), True)
    return


def test_taskhandle_wait_cancelled_cycle():
    session = _make_status_session(
        [TaskState.RUNNING, TaskState.CANCELLED]
    )
    handle = _make_handle(session, task_id="task-3")
    aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

    with patch.object(time, "sleep", return_value=None):
        result = handle.wait(aspects=aspects)

    testbase.assert_equal(result.state, TaskState.CANCELLED)
    return


def test_taskhandle_wait_timeout_raises_with_task_id_and_state():
    session = _make_status_session(
        [TaskState.RUNNING, TaskState.RUNNING, TaskState.RUNNING]
    )
    handle = _make_handle(session, task_id="never-finishes")
    aspects = AspectsRest(completion_interval=1, completion_timeout=2)

    # Fake monotonic clock that advances on each read so the deadline is
    # crossed after two iterations.
    ticker = iter([0.0, 1.0, 2.5])

    error: Optional[BaseException] = None
    with patch.object(time, "sleep", return_value=None), \
         patch.object(time, "monotonic", side_effect=lambda: next(ticker)):
        try:
            handle.wait(aspects=aspects)
        except TimeoutError as terr:
            error = terr

    testbase.assert_equal(error is not None, True)
    testbase.assert_equal("never-finishes" in str(error), True)
    testbase.assert_equal("RUNNING" in str(error), True)
    return


def test_taskhandle_wait_rejects_non_positive_interval():
    handle = _make_handle(None, task_id="t")
    aspects = AspectsRest(completion_interval=0, completion_timeout=10)
    with testbase.raises(SemanticError):
        handle.wait(aspects=aspects)
    return


def test_taskhandle_wait_rejects_non_positive_timeout():
    handle = _make_handle(None, task_id="t")
    aspects = AspectsRest(completion_interval=1, completion_timeout=0)
    with testbase.raises(SemanticError):
        handle.wait(aspects=aspects)
    return


def test_taskhandle_fetch_status_passes_connection_timeout():
    """
        Regression for audit finding F-H7: every status poll must pass
        ``aspects.connection_timeout`` as the per-request timeout so a hung
        status endpoint cannot defeat ``aspects.completion_timeout``.
    """
    session = _make_status_session([TaskState.SUCCEEDED])
    handle = _make_handle(session, task_id="task-t")
    aspects = AspectsRest(
        completion_interval=0.0001,
        completion_timeout=10,
        connection_timeout=7,
    )

    with patch.object(time, "sleep", return_value=None):
        handle.wait(aspects=aspects)

    testbase.assert_equal(len(session.calls), 1)
    testbase.assert_equal(session.last_call.timeout, 7)
    return


# -------------------------------------------------------------------------
# cancel
# -------------------------------------------------------------------------


def test_taskhandle_cancel_with_url_posts_and_returns_none():
    session = FakeSession([(204, None, {})])
    handle = _make_handle(session, cancel_url=CANCEL_URL)
    aspects = AspectsRest(completion_timeout=5)

    result = handle.cancel(aspects=aspects)

    testbase.assert_equal(result, None)
    testbase.assert_equal(len(session.calls), 1)
    call = session.last_call
    testbase.assert_equal(call.method, "POST")
    testbase.assert_equal(call.url, CANCEL_URL)
    testbase.assert_equal(call.timeout, 5)
    return


def test_taskhandle_cancel_non_success_response_raises():
    """
        Regression: cancel() must surface a non-2xx cancel response as
        an error rather than silently reporting success.
    """
    session = FakeSession([(500, {"message": "boom"}, {})])
    handle = _make_handle(session, cancel_url=CANCEL_URL)
    aspects = AspectsRest(completion_timeout=5)
    with testbase.raises(RuntimeError):
        handle.cancel(aspects=aspects)
    return


def test_taskhandle_cancel_without_url_raises_notimplemented():
    session = FakeSession([])
    handle = _make_handle(session, cancel_url=None)
    aspects = AspectsRest()
    with testbase.raises(NotImplementedError):
        handle.cancel(aspects=aspects)
    testbase.assert_equal(len(session.calls), 0)
    return


def test_taskhandle_cancel_after_terminal_state_is_noop():
    session = FakeSession([])
    handle = _make_handle(session, cancel_url=CANCEL_URL)
    # Simulate a completed wait
    handle._last_observed_state = TaskState.SUCCEEDED

    aspects = AspectsRest()
    result = handle.cancel(aspects=aspects)

    testbase.assert_equal(result, None)
    testbase.assert_equal(len(session.calls), 0)
    return


# -------------------------------------------------------------------------
# Canonical types
# -------------------------------------------------------------------------


def test_taskhandle_taskstate_is_canonical_intenum():
    """
        Regression for audit finding F-H6: ``taskhandle.TaskState`` must be
        the canonical ``ccai.interfaces.itaskhandle.TaskState`` IntEnum, not
        a string-valued fallback.
    """
    testbase.assert_equal(TaskState is CanonicalTaskState, True)
    testbase.assert_equal(issubclass(TaskState, IntEnum), True)
    testbase.assert_equal(int(TaskState.SUCCEEDED), 3)
    return


# -------------------------------------------------------------------------
# Property-based tests covering poll-loop convergence under arbitrary
# state sequences.  ``@given`` is driven by the testbase sequencer's
# PropertyRunner; it is only valid on module-level functions.
# -------------------------------------------------------------------------

_terminal_state_strategy = st.sampled_from(
    [TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED]
)
_non_terminal_state_strategy = st.sampled_from(
    [TaskState.PENDING, TaskState.RUNNING]
)


@given(
constraints={"max_examples": 50},
    prefix=st.lists(_non_terminal_state_strategy, min_size=0, max_size=20),
    terminal=_terminal_state_strategy,
)
def test_wait_converges_on_first_terminal(prefix: List[TaskState], terminal: TaskState
) -> None:
    """
        For any sequence of non-terminal states followed by a
        terminal one, :meth:`TaskHandle.wait` SHALL converge on the
        first terminal state, return a :class:`TaskResult` with
        ``state == terminal``, and report :meth:`is_done` ``True``
        thereafter.
    """
    states = list(prefix) + [terminal]
    session = _make_status_session(states)
    handle = _make_handle(session, task_id="prop")
    aspects = AspectsRest(
        completion_interval=0.0001, completion_timeout=1000
    )

    with patch.object(time, "sleep", return_value=None):
        result = handle.wait(aspects=aspects)

    assert result.state == terminal
    assert result.task_id == "prop"
    assert handle.is_done()
    assert handle._last_observed_state in TERMINAL_STATES
    assert len(session.calls) == len(states)
    return


@given(non_terminal_count=st.integers(min_value=1, max_value=10), constraints={"max_examples": 20})
def test_wait_times_out_on_all_non_terminal_sequence(non_terminal_count: int
) -> None:
    """
        When no terminal state appears in the observed sequence the
        wait loop SHALL raise :class:`TimeoutError` once the
        monotonic clock crosses the deadline.
    """
    states = [TaskState.RUNNING] * non_terminal_count
    session = _make_status_session(states)
    handle = _make_handle(session, task_id="never")
    aspects = AspectsRest(completion_interval=1, completion_timeout=1)

    # Fake clock starts at 0, then immediately jumps past the
    # deadline on the next read.
    clock_values = iter([0.0] + [10.0] * (non_terminal_count + 5))
    with patch.object(time, "sleep", return_value=None), \
         patch.object(time, "monotonic", side_effect=lambda: next(clock_values)):
        with testbase.raises(TimeoutError):
            handle.wait(aspects=aspects)

    assert handle._last_observed_state == TaskState.RUNNING
    return


@given(
constraints={"max_examples": 30},
    running_then_terminal=st.lists(
        _non_terminal_state_strategy, min_size=0, max_size=5
    ),
    terminal=_terminal_state_strategy,
)
def test_is_done_matches_terminal_set_after_wait(running_then_terminal: List[TaskState], terminal: TaskState
) -> None:
    """
        After a successful wait :meth:`is_done` SHALL be ``True``
        iff the last observed state is in :data:`TERMINAL_STATES`.
    """
    states = list(running_then_terminal) + [terminal]
    session = _make_status_session(states)
    handle = _make_handle(session, task_id="prop2")
    aspects = AspectsRest(completion_interval=0.0001, completion_timeout=1000)

    with patch.object(time, "sleep", return_value=None):
        handle.wait(aspects=aspects)

    assert (handle.is_done()
            == (handle._last_observed_state in TERMINAL_STATES))
    return
