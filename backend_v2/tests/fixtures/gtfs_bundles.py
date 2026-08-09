"""Builder for small but genuinely valid GTFS static bundles.

Shared between the integration tests that drive `refresh_feed` end to end and
the unit tests for `_bundle_service_status`, so both exercise the exact same
zip shape instead of each maintaining its own.
"""

import io
import zipfile
from collections.abc import Sequence


def build_gtfs_zip(
    *,
    trips: int = 2,
    service_id: str = "WKDY",
    start_date: str = "20260101",
    end_date: str = "20261231",
    include_calendar: bool = True,
    route_type: str = "2",
    extra_calendar_rows: Sequence[str] = (),
    calendar_dates_rows: Sequence[str] = (),
    extra_route_rows: Sequence[str] = (),
    extra_trip_rows: Sequence[str] = (),
) -> bytes:
    """Build a small but genuinely valid GTFS static feed.

    Real enough that `_parse_and_store_gtfs` walks its whole pipeline —
    routes → calendar → stops → trips → stop_times — and reports non-zero
    counts, so a test can assert on what the parse actually persisted rather
    than on a stubbed stats dict.

    ``start_date`` / ``end_date`` set the calendar's service window in GTFS's
    own ``YYYYMMDD`` form; a start date in the future models an agency
    publishing next week's bundle early (issue #1769).

    ``include_calendar=False`` drops ``calendar.txt`` entirely, as NJT's real
    feed does — the bundle then declares no service window at all.

    ``route_type`` sets route R1's type (default "2", heavy rail) so a bundle
    can model a source under ``GTFS_ROUTE_TYPE_FILTER``.

    The ``extra_*_rows`` parameters append literal CSV lines (no trailing
    newline) to the named file, so a test can spell out exactly the historical
    calendar row, bus route, or foreign-service trip it needs. Non-empty
    ``calendar_dates_rows`` adds a ``calendar_dates.txt``
    (``service_id,date,exception_type``), which the base bundle otherwise
    omits.
    """
    trip_rows = "\n".join(
        f"T{n},{service_id},R1,Test Terminal,{n % 2}" for n in range(1, trips + 1)
    )
    stop_time_rows = "\n".join(
        f"T{n},{(5 + n) % 24:02d}:00:00,{(5 + n) % 24:02d}:00:00,S1,1\n"
        f"T{n},{(5 + n) % 24:02d}:30:00,{(5 + n) % 24:02d}:30:00,S2,2"
        for n in range(1, trips + 1)
    )

    def _with_extras(body: str, extras: Sequence[str]) -> str:
        return body + "".join(f"{line}\n" for line in extras)

    files = {
        "routes.txt": _with_extras(
            "route_id,route_short_name,route_long_name,route_type,route_color\n"
            f"R1,TL,Test Line,{route_type},ff0000\n",
            extra_route_rows,
        ),
        "calendar.txt": _with_extras(
            "service_id,monday,tuesday,wednesday,thursday,friday,"
            "saturday,sunday,start_date,end_date\n"
            f"{service_id},1,1,1,1,1,0,0,{start_date},{end_date}\n",
            extra_calendar_rows,
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,Test Origin,40.7,-74.0\n"
            "S2,Test Terminal,40.8,-74.1\n"
        ),
        "trips.txt": _with_extras(
            "trip_id,service_id,route_id,trip_headsign,direction_id\n"
            + trip_rows
            + "\n",
            extra_trip_rows,
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            + stop_time_rows
            + "\n"
        ),
    }

    if not include_calendar:
        del files["calendar.txt"]
    if calendar_dates_rows:
        files["calendar_dates.txt"] = _with_extras(
            "service_id,date,exception_type\n", calendar_dates_rows
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buffer.getvalue()
