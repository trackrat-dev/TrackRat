"""Share-link OG-preview endpoints.

Apple Messages (and other unfurlers) read OG/Twitter meta tags from raw
HTML; they do not execute JavaScript. The webpage SPA at trackrat.net is
client-rendered, so its share links would otherwise show only the static
generic OG tags from index.html.

These two routes solve that:

- ``GET /share/train/{train_id}`` — tiny HTML doc with rich OG tags and a
  meta-refresh that sends real users on to the trackrat.net SPA URL.
- ``GET /share/train/{train_id}/image`` — PNG generated on demand from
  current train data. The HTML's ``og:image`` points here.

The iOS share sheet (and webpage share button) emits the
``apiv2.trackrat.net/share/...`` URL instead of the trackrat.net URL.
Apple's Universal Links AASA on this domain forwards taps back into the
iOS app for users who have it installed.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_db
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.share_image import render_share_image
from trackrat.utils.time import normalize_to_et, now_et

logger = get_logger(__name__)
router = APIRouter(prefix="/share", tags=["share"], include_in_schema=False)

# Where humans (browsers, app users) are sent after the meta-refresh.
_SPA_HOST = "https://trackrat.net"

# Generic copy when the train can't be found — preview still renders
# a sensible fallback rather than a broken link.
_FALLBACK_HEADLINE = "TrackRat"
_FALLBACK_STATUS = "Real-time train tracking"


@dataclass(frozen=True)
class _ShareCopy:
    """Text strings used by the share HTML and generated preview image."""

    title: str
    headline: str
    status: str


@router.get("/train/{train_id}", name="share_train_html")
@handle_errors
async def share_train_html(
    request: Request,
    train_id: str = Path(..., description="Train ID"),
    date: date_type | None = Query(None, description="Journey date (YYYY-MM-DD)"),
    from_: str | None = Query(None, alias="from", description="Origin station code"),
    to: str | None = Query(None, description="Destination station code"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return an OG-tagged HTML doc that unfurls in iMessage and redirects to the SPA."""
    journey = await _fetch_journey(db, train_id, date or now_et().date())
    copy = (
        _format_share_copy(journey, from_, to)
        if journey is not None
        else _ShareCopy(
            title=_FALLBACK_HEADLINE,
            headline=_FALLBACK_HEADLINE,
            status=_FALLBACK_STATUS,
        )
    )

    redirect_url = _build_spa_url(train_id, date, from_, to)
    image_url = (
        _build_image_url(request, train_id, date, from_, to) if journey else None
    )

    return Response(
        content=_render_html(copy.title, copy.status, redirect_url, image_url),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.get("/train/{train_id}/image", name="share_train_image")
@handle_errors
async def share_train_image(
    train_id: str = Path(..., description="Train ID"),
    date: date_type | None = Query(None, description="Journey date (YYYY-MM-DD)"),
    to: str | None = Query(None, description="Destination station code"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a 1000x540 PNG OG preview rendered from current train data."""
    journey = await _fetch_journey(db, train_id, date or now_et().date())
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Train {train_id} not found")

    copy = _format_share_copy(journey, None, to)
    png = render_share_image(copy.headline, copy.status)

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=600"},
    )


async def _fetch_journey(
    db: AsyncSession, train_id: str, journey_date: date_type
) -> TrainJourney | None:
    """Most-recent journey for ``train_id`` on ``journey_date`` (any data source)."""
    result: TrainJourney | None = await db.scalar(
        select(TrainJourney)
        .where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
            )
        )
        .options(selectinload(TrainJourney.stops))
        .order_by(TrainJourney.last_updated_at.desc())
        .limit(1)
    )
    return result


def _format_share_copy(
    journey: TrainJourney, from_station_code: str | None, to_station_code: str | None
) -> _ShareCopy:
    """Translate a journey + optional user route context into share copy."""
    # ``terminal_station_code`` is non-null in the schema; narrow for mypy.
    dest_code: str = to_station_code or journey.terminal_station_code or ""
    origin_code: str = from_station_code or journey.origin_station_code or ""
    headline = (
        f"{journey.data_source} {journey.train_id} to {get_station_name(dest_code)}"
    )
    title = _format_share_title(journey, headline, origin_code, dest_code)

    if journey.is_cancelled:
        return _ShareCopy(title=headline, headline=headline, status="Cancelled")

    eta = _arrival_at(journey, dest_code)
    if eta is None:
        return _ShareCopy(
            title=title, headline=headline, status="View train details"
        )

    time_str = _format_clock_time(normalize_to_et(eta))
    if journey.observation_type == "SCHEDULED":
        return _ShareCopy(
            title=title, headline=headline, status=f"Scheduled {time_str}"
        )
    return _ShareCopy(title=title, headline=headline, status=f"Arriving {time_str}")


def _format_share_strings(
    journey: TrainJourney, to_station_code: str | None
) -> tuple[str, str]:
    """Translate a journey + optional user destination into image headline/status."""
    copy = _format_share_copy(journey, None, to_station_code)
    return copy.headline, copy.status


def _format_share_title(
    journey: TrainJourney, headline: str, from_station_code: str, to_station_code: str
) -> str:
    """Return the HTML/OG title, including route times when both are trustworthy."""
    if journey.is_cancelled:
        return headline

    departure = _departure_at(journey, from_station_code)
    arrival = _arrival_at(journey, to_station_code)
    if departure is None or arrival is None:
        return headline

    departure_et = normalize_to_et(departure)
    arrival_et = normalize_to_et(arrival)
    if arrival_et <= departure_et:
        return headline

    return f"{headline} from {_format_time_range(departure_et, arrival_et)}"


def _departure_at(journey: TrainJourney, station_code: str) -> datetime | None:
    """Best-available departure estimate at ``station_code``.

    Falls through actual -> updated -> scheduled. For updated departure estimates,
    use the later of ``updated_arrival`` and ``updated_departure`` when both exist:
    NJT stores the live delayed estimate in different fields depending on stop type,
    and the later timestamp matches the canonical DepartureService behavior.
    """
    for stop in journey.stops or []:
        if stop.station_code != station_code:
            continue
        return (
            stop.actual_departure
            or stop.actual_arrival
            or _latest_updated_time(stop)
            or stop.scheduled_departure
            or stop.scheduled_arrival
        )

    if station_code == journey.origin_station_code:
        return journey.actual_departure or journey.scheduled_departure
    return None


def _latest_updated_time(stop: JourneyStop) -> datetime | None:
    """Return the later updated stop time, tolerating providers with only one field."""
    updated_times = [t for t in (stop.updated_arrival, stop.updated_departure) if t]
    return max(updated_times) if updated_times else None


def _arrival_at(journey: TrainJourney, station_code: str) -> datetime | None:
    """Best-available arrival estimate at ``station_code``.

    Falls through actual → updated → scheduled. NJT's ``updated_*`` fields
    have inverted semantics at intermediate stops (see JourneyStop docs);
    we take ``max(updated_arrival, updated_departure)`` as the live estimate
    for that case, which is harmless for other providers.

    If ``station_code`` is the journey's terminal and there's no matching
    ``JourneyStop`` (rare — happens for journeys without per-stop records
    yet), falls back to the journey-level arrival fields. For any other
    station_code with no matching stop, returns ``None`` so the caller
    can render a generic status rather than the wrong time.
    """
    for stop in journey.stops or []:
        if stop.station_code != station_code:
            continue
        if stop.actual_arrival:
            return stop.actual_arrival
        if journey.data_source == "NJT":
            updated = [t for t in (stop.updated_arrival, stop.updated_departure) if t]
            if updated:
                return max(updated)
        elif stop.updated_arrival:
            return stop.updated_arrival
        return stop.scheduled_arrival

    if station_code == journey.terminal_station_code:
        return journey.actual_arrival or journey.scheduled_arrival
    return None


def _format_clock_time(dt: datetime) -> str:
    """Render an ET datetime as a 12-hour clock string (e.g. ``"5:42 PM"``)."""
    # %-I is GNU-only; build the same output portably by stripping the leading zero.
    return dt.strftime("%I:%M %p").lstrip("0")


def _format_time_range(start: datetime, end: datetime) -> str:
    """Render a compact clock range for two ET datetimes."""
    start_clock, start_meridiem = _split_clock_time(start)
    end_clock, end_meridiem = _split_clock_time(end)
    if start.date() == end.date() and start_meridiem == end_meridiem:
        return f"{start_clock} to {end_clock} {end_meridiem}"
    return f"{start_clock} {start_meridiem} to {end_clock} {end_meridiem}"


def _split_clock_time(dt: datetime) -> tuple[str, str]:
    """Split ``_format_clock_time`` into clock and AM/PM pieces."""
    clock, meridiem = _format_clock_time(dt).rsplit(" ", 1)
    return clock, meridiem


def _build_spa_url(
    train_id: str,
    journey_date: date_type | None,
    from_: str | None,
    to: str | None,
) -> str:
    """The trackrat.net SPA URL the share link redirects to."""
    params: dict[str, str] = {}
    if journey_date is not None:
        params["date"] = journey_date.isoformat()
    if from_:
        params["from"] = from_
    if to:
        params["to"] = to
    suffix = f"?{urlencode(params)}" if params else ""
    # quote() with safe="" prevents a malicious train_id from injecting URL
    # structure (path traversal, query corruption, fragment injection).
    return f"{_SPA_HOST}/train/{quote(train_id, safe='')}{suffix}"


def _build_image_url(
    request: Request,
    train_id: str,
    journey_date: date_type | None,
    from_: str | None,  # accepted but unused — kept to mirror SPA URL params
    to: str | None,
) -> str:
    """Absolute URL of the OG image, rooted at the host the request arrived on."""
    del from_  # Image route doesn't need ``from``; only ``to`` affects the rendered string.
    # Behind the GCP load balancer TLS terminates at the LB, so request.url.scheme
    # is "http". Apple's iMessage crawler will reject http og:image URLs as
    # insecure, so trust X-Forwarded-Proto when present.
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    base = f"{scheme}://{host}"
    params: dict[str, str] = {}
    if journey_date is not None:
        params["date"] = journey_date.isoformat()
    if to:
        params["to"] = to
    suffix = f"?{urlencode(params)}" if params else ""
    return f"{base}/share/train/{quote(train_id, safe='')}/image{suffix}"


def _render_html(
    title: str, status: str, redirect_url: str, image_url: str | None
) -> str:
    """Minimal HTML doc with OG/Twitter tags and a meta-refresh."""
    title = html.escape(title)
    description = html.escape(status)
    redirect = html.escape(redirect_url, quote=True)

    image_tags = ""
    twitter_card = "summary"
    if image_url:
        image = html.escape(image_url, quote=True)
        image_tags = (
            f'<meta property="og:image" content="{image}">\n'
            f'<meta property="og:image:width" content="1000">\n'
            f'<meta property="og:image:height" content="540">\n'
            f'<meta name="twitter:image" content="{image}">\n'
        )
        twitter_card = "summary_large_image"

    return (
        f"<!DOCTYPE html>\n"
        f'<html lang="en">\n'
        f"<head>\n"
        f'<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<meta http-equiv="refresh" content="0; url={redirect}">\n'
        f'<link rel="canonical" href="{redirect}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{redirect}">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{description}">\n'
        f"{image_tags}"
        f'<meta name="twitter:card" content="{twitter_card}">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{description}">\n'
        f"</head>\n"
        f"<body>\n"
        f'<p>Redirecting to <a href="{redirect}">{redirect}</a>…</p>\n'
        f"</body>\n"
        f"</html>\n"
    )
