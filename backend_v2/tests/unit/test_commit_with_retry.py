"""
Tests for commit_with_retry in scheduler_utils.

Verifies retry behavior on transient PostgreSQL errors, including
rollback before retry and proper re-raise on non-transient errors.
"""

from unittest.mock import Mock, call, patch

import pytest

from trackrat.utils.scheduler_utils import commit_with_retry


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_succeeds_on_first_attempt(mock_sleep):
    """Normal commit should succeed without retries."""
    session = Mock()
    commit_with_retry(session)

    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    mock_sleep.assert_not_called()


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_retries_on_serialization_failure(mock_sleep):
    """Serialization failure should trigger rollback + retry."""
    session = Mock()
    session.commit.side_effect = [
        Exception("serialization failure"),
        None,  # succeeds on retry
    ]

    commit_with_retry(session)

    assert session.commit.call_count == 2
    session.rollback.assert_called_once()
    mock_sleep.assert_called_once()


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_retries_on_deadlock(mock_sleep):
    """Deadlock detected should trigger rollback + retry."""
    session = Mock()
    session.commit.side_effect = [
        Exception("deadlock detected"),
        None,
    ]

    commit_with_retry(session)

    assert session.commit.call_count == 2
    session.rollback.assert_called_once()


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_retries_on_statement_timeout(mock_sleep):
    """Statement timeout (canceling statement) should trigger retry."""
    session = Mock()
    session.commit.side_effect = [
        Exception("canceling statement due to user request"),
        None,
    ]

    commit_with_retry(session)

    assert session.commit.call_count == 2
    session.rollback.assert_called_once()


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_raises_on_non_transient_error(mock_sleep):
    """Non-transient errors (e.g., integrity violation) should raise immediately."""
    session = Mock()
    session.commit.side_effect = Exception("unique constraint violated")

    with pytest.raises(Exception, match="unique constraint violated"):
        commit_with_retry(session)

    session.commit.assert_called_once()
    session.rollback.assert_not_called()


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_exhausts_retries_then_raises(mock_sleep):
    """After max_retries transient failures, the last error should be raised."""
    session = Mock()
    session.commit.side_effect = Exception("deadlock detected")

    with pytest.raises(Exception, match="deadlock detected"):
        commit_with_retry(session, max_retries=3)

    # 3 attempts total: first + 2 retries
    assert session.commit.call_count == 3
    # Rollback called for retries 1 and 2 (not the final raise)
    assert session.rollback.call_count == 2


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_rollback_called_before_each_retry(mock_sleep):
    """Session.rollback() must be called BEFORE sleep on each retry.
    PostgreSQL rejects commands on an aborted transaction until rollback."""
    session = Mock()
    call_order = []

    def track_rollback():
        call_order.append("rollback")

    def track_sleep(duration):
        call_order.append(f"sleep({duration})")

    session.rollback.side_effect = track_rollback
    mock_sleep.side_effect = track_sleep
    session.commit.side_effect = [
        Exception("serialization failure"),
        None,
    ]

    commit_with_retry(session)

    assert call_order == [
        "rollback",
        "sleep(0.5)",
    ], f"Expected rollback before sleep, got: {call_order}"


@patch("trackrat.utils.scheduler_utils.time.sleep")
def test_backoff_increases_with_retries(mock_sleep):
    """Sleep duration should increase with each retry."""
    session = Mock()
    session.commit.side_effect = [
        Exception("deadlock detected"),
        Exception("deadlock detected"),
        None,
    ]

    commit_with_retry(session, max_retries=3)

    # sleep(0.5 * 1), sleep(0.5 * 2)
    assert mock_sleep.call_args_list == [call(0.5), call(1.0)]
