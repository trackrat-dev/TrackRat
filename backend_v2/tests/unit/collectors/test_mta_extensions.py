"""
Unit tests for MTA GTFS-RT extension parser.

Tests extraction of track assignments from the MtaRailroadStopTimeUpdate
extension (field 1005) embedded in StopTimeUpdate protobuf messages.
"""

import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.mta_extensions import (
    _decode_varint,
    _find_length_delimited_field,
    extract_mta_track,
)

# MTA Railroad extension: field 1005, wire type 2 (length-delimited)
# Tag varint for (1005 << 3) | 2 = 8042 encodes as [0xEA, 0x3E]
_EXT_TAG = b"\xea\x3e"


def _build_extension_bytes(track: str) -> bytes:
    """Build raw protobuf bytes for MtaRailroadStopTimeUpdate extension.

    Constructs: field 1005 (length-delimited) containing a sub-message
    with field 1 (track string).
    """
    track_bytes = track.encode("utf-8")
    # Sub-message: field 1, wire type 2 (string)
    sub_msg = b"\x0a" + bytes([len(track_bytes)]) + track_bytes
    # Extension: field 1005, wire type 2 (length-delimited)
    return _EXT_TAG + bytes([len(sub_msg)]) + sub_msg


def _build_extension_with_status(track: str, status: str) -> bytes:
    """Build extension bytes with both track (field 1) and trainStatus (field 2)."""
    track_bytes = track.encode("utf-8")
    status_bytes = status.encode("utf-8")
    # Field 1 (track)
    track_field = b"\x0a" + bytes([len(track_bytes)]) + track_bytes
    # Field 2 (trainStatus): tag = (2 << 3) | 2 = 18 = 0x12
    status_field = b"\x12" + bytes([len(status_bytes)]) + status_bytes
    sub_msg = track_field + status_field
    return _EXT_TAG + bytes([len(sub_msg)]) + sub_msg


def _make_stu_with_extension(
    stop_id: str = "102",
    arrival_time: int = 1706123456,
    delay: int = 0,
    ext_bytes: bytes | None = None,
) -> gtfs_realtime_pb2.TripUpdate.StopTimeUpdate:
    """Create a real protobuf StopTimeUpdate with optional MTA extension bytes.

    Builds a standard message, serializes it, appends extension bytes,
    and parses back. The protobuf library preserves unknown fields, so
    the extension data survives the round-trip.
    """
    stu = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate()
    stu.stop_id = stop_id
    stu.arrival.time = arrival_time
    stu.arrival.delay = delay
    base = stu.SerializeToString()

    if ext_bytes is None:
        return stu

    # Append extension and re-parse
    combined = base + ext_bytes
    stu_with_ext = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate()
    stu_with_ext.ParseFromString(combined)
    return stu_with_ext


class TestDecodeVarint:
    """Tests for the protobuf varint decoder."""

    def test_single_byte(self):
        """Values < 128 use a single byte."""
        val, pos = _decode_varint(b"\x07", 0)
        assert val == 7
        assert pos == 1

    def test_two_bytes(self):
        """Values 128-16383 use two bytes."""
        # 300 = 0b100101100 → varint: [0xAC, 0x02]
        val, pos = _decode_varint(b"\xac\x02", 0)
        assert val == 300
        assert pos == 2

    def test_extension_tag(self):
        """Varint for the MTA extension tag (8042)."""
        val, pos = _decode_varint(b"\xea\x3e", 0)
        assert val == 8042
        assert pos == 2

    def test_at_offset(self):
        """Decoding starting at a non-zero position."""
        val, pos = _decode_varint(b"\xff\x07\x03", 2)
        assert val == 3
        assert pos == 3


class TestFindLengthDelimitedField:
    """Tests for finding length-delimited fields in raw protobuf bytes."""

    def test_find_existing_field(self):
        """Find a known length-delimited field."""
        # Field 1, wire type 2, length 3, data "abc"
        data = b"\x0a\x03abc"
        result = _find_length_delimited_field(data, 1)
        assert result == b"abc"

    def test_field_not_found(self):
        """Return None when field doesn't exist."""
        data = b"\x0a\x03abc"
        result = _find_length_delimited_field(data, 99)
        assert result is None

    def test_empty_data(self):
        """Return None for empty input."""
        result = _find_length_delimited_field(b"", 1)
        assert result is None

    def test_skip_varint_field(self):
        """Correctly skip over varint fields to find target."""
        # Field 3, wire type 0 (varint), value 42
        # Then field 1, wire type 2, length 2, data "ok"
        data = b"\x18\x2a\x0a\x02ok"
        result = _find_length_delimited_field(data, 1)
        assert result == b"ok"

    def test_extension_field_number(self):
        """Find field 1005 (the MTA extension field number)."""
        ext_data = _build_extension_bytes("7")
        # The top-level field 1005 contains a sub-message
        result = _find_length_delimited_field(ext_data, 1005)
        assert result is not None
        assert result == b"\x0a\x01\x37"  # sub-message with track "7"


class TestExtractMtaTrack:
    """Tests for track extraction from MTA Railroad extension."""

    def test_single_digit_track(self):
        """Extract a single digit track like '7'."""
        ext = _build_extension_bytes("7")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "7"

    def test_two_digit_track(self):
        """Extract a two-digit track like '12'."""
        ext = _build_extension_bytes("12")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "12"

    def test_three_digit_track(self):
        """Extract a three-digit track like '201' (LIRR Grand Central Madison)."""
        ext = _build_extension_bytes("201")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "201"

    def test_alphanumeric_track(self):
        """Extract an alphanumeric track like '1A' (LIRR branch stations)."""
        ext = _build_extension_bytes("1A")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "1A"

    def test_alpha_track(self):
        """Extract a purely alphabetic track like 'A' (LIRR small stations)."""
        ext = _build_extension_bytes("A")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "A"

    def test_no_extension(self):
        """Return None when no MTA extension is present."""
        stu = _make_stu_with_extension(ext_bytes=None)
        assert extract_mta_track(stu) is None

    def test_empty_track_string(self):
        """Return None for empty track string in extension."""
        # Extension with empty sub-message field 1
        sub_msg = b"\x0a\x00"  # field 1, wire type 2, length 0
        ext = _EXT_TAG + bytes([len(sub_msg)]) + sub_msg
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) is None

    def test_extension_with_status(self):
        """Track is extracted correctly when trainStatus field is also present."""
        ext = _build_extension_with_status("13", "On-Time")
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) == "13"

    def test_extension_with_only_status_no_track(self):
        """Return None when extension has trainStatus but no track field."""
        # Only field 2 (trainStatus), no field 1 (track)
        status_bytes = b"On-Time"
        sub_msg = b"\x12" + bytes([len(status_bytes)]) + status_bytes
        ext = _EXT_TAG + bytes([len(sub_msg)]) + sub_msg
        stu = _make_stu_with_extension(ext_bytes=ext)
        assert extract_mta_track(stu) is None

    def test_serialize_error_returns_none(self):
        """Return None if the object can't be serialized."""

        class BadSTU:
            def SerializeToString(self):
                raise RuntimeError("serialize failed")

        assert extract_mta_track(BadSTU()) is None

    def test_preserves_standard_fields(self):
        """Verify standard protobuf fields are unaffected by extension parsing."""
        ext = _build_extension_bytes("42")
        stu = _make_stu_with_extension(
            stop_id="1", arrival_time=1706000000, delay=120, ext_bytes=ext
        )
        # Standard fields should still be readable
        assert stu.stop_id == "1"
        assert stu.arrival.time == 1706000000
        assert stu.arrival.delay == 120
        # And track should be extracted
        assert extract_mta_track(stu) == "42"

    def test_multiple_tracks_in_feed(self):
        """Extract different tracks from different StopTimeUpdates."""
        tracks = ["15", "16", "201", "A", "1B"]
        for expected_track in tracks:
            ext = _build_extension_bytes(expected_track)
            stu = _make_stu_with_extension(ext_bytes=ext)
            result = extract_mta_track(stu)
            assert result == expected_track, (
                f"Expected track '{expected_track}', got '{result}'"
            )
