"""
MTA GTFS-RT extension parser for LIRR, Metro-North, and NYC Subway feeds.

MTA's railroad feeds include a custom protobuf extension (field 1005) on
TripUpdate.StopTimeUpdate containing track assignment and train status:

    extend transit_realtime.TripUpdate.StopTimeUpdate {
        optional MtaRailroadStopTimeUpdate mta_railroad_stop_time_update = 1005;
    }

    message MtaRailroadStopTimeUpdate {
        optional string track = 1;
        optional string trainStatus = 2;
    }

NYC Subway feeds use different extensions (field 1001) on TripDescriptor
and StopTimeUpdate:

    extend transit_realtime.TripDescriptor {
        optional NyctTripDescriptor nyct_trip_descriptor = 1001;
    }

    message NyctTripDescriptor {
        optional string train_id = 1;
        optional bool is_assigned = 2;
        enum Direction { NORTH = 1; EAST = 2; SOUTH = 3; WEST = 4; }
        optional Direction direction = 3;
    }

    extend transit_realtime.TripUpdate.StopTimeUpdate {
        optional NyctStopTimeUpdate nyct_stop_time_update = 1001;
    }

    message NyctStopTimeUpdate {
        optional string scheduled_track = 1;
        optional string actual_track = 2;
    }

Since the standard gtfs-realtime-bindings package doesn't include MTA's
extensions, we extract the data directly from the serialized protobuf bytes.

Reference (railroad): https://github.com/OneBusAway/onebusaway-gtfs-realtime-api
Reference (subway): https://github.com/jonthornton/MTAPI/blob/master/mtaproto/nyct-subway.proto
"""

import logging
from typing import Any

from google.protobuf.message import Message

logger = logging.getLogger(__name__)

# MTA Railroad extension field numbers (LIRR/MNR)
_RAILROAD_EXTENSION_FIELD = 1005
_RAILROAD_TRACK_FIELD = 1

# NYCT Subway extension field numbers
_NYCT_EXTENSION_FIELD = 1001
# NyctTripDescriptor fields
_NYCT_TRAIN_ID_FIELD = 1
_NYCT_IS_ASSIGNED_FIELD = 2
_NYCT_DIRECTION_FIELD = 3
# NyctStopTimeUpdate fields
_NYCT_SCHEDULED_TRACK_FIELD = 1
_NYCT_ACTUAL_TRACK_FIELD = 2

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


def _find_varint_field(data: bytes, target_field: int) -> int | None:
    """Find and return the value of a varint protobuf field."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _decode_varint(data, pos)
            field_number = tag >> 3
            wire_type = tag & 0x07

            if wire_type == _WIRE_VARINT:
                value, pos = _decode_varint(data, pos)
                if field_number == target_field:
                    return value
            elif wire_type == _WIRE_64BIT:
                pos += 8
            elif wire_type == _WIRE_LENGTH_DELIMITED:
                length, pos = _decode_varint(data, pos)
                pos += length
            elif wire_type == _WIRE_32BIT:
                pos += 4
            else:
                break
        except (IndexError, ValueError):
            break
    return None


def extract_mta_track(stu: Message) -> str | None:
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
    ext_data = _find_length_delimited_field(raw, _RAILROAD_EXTENSION_FIELD)
    if ext_data is None:
        return None

    # Within the sub-message, field 1 is the track string
    track_data = _find_length_delimited_field(ext_data, _RAILROAD_TRACK_FIELD)
    if track_data is None:
        return None

    try:
        track = track_data.decode("utf-8")
        return track if track else None
    except UnicodeDecodeError:
        return None


def extract_nyct_trip_descriptor(trip_update: Message) -> dict[str, Any] | None:
    """Extract NyctTripDescriptor from a subway TripUpdate's TripDescriptor.

    Parses extension field 1001 on the TripDescriptor to get subway-specific
    train identification and direction.

    Args:
        trip_update: A gtfs_realtime_pb2.TripUpdate protobuf message.

    Returns:
        Dict with keys: train_id (str|None), is_assigned (bool),
        direction (int|None, 1=NORTH 2=EAST 3=SOUTH 4=WEST), or None if
        the extension is absent.
    """
    try:
        raw = trip_update.trip.SerializeToString()
    except Exception:
        return None

    ext_data = _find_length_delimited_field(raw, _NYCT_EXTENSION_FIELD)
    if ext_data is None:
        return None

    # train_id: field 1, string (length-delimited)
    train_id = None
    train_id_data = _find_length_delimited_field(ext_data, _NYCT_TRAIN_ID_FIELD)
    if train_id_data is not None:
        try:
            train_id = train_id_data.decode("utf-8") or None
        except UnicodeDecodeError:
            pass

    # is_assigned: field 2, bool (varint)
    is_assigned_val = _find_varint_field(ext_data, _NYCT_IS_ASSIGNED_FIELD)
    is_assigned = bool(is_assigned_val) if is_assigned_val is not None else False

    # direction: field 3, enum (varint)
    direction = _find_varint_field(ext_data, _NYCT_DIRECTION_FIELD)

    return {
        "train_id": train_id,
        "is_assigned": is_assigned,
        "direction": direction,
    }


def extract_nyct_stop_time_update(stu: Message) -> dict[str, Any] | None:
    """Extract NyctStopTimeUpdate from a subway StopTimeUpdate.

    Parses extension field 1001 on the StopTimeUpdate to get track info.

    Args:
        stu: A gtfs_realtime_pb2.TripUpdate.StopTimeUpdate protobuf message.

    Returns:
        Dict with keys: scheduled_track (str|None), actual_track (str|None),
        or None if the extension is absent.
    """
    try:
        raw = stu.SerializeToString()
    except Exception:
        return None

    ext_data = _find_length_delimited_field(raw, _NYCT_EXTENSION_FIELD)
    if ext_data is None:
        return None

    scheduled_track = None
    actual_track = None

    sched_data = _find_length_delimited_field(ext_data, _NYCT_SCHEDULED_TRACK_FIELD)
    if sched_data is not None:
        try:
            scheduled_track = sched_data.decode("utf-8") or None
        except UnicodeDecodeError:
            pass

    actual_data = _find_length_delimited_field(ext_data, _NYCT_ACTUAL_TRACK_FIELD)
    if actual_data is not None:
        try:
            actual_track = actual_data.decode("utf-8") or None
        except UnicodeDecodeError:
            pass

    return {
        "scheduled_track": scheduled_track,
        "actual_track": actual_track,
    }
