"""Parser for NJT cancellation alerts from STATIONMSGS.

This module extracts train cancellation information from NJ Transit's
station message alerts, which are embedded in the getDepartureVisionData
API response.
"""

import re
from dataclasses import dataclass

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class CancellationAlert:
    """Parsed cancellation information from NJT station message."""

    train_id: str
    line_code: str | None
    scheduled_time: str | None
    reason: str | None
    alternative_train_id: str | None
    raw_message: str


# Pattern to extract train cancellation info from NJT alert messages
# Examples:
#   "NEC train #3735, the 7:43 PM departure from PSNY... is cancelled due to equipment availability"
#   "NJCL train #3515, the 6:29 PM departure from PSNY... is cancelled"
#   "Morris and Essex train #665... is cancelled due to equipment availability"
_CANCELLATION_PATTERN = re.compile(
    r"train\s*#?(\d+)"  # Group 1: Train ID (required)
    r".*?"  # Skip intervening text
    r"(?:is|has been)\s+cancell?ed"  # Cancellation phrase (required)
    r"(?:\s+due\s+to\s+([^.]+))?"  # Group 2: Optional reason
    , re.IGNORECASE | re.DOTALL
)

# Separate pattern to extract scheduled time (e.g., "the 7:43 PM departure")
_TIME_PATTERN = re.compile(
    r"the\s+(\d{1,2}:\d{2}\s*(?:AM|PM))\s+departure",
    re.IGNORECASE
)

# Pattern to extract alternative train suggestion
_ALTERNATIVE_PATTERN = re.compile(
    r"(?:please\s+)?take\s+train\s*#?(\d+)",
    re.IGNORECASE
)

# Line name to code mapping
_LINE_NAME_TO_CODE = {
    "nec": "NE",
    "northeast": "NE",
    "njcl": "NC",
    "coast": "NC",
    "m&e": "ME",
    "morris": "ME",
    "essex": "ME",
    "raritan": "RV",
    "bergen": "BL",
    "main": "ML",
    "pascack": "PV",
    "montclair": "MC",
    "boonton": "MC",
    "gladstone": "GL",
    "atlantic": "AC",
}


def parse_cancellation_alerts(station_messages: list[dict]) -> list[CancellationAlert]:
    """Parse STATIONMSGS array for cancellation alerts.

    Args:
        station_messages: List of message dicts from STATIONMSGS.
            Each dict should have at least MSG_TEXT field.

    Returns:
        List of parsed CancellationAlert objects for cancelled trains.
    """
    if not station_messages:
        return []

    alerts = []

    for msg in station_messages:
        msg_text = msg.get("MSG_TEXT", "")
        if not msg_text:
            continue

        # Skip non-cancellation messages (quick check before regex)
        if "cancell" not in msg_text.lower():
            continue

        # Try to extract line code from message prefix
        line_code = _extract_line_code(msg_text)

        match = _CANCELLATION_PATTERN.search(msg_text)
        if match:
            train_id = match.group(1)
            reason = match.group(2).strip() if match.group(2) else None

            # Extract scheduled time with separate pattern
            time_match = _TIME_PATTERN.search(msg_text)
            scheduled_time = time_match.group(1) if time_match else None

            # Extract alternative train suggestion with separate pattern
            alt_match = _ALTERNATIVE_PATTERN.search(msg_text)
            alternative = alt_match.group(1) if alt_match else None

            alerts.append(CancellationAlert(
                train_id=train_id,
                line_code=line_code,
                scheduled_time=scheduled_time,
                reason=reason,
                alternative_train_id=alternative,
                raw_message=msg_text,
            ))

            logger.debug(
                "parsed_cancellation_alert",
                train_id=train_id,
                line_code=line_code,
                scheduled_time=scheduled_time,
                reason=reason,
            )
        else:
            # Log messages that mention "cancelled" but don't match our pattern
            # This helps us identify new message formats
            logger.warning(
                "unparseable_cancellation_message",
                message=msg_text[:200],
            )

    return alerts


def _extract_line_code(message: str) -> str | None:
    """Extract line code from the beginning of a cancellation message.

    Args:
        message: Full message text

    Returns:
        Two-character line code or None
    """
    # Check first ~30 chars for line name
    prefix = message[:30].lower()

    for name, code in _LINE_NAME_TO_CODE.items():
        if name in prefix:
            return code

    return None
