"""
    .. module:: test_taskhandle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit and property tests for the reusable
        :class:`TaskHandle` polling base class.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


import unittest

from typing import List, Optional
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from ccai.errors.exceptions import SemanticError

from ccai.restclient.base.aspectsrest import AspectsRest
from ccai.restclient.base.taskhandle import (
    TERMINAL_STATES,
    TaskHandle,
    TaskResult,
    TaskState,
)


class _ClientStub:
    """
        Minimal client stand-in carrying just the ``_session`` attribute
        used by :class:`TaskHandle`.
    """

    def __init__(self, session: object = None) -> None:
        self._session = session
        return


def _make_status_session(states: List[TaskState], error_message: Optional[str] = None) -> MagicMock:
    """
        Builds a session whose ``get`` returns a sequence of programmed
        status payloads.

        :param states: Sequence of states to return.
        :param error_message: Optional error string surfaced via the
            payload's ``"error"`` field.

        :returns: A configured :class:`MagicMock` session.
    """
    responses: List[MagicMock] = []
    for state in states:
        payload = {"state": state.value}
        if error_message is not None and state == TaskState.FAILED:
            payload["error"] = error_message
        response = MagicMock()
        response.json.return_value = payload
        responses.append(response)

    session = MagicMock()
    session.get.side_effect = responses
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


class TestConstruction(unittest.TestCase):

    def test_construction_and_task_id(self) -> None:
        handle = TaskHandle(
            task_id="task-1",
            client=_ClientStub(),
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        self.assertEqual(handle.task_id(), "task-1")
        return

    def test_is_done_false_before_wait(self) -> None:
        handle = TaskHandle(
            task_id="task-1",
            client=_ClientStub(),
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        self.assertFalse(handle.is_done())
        return


class TestWaitSuccess(unittest.TestCase):

    def test_wait_succeeded_cycle(self) -> None:
        session = _make_status_session(
            [TaskState.PENDING, TaskState.RUNNING, TaskState.SUCCEEDED]
        )
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-1",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            result = handle.wait(aspects=aspects)

        self.assertIsInstance(result, TaskResult)
        self.assertEqual(result.state, TaskState.SUCCEEDED)
        self.assertEqual(result.task_id, "task-1")
        self.assertTrue(handle.is_done())
        return

    def test_wait_failed_cycle_returns_taskresult_with_error(self) -> None:
        session = _make_status_session(
            [TaskState.RUNNING, TaskState.FAILED], error_message="boom"
        )
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-2",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
            error_extractor=_error_extractor,
        )
        aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            result = handle.wait(aspects=aspects)

        self.assertEqual(result.state, TaskState.FAILED)
        self.assertEqual(result.error, "boom")
        self.assertTrue(handle.is_done())
        return

    def test_wait_cancelled_cycle(self) -> None:
        session = _make_status_session(
            [TaskState.RUNNING, TaskState.CANCELLED]
        )
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-3",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=0.0001, completion_timeout=10)

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            result = handle.wait(aspects=aspects)

        self.assertEqual(result.state, TaskState.CANCELLED)
        return


class TestWaitTimeout(unittest.TestCase):

    def test_timeout_raises_with_task_id_and_state(self) -> None:
        session = _make_status_session(
            [TaskState.RUNNING, TaskState.RUNNING, TaskState.RUNNING]
        )
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="never-finishes",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=1, completion_timeout=2)

        # Fake monotonic clock that advances by `interval` each call so
        # the deadline is crossed after two iterations.
        ticker = iter([0.0, 1.0, 2.5])
        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ), patch(
            "ccai.restclient.base.taskhandle.time.monotonic",
            side_effect=lambda: next(ticker),
        ):
            error: Optional[BaseException] = None
            try:
                handle.wait(aspects=aspects)
            except TimeoutError as terr:
                error = terr

        self.assertIsNotNone(error)
        self.assertIn("never-finishes", str(error))
        self.assertIn("RUNNING", str(error))
        return


class TestWaitAspectsValidation(unittest.TestCase):

    def test_negative_interval_raises(self) -> None:
        handle = TaskHandle(
            task_id="t",
            client=_ClientStub(),
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=0, completion_timeout=10)
        with self.assertRaises(SemanticError):
            handle.wait(aspects=aspects)
        return

    def test_negative_timeout_raises(self) -> None:
        handle = TaskHandle(
            task_id="t",
            client=_ClientStub(),
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=1, completion_timeout=0)
        with self.assertRaises(SemanticError):
            handle.wait(aspects=aspects)
        return


class TestCancel(unittest.TestCase):

    def test_with_url_posts_and_returns_none(self) -> None:
        session = MagicMock()
        session.post.return_value.status_code = 204
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-1",
            client=client,
            status_url="https://host/status",
            cancel_url="https://host/cancel",
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_timeout=5)

        result = handle.cancel(aspects=aspects)

        self.assertIsNone(result)
        session.post.assert_called_once()
        kwargs = session.post.call_args.kwargs
        self.assertEqual(kwargs["url"], "https://host/cancel")
        self.assertEqual(kwargs["timeout"], 5)
        return

    def test_non_success_response_raises(self) -> None:
        """
            Regression: cancel() must surface a non-2xx cancel response as
            an error rather than silently reporting success.
        """
        session = MagicMock()
        session.post.return_value.status_code = 500
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-1",
            client=client,
            status_url="https://host/status",
            cancel_url="https://host/cancel",
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_timeout=5)
        with self.assertRaises(RuntimeError):
            handle.cancel(aspects=aspects)
        return

    def test_without_url_raises_notimplemented(self) -> None:
        client = _ClientStub(session=MagicMock())
        handle = TaskHandle(
            task_id="task-1",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest()
        with self.assertRaises(NotImplementedError):
            handle.cancel(aspects=aspects)
        return

    def test_after_terminal_state_is_noop(self) -> None:
        session = MagicMock()
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-1",
            client=client,
            status_url="https://host/status",
            cancel_url="https://host/cancel",
            state_extractor=_state_extractor,
        )
        # Simulate completed wait
        handle._last_observed_state = TaskState.SUCCEEDED

        aspects = AspectsRest()
        result = handle.cancel(aspects=aspects)

        self.assertIsNone(result)
        session.post.assert_not_called()
        return


# -------------------------------------------------------------------------
# Property-based tests covering poll-loop convergence under arbitrary
# state sequences.
# -------------------------------------------------------------------------

_terminal_state_strategy = st.sampled_from(
    [TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED]
)
_non_terminal_state_strategy = st.sampled_from(
    [TaskState.PENDING, TaskState.RUNNING]
)


class TestTaskHandleProperties(unittest.TestCase):

    @settings(max_examples=50, deadline=None)
    @given(
        prefix=st.lists(_non_terminal_state_strategy, min_size=0, max_size=20),
        terminal=_terminal_state_strategy,
    )
    def test_wait_converges_on_first_terminal(
        self, prefix: List[TaskState], terminal: TaskState
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
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="prop",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(
            completion_interval=0.0001, completion_timeout=1000
        )

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            result = handle.wait(aspects=aspects)

        self.assertEqual(result.state, terminal)
        self.assertEqual(result.task_id, "prop")
        self.assertTrue(handle.is_done())
        self.assertIn(handle._last_observed_state, TERMINAL_STATES)
        self.assertEqual(session.get.call_count, len(states))
        return

    @settings(max_examples=20, deadline=None)
    @given(non_terminal_count=st.integers(min_value=1, max_value=10))
    def test_wait_times_out_on_all_non_terminal_sequence(
        self, non_terminal_count: int
    ) -> None:
        """
            When no terminal state appears in the observed sequence the
            wait loop SHALL raise :class:`TimeoutError` once the
            monotonic clock crosses the deadline.
        """
        states = [TaskState.RUNNING] * non_terminal_count
        session = _make_status_session(states)
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="never",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=1, completion_timeout=1)

        # Fake clock starts at 0, then immediately jumps past the
        # deadline on the next read.
        clock_values = iter([0.0] + [10.0] * (non_terminal_count + 5))
        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ), patch(
            "ccai.restclient.base.taskhandle.time.monotonic",
            side_effect=lambda: next(clock_values),
        ):
            with self.assertRaises(TimeoutError):
                handle.wait(aspects=aspects)

        self.assertEqual(handle._last_observed_state, TaskState.RUNNING)
        return

    @settings(max_examples=30, deadline=None)
    @given(
        running_then_terminal=st.lists(
            _non_terminal_state_strategy, min_size=0, max_size=5
        ),
        terminal=_terminal_state_strategy,
    )
    def test_is_done_matches_terminal_set_after_wait(
        self, running_then_terminal: List[TaskState], terminal: TaskState
    ) -> None:
        """
            After a successful wait :meth:`is_done` SHALL be ``True``
            iff the last observed state is in :data:`TERMINAL_STATES`.
        """
        states = list(running_then_terminal) + [terminal]
        session = _make_status_session(states)
        handle = TaskHandle(
            task_id="prop2",
            client=_ClientStub(session=session),
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(completion_interval=0.0001, completion_timeout=1000)

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            handle.wait(aspects=aspects)

        self.assertEqual(
            handle.is_done(),
            handle._last_observed_state in TERMINAL_STATES,
        )
        return


class TestFetchStatusTimeout(unittest.TestCase):
    """
        Regression tests for audit finding F-H7: ``_fetch_status`` issued
        ``session.get`` with no timeout, so a hung status endpoint blocked
        ``wait()`` forever and defeated ``aspects.completion_timeout``.
    """

    def test_fetch_status_passes_connection_timeout(self) -> None:
        """
            Every status poll must pass ``aspects.connection_timeout`` as
            the per-request timeout to ``session.get``.
        """
        session = _make_status_session([TaskState.SUCCEEDED])
        client = _ClientStub(session=session)
        handle = TaskHandle(
            task_id="task-t",
            client=client,
            status_url="https://host/status",
            cancel_url=None,
            state_extractor=_state_extractor,
        )
        aspects = AspectsRest(
            completion_interval=0.0001,
            completion_timeout=10,
            connection_timeout=7,
        )

        with patch(
            "ccai.restclient.base.taskhandle.time.sleep", return_value=None
        ):
            handle.wait(aspects=aspects)

        session.get.assert_called_once()
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 7)
        return


class TestCanonicalTaskState(unittest.TestCase):
    """
        Regression test for audit finding F-H6: the ImportError fallback
        defined ``TaskState`` as a string ``Enum`` while the canonical type
        is an ``IntEnum`` -- a value-incompatible silent divergence.
    """

    def test_taskstate_is_canonical_intenum(self) -> None:
        """
            ``taskhandle.TaskState`` must be the canonical
            ``ccai.interfaces.itaskhandle.TaskState`` IntEnum.
        """
        from enum import IntEnum
        from ccai.interfaces.itaskhandle import TaskState as CanonicalTaskState

        self.assertIs(TaskState, CanonicalTaskState)
        self.assertTrue(issubclass(TaskState, IntEnum))
        self.assertEqual(int(TaskState.SUCCEEDED), 3)
        return


if __name__ == "__main__":
    unittest.main()
