"""
MTA GTFS-RT extension parser for LIRR and Metro-North feeds.

MTA's railroad feeds include a custom protobuf extension (field 1005) on
TripUpdate.StopTimeUpdate containing track assignment and train status:

    extend transit_realtime.TripUpdate.StopTimeUpdate {
        optional MtaRailroadStopTimeUpdate mta_railroad_stop_time_update = 1005;
    }

    message MtaRailroadStopTimeUpdate {
        optional string track = 1;
        optional string trainStatus = 2;
    }

Since the standard gtfs-realtime-bindings package doesn't include MTA's
extensions, we extract the data directly from the serialized protobuf bytes.

Reference: https://github.com/OneBusAway/onebusaway-gtfs-realtime-api/blob/
    master/src/main/proto/com/google/transit/realtime/gtfs-realtime-MTARR.proto
"""

import logging

logger = logging.getLogger(__name__)

# MTA Railroad extension field numbers
_EXTENSION_FIELD = 1005
_TRACK_FIELD = 1

# Protobuf wire types
_WIRE_VARINT = 0
_WIRE_64BIT = 1
_WIRE_LENGTH_DELIMITED = 2
_WIRE_32BIT = 5


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a protobuf varint starting at pos. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
    return result, pos


def _find_length_delimited_field(data: bytes, target_field: int) -> bytes | None:
    """Find and return the raw bytes of a length-delimited protobuf field."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _decode_varint(data, pos)
            field_number = tag >> 3
            wire_type = tag & 0x07

            if wire_type == _WIRE_VARINT:
                _, pos = _decode_varint(data, pos)
            elif wire_type == _WIRE_64BIT:
                pos += 8
            elif wire_type == _WIRE_LENGTH_DELIMITED:
                length, pos = _decode_varint(data, pos)
                if field_number == target_field:
                    return data[pos : pos + length]
                pos += length
            elif wire_type == _WIRE_32BIT:
                pos += 4
            else:
                break
        except (IndexError, ValueError):
            break
    return None


def extract_mta_track(stu: object) -> str | None:
    """Extract track assignment from an MTA Railroad GTFS-RT StopTimeUpdate.

    Parses the MtaRailroadStopTimeUpdate extension (field 1005) to get the
    track string. Returns None if the extension is absent or empty.

    Args:
        stu: A gtfs_realtime_pb2.TripUpdate.StopTimeUpdate protobuf message.

    Returns:
        Track string (e.g., "7", "1A", "201") or None if not available.
    """
    try:
        raw = stu.SerializeToString()
    except Exception:
        return None

    # Find extension field 1005 (length-delimited sub-message)
    ext_data = _find_length_delimited_field(raw, _EXTENSION_FIELD)
    if ext_data is None:
        return None

    # Within the sub-message, field 1 is the track string
    track_data = _find_length_delimited_field(ext_data, _TRACK_FIELD)
    if track_data is None:
        return None

    try:
        track = track_data.decode("utf-8")
        return track if track else None
    except UnicodeDecodeError:
        return None
