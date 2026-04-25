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
from datetime import date as date_type
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_db
from trackrat.models.database import TrainJourney
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
    headline, status = (
        _format_share_strings(journey, to)
        if journey is not None
        else (_FALLBACK_HEADLINE, _FALLBACK_STATUS)
    )

    redirect_url = _build_spa_url(train_id, date, from_, to)
    image_url = (
        _build_image_url(request, train_id, date, from_, to) if journey else None
    )

    return Response(
        content=_render_html(headline, status, redirect_url, image_url),
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

    headline, status = _format_share_strings(journey, to)
    png = render_share_image(headline, status)

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


def _format_share_strings(
    journey: TrainJourney, to_station_code: str | None
) -> tuple[str, str]:
    """Translate a journey + optional user destination into (headline, status)."""
    # ``terminal_station_code`` is non-null in the schema; narrow for mypy.
    dest_code: str = to_station_code or journey.terminal_station_code or ""
    headline = (
        f"{journey.data_source} {journey.train_id} to {get_station_name(dest_code)}"
    )

    if journey.is_cancelled:
        return headline, "Cancelled"

    eta = _arrival_at(journey, dest_code)
    if eta is None:
        return headline, "View train details"

    time_str = _format_clock_time(normalize_to_et(eta))
    if journey.observation_type == "SCHEDULED":
        return headline, f"Scheduled {time_str}"
    return headline, f"Arriving {time_str}"


def _arrival_at(journey: TrainJourney, station_code: str) -> datetime | None:
    """Best-available arrival estimate at ``station_code``.

    Falls through actual → updated → scheduled. NJT's ``updated_*`` fields
    have inverted semantics at intermediate stops (see JourneyStop docs);
    we take ``max(updated_arrival, updated_departure)`` as the live estimate
    for that case, which is harmless for other providers.
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
    return journey.actual_arrival or journey.scheduled_arrival


def _format_clock_time(dt: datetime) -> str:
    """Render an ET datetime as a 12-hour clock string (e.g. ``"5:42 PM"``)."""
    # %-I is GNU-only; build the same output portably by stripping the leading zero.
    return dt.strftime("%I:%M %p").lstrip("0")


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
    return f"{_SPA_HOST}/train/{train_id}{suffix}"


def _build_image_url(
    request: Request,
    train_id: str,
    journey_date: date_type | None,
    from_: str | None,  # accepted but unused — kept to mirror SPA URL params
    to: str | None,
) -> str:
    """Absolute URL of the OG image, rooted at the host the request arrived on."""
    del from_  # Image route doesn't need ``from``; only ``to`` affects the rendered string.
    base = f"{request.url.scheme}://{request.url.netloc}"
    params: dict[str, str] = {}
    if journey_date is not None:
        params["date"] = journey_date.isoformat()
    if to:
        params["to"] = to
    suffix = f"?{urlencode(params)}" if params else ""
    return f"{base}/share/train/{train_id}/image{suffix}"


def _render_html(
    headline: str, status: str, redirect_url: str, image_url: str | None
) -> str:
    """Minimal HTML doc with OG/Twitter tags and a meta-refresh."""
    title = html.escape(headline)
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
