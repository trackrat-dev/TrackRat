"""
Inspect MTA LIRR and MNR GTFS-RT feeds for track/extension data.

The MTARR proto defines extension field 1005 on StopTimeUpdate:
  message MtaRailroadStopTimeUpdate {
    optional string track = 1;
    optional string trainStatus = 2;
  }
"""

import struct
from datetime import UTC, datetime

import httpx
from google.transit import gtfs_realtime_pb2

LIRR_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"
MNR_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr"


def decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a protobuf varint. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, pos


def parse_protobuf_fields(data: bytes) -> list[tuple[int, int, object]]:
    """Parse raw protobuf bytes into (field_number, wire_type, value) tuples."""
    fields = []
    pos = 0
    while pos < len(data):
        try:
            tag, pos = decode_varint(data, pos)
            field_number = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 0:
                value, pos = decode_varint(data, pos)
            elif wire_type == 1:
                value = struct.unpack("<q", data[pos : pos + 8])[0]
                pos += 8
            elif wire_type == 2:
                length, pos = decode_varint(data, pos)
                value = data[pos : pos + length]
                pos += length
            elif wire_type == 5:
                value = struct.unpack("<i", data[pos : pos + 4])[0]
                pos += 4
            else:
                break
            fields.append((field_number, wire_type, value))
        except Exception:
            break
    return fields


def try_string(data: bytes) -> str | None:
    """Try to decode bytes as UTF-8."""
    try:
        s = data.decode("utf-8")
        if all(32 <= ord(c) < 127 or c in "\n\r\t" for c in s):
            return s
    except (UnicodeDecodeError, ValueError):
        pass
    return None


def inspect_feed(name: str, url: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"INSPECTING: {name}")
    print(f"{'=' * 70}")

    resp = httpx.get(url, timeout=30.0, headers={"Accept": "application/x-protobuf"})
    resp.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)

    print(f"Feed timestamp: {datetime.fromtimestamp(feed.header.timestamp, tz=UTC)}")
    print(f"Entities: {len(feed.entity)}")

    tu_count = stu_count = stu_with_ext = 0
    tracks: dict[str, list[str]] = {}
    statuses: dict[str, int] = {}
    printed = 0

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu_count += 1
        trip = entity.trip_update.trip
        trip_id = trip.trip_id if trip.HasField("trip_id") else "?"

        for stu in entity.trip_update.stop_time_update:
            stu_count += 1
            raw = stu.SerializeToString()
            fields = parse_protobuf_fields(raw)
            ext = [f for f in fields if f[0] >= 1000]

            if not ext:
                continue
            stu_with_ext += 1

            for fn, wt, val in ext:
                if fn == 1005 and isinstance(val, bytes):
                    sub = parse_protobuf_fields(val)
                    for sfn, _swt, sval in sub:
                        if sfn == 1 and isinstance(sval, bytes):
                            t = try_string(sval)
                            if t:
                                tracks.setdefault(t, [])
                                if len(tracks[t]) < 3:
                                    tracks[t].append(
                                        f"{trip_id}@stop{stu.stop_id}"
                                    )
                        elif sfn == 2 and isinstance(sval, bytes):
                            s = try_string(sval)
                            if s:
                                statuses[s] = statuses.get(s, 0) + 1

                    if printed < 10:
                        printed += 1
                        stop_id = (
                            stu.stop_id if stu.HasField("stop_id") else "?"
                        )
                        sub_decoded = {
                            sfn: try_string(sv) if isinstance(sv, bytes) else sv
                            for sfn, _sw, sv in sub
                        }
                        print(
                            f"  trip={trip_id} stop={stop_id} ext_1005={sub_decoded}"
                        )

    print(f"\n--- {name} SUMMARY ---")
    print(f"TripUpdates: {tu_count}")
    print(f"StopTimeUpdates: {stu_count}")
    print(
        f"STUs with extensions: {stu_with_ext}"
        f" ({100 * stu_with_ext / max(stu_count, 1):.1f}%)"
    )

    if tracks:
        print(f"\nTRACKS ({len(tracks)} unique):")
        for t in sorted(tracks.keys()):
            print(f"  Track '{t}': {tracks[t][:3]}")
    else:
        print("\nNO TRACKS found")

    if statuses:
        print(f"\nSTATUSES:")
        for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
            print(f"  '{s}': {c}")
    else:
        print("\nNO STATUSES found")


def main():
    print(f"MTA GTFS-RT Extension Inspector  |  {datetime.now(UTC).isoformat()}\n")
    for name, url in [("LIRR", LIRR_URL), ("Metro-North", MNR_URL)]:
        try:
            inspect_feed(name, url)
        except Exception as e:
            print(f"\nERROR for {name}: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
