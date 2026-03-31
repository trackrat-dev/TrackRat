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
    _find_varint_field,
    extract_mta_track,
    extract_nyct_stop_time_update,
    extract_nyct_trip_descriptor,
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
            assert (
                result == expected_track
            ), f"Expected track '{expected_track}', got '{result}'"


# =========================================================================
# NYCT Subway Extension Tests
# =========================================================================

# NYCT extension: field 1001, wire type 2 (length-delimited)
# Tag varint for (1001 << 3) | 2 = 8010 encodes as [0xCA, 0x3E]
_NYCT_TAG = b"\xca\x3e"


class TestFindVarintField:
    """Tests for the varint field finder."""

    def test_find_existing_field(self):
        """Find a varint field value."""
        # Field 2, wire type 0 (varint), value 1
        data = b"\x10\x01"
        result = _find_varint_field(data, 2)
        assert result == 1

    def test_field_not_found(self):
        """Return None when field doesn't exist."""
        data = b"\x10\x01"
        result = _find_varint_field(data, 99)
        assert result is None

    def test_skip_length_delimited(self):
        """Skip length-delimited fields to find varint target."""
        # Field 1 (string "abc"), then field 3 (varint 42)
        data = b"\x0a\x03abc\x18\x2a"
        result = _find_varint_field(data, 3)
        assert result == 42

    def test_zero_value(self):
        """Zero varint value is found (not confused with missing)."""
        # Field 2, wire type 0, value 0
        data = b"\x10\x00"
        result = _find_varint_field(data, 2)
        assert result == 0

    def test_empty_data(self):
        """Return None for empty input."""
        result = _find_varint_field(b"", 1)
        assert result is None


def _build_nyct_trip_descriptor_extension(
    train_id: str | None = None,
    is_assigned: bool | None = None,
    direction: int | None = None,
) -> bytes:
    """Build raw protobuf bytes for NyctTripDescriptor extension.

    Constructs field 1001 on TripDescriptor containing the NyctTripDescriptor
    sub-message with optional train_id, is_assigned, and direction fields.
    """
    sub_msg = b""
    if train_id is not None:
        tid = train_id.encode("utf-8")
        sub_msg += b"\x0a" + bytes([len(tid)]) + tid  # field 1, string
    if is_assigned is not None:
        sub_msg += b"\x10" + (b"\x01" if is_assigned else b"\x00")  # field 2, bool
    if direction is not None:
        sub_msg += b"\x18" + bytes([direction])  # field 3, varint
    return _NYCT_TAG + bytes([len(sub_msg)]) + sub_msg


def _build_nyct_stop_time_extension(
    scheduled_track: str | None = None,
    actual_track: str | None = None,
) -> bytes:
    """Build raw protobuf bytes for NyctStopTimeUpdate extension."""
    sub_msg = b""
    if scheduled_track is not None:
        st = scheduled_track.encode("utf-8")
        sub_msg += b"\x0a" + bytes([len(st)]) + st  # field 1, string
    if actual_track is not None:
        at = actual_track.encode("utf-8")
        sub_msg += b"\x12" + bytes([len(at)]) + at  # field 2, string
    return _NYCT_TAG + bytes([len(sub_msg)]) + sub_msg


def _make_trip_update_with_nyct_extension(
    trip_id: str = "070200_6..N",
    route_id: str = "6",
    ext_bytes: bytes | None = None,
) -> gtfs_realtime_pb2.TripUpdate:
    """Create a TripUpdate with NyctTripDescriptor extension on TripDescriptor."""
    tu = gtfs_realtime_pb2.TripUpdate()
    tu.trip.trip_id = trip_id
    tu.trip.route_id = route_id

    if ext_bytes is None:
        return tu

    # Serialize TripDescriptor, append extension, re-parse into TripUpdate
    trip_raw = tu.trip.SerializeToString()
    combined_trip = trip_raw + ext_bytes
    tu.trip.ParseFromString(combined_trip)
    return tu


class TestExtractNyctTripDescriptor:
    """Tests for NYC Subway NyctTripDescriptor extraction."""

    def test_full_descriptor(self):
        """Extract all fields: train_id, is_assigned, direction."""
        ext = _build_nyct_trip_descriptor_extension(
            train_id="01 0123+ PEL/BBR",
            is_assigned=True,
            direction=3,  # SOUTH
        )
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result is not None
        assert result["train_id"] == "01 0123+ PEL/BBR"
        assert result["is_assigned"] is True
        assert result["direction"] == 3

    def test_train_id_only(self):
        """Extract when only train_id is present."""
        ext = _build_nyct_trip_descriptor_extension(train_id="05 1234")
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result is not None
        assert result["train_id"] == "05 1234"
        assert result["is_assigned"] is False  # default
        assert result["direction"] is None

    def test_is_assigned_false(self):
        """Explicitly false is_assigned."""
        ext = _build_nyct_trip_descriptor_extension(
            train_id="01 0001", is_assigned=False
        )
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result is not None
        assert result["is_assigned"] is False

    def test_direction_north(self):
        """Direction NORTH = 1."""
        ext = _build_nyct_trip_descriptor_extension(direction=1)
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result["direction"] == 1

    def test_direction_east(self):
        """Direction EAST = 2 (used by L train, shuttles)."""
        ext = _build_nyct_trip_descriptor_extension(direction=2)
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result["direction"] == 2

    def test_direction_west(self):
        """Direction WEST = 4."""
        ext = _build_nyct_trip_descriptor_extension(direction=4)
        tu = _make_trip_update_with_nyct_extension(ext_bytes=ext)
        result = extract_nyct_trip_descriptor(tu)
        assert result["direction"] == 4

    def test_no_extension(self):
        """Return None when no NYCT extension present."""
        tu = _make_trip_update_with_nyct_extension(ext_bytes=None)
        result = extract_nyct_trip_descriptor(tu)
        assert result is None

    def test_serialize_error(self):
        """Return None if serialization fails."""

        class BadTU:
            class trip:
                @staticmethod
                def SerializeToString():
                    raise RuntimeError("fail")

        assert extract_nyct_trip_descriptor(BadTU()) is None


class TestExtractNyctStopTimeUpdate:
    """Tests for NYC Subway NyctStopTimeUpdate extraction."""

    def test_both_tracks(self):
        """Extract both scheduled and actual track."""
        ext = _build_nyct_stop_time_extension(scheduled_track="2", actual_track="1")
        stu = _make_stu_with_extension(ext_bytes=ext)
        result = extract_nyct_stop_time_update(stu)
        assert result is not None
        assert result["scheduled_track"] == "2"
        assert result["actual_track"] == "1"

    def test_scheduled_track_only(self):
        """Extract when only scheduled_track is present."""
        ext = _build_nyct_stop_time_extension(scheduled_track="4")
        stu = _make_stu_with_extension(ext_bytes=ext)
        result = extract_nyct_stop_time_update(stu)
        assert result is not None
        assert result["scheduled_track"] == "4"
        assert result["actual_track"] is None

    def test_actual_track_only(self):
        """Extract when only actual_track is present."""
        ext = _build_nyct_stop_time_extension(actual_track="3")
        stu = _make_stu_with_extension(ext_bytes=ext)
        result = extract_nyct_stop_time_update(stu)
        assert result is not None
        assert result["scheduled_track"] is None
        assert result["actual_track"] == "3"

    def test_no_extension(self):
        """Return None when no NYCT extension present."""
        stu = _make_stu_with_extension(ext_bytes=None)
        result = extract_nyct_stop_time_update(stu)
        assert result is None

    def test_empty_extension(self):
        """Handle extension with empty sub-message."""
        ext = _NYCT_TAG + b"\x00"  # field 1001, length 0
        stu = _make_stu_with_extension(ext_bytes=ext)
        result = extract_nyct_stop_time_update(stu)
        assert result is not None
        assert result["scheduled_track"] is None
        assert result["actual_track"] is None

    def test_serialize_error(self):
        """Return None if serialization fails."""

        class BadSTU:
            def SerializeToString(self):
                raise RuntimeError("fail")

        assert extract_nyct_stop_time_update(BadSTU()) is None
