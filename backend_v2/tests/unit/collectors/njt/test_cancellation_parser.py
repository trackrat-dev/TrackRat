"""Tests for NJT cancellation alert parser."""

import pytest

from trackrat.collectors.njt.cancellation_parser import (
    CancellationAlert,
    parse_cancellation_alerts,
)


class TestParseCancellationAlerts:
    """Tests for parse_cancellation_alerts function."""

    def test_parses_nec_cancellation_with_reason_and_alternative(self):
        """Test parsing a complete NEC cancellation message."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": (
                    "NEC train #3735, the 7:43 PM departure from PSNY scheduled to "
                    "arrive at Jersey Ave at 8:50 PM, is cancelled due to equipment "
                    "availability. Please take train #3883, the 8:07 PM departure from PSNY."
                ),
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.train_id == "3735"
        assert alert.line_code == "NE"
        assert alert.scheduled_time == "7:43 PM"
        assert alert.reason == "equipment availability"
        assert alert.alternative_train_id == "3883"

    def test_parses_njcl_cancellation(self):
        """Test parsing NJCL cancellation message."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": (
                    "NJCL train #3515, the 6:29 PM departure from PSNY scheduled to "
                    "arrive at South Amboy at 7:41 PM, is cancelled due to equipment "
                    "availability resulting from a mechanical issue."
                ),
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.train_id == "3515"
        assert alert.line_code == "NC"
        assert alert.scheduled_time == "6:29 PM"
        assert "equipment availability" in alert.reason

    def test_parses_morris_essex_cancellation(self):
        """Test parsing Morris & Essex line cancellation."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": (
                    "Morris and Essex Line train #6359, the 6:50 PM departure from PSNY, "
                    "scheduled to arrive in Summit at 7:41 PM, is cancelled due to "
                    "equipment availability."
                ),
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.train_id == "6359"
        assert alert.line_code == "ME"

    def test_ignores_delay_messages(self):
        """Test that delay messages are not parsed as cancellations."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": (
                    "NEC train #3873, the 7:51 PM arrival to Trenton is up to 45 minutes "
                    "late due to congestion from earlier weather-related overhead wire inspection."
                ),
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 0

    def test_handles_empty_messages(self):
        """Test handling of empty message list."""
        alerts = parse_cancellation_alerts([])
        assert alerts == []

    def test_handles_none_msg_text(self):
        """Test handling of message without MSG_TEXT."""
        messages = [{"MSG_TYPE": "banner"}]

        alerts = parse_cancellation_alerts(messages)

        assert alerts == []

    def test_parses_multiple_cancellations(self):
        """Test parsing multiple cancellation alerts."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train #3735 is cancelled due to equipment issues.",
            },
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train #3873 is up to 35 minutes late.",  # Not cancelled
            },
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NJCL train #3515 has been cancelled due to mechanical issue.",
            },
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 2
        train_ids = {a.train_id for a in alerts}
        assert train_ids == {"3735", "3515"}

    def test_parses_train_id_without_hash(self):
        """Test parsing train ID when # is missing."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train 3735 is cancelled.",
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 1
        assert alerts[0].train_id == "3735"

    def test_parses_has_been_cancelled_variant(self):
        """Test parsing 'has been cancelled' phrasing."""
        messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train #3735 has been cancelled due to weather.",
            }
        ]

        alerts = parse_cancellation_alerts(messages)

        assert len(alerts) == 1
        assert alerts[0].train_id == "3735"
        assert alerts[0].reason == "weather"


class TestCancellationAlert:
    """Tests for CancellationAlert dataclass."""

    def test_alert_stores_all_fields(self):
        """Test that CancellationAlert stores all provided fields."""
        alert = CancellationAlert(
            train_id="3735",
            line_code="NE",
            scheduled_time="7:43 PM",
            reason="equipment availability",
            alternative_train_id="3883",
            raw_message="Original message text",
        )

        assert alert.train_id == "3735"
        assert alert.line_code == "NE"
        assert alert.scheduled_time == "7:43 PM"
        assert alert.reason == "equipment availability"
        assert alert.alternative_train_id == "3883"
        assert alert.raw_message == "Original message text"

    def test_alert_allows_none_for_optional_fields(self):
        """Test that optional fields can be None."""
        alert = CancellationAlert(
            train_id="3735",
            line_code=None,
            scheduled_time=None,
            reason=None,
            alternative_train_id=None,
            raw_message="Train 3735 is cancelled.",
        )

        assert alert.train_id == "3735"
        assert alert.line_code is None
        assert alert.scheduled_time is None
        assert alert.reason is None
        assert alert.alternative_train_id is None
