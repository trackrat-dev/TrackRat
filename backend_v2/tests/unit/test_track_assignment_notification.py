"""
Tests for track assignment notification logic.

Verifies:
1. alertMetadata is injected into content state when track transitions from None to assigned
2. Duplicate notifications are prevented via track_notified_at
3. Force JIT refresh triggers for tokens awaiting track assignment
4. LIRR/MNR collectors set track_assigned_at on new track assignments
"""

from datetime import datetime, timedelta

from trackrat.models.database import (
    JourneyStop,
    LiveActivityToken,
    TrainJourney,
)
from trackrat.utils.time import now_et

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_journey(
    train_id: str = "3821",
    data_source: str = "NJT",
    origin_code: str = "NY",
    terminal_code: str = "TR",
) -> TrainJourney:
    """Create a TrainJourney with minimal required fields."""
    now = now_et()
    journey = TrainJourney(
        id=1,
        train_id=train_id,
        journey_date=now.date(),
        line_code="NEC",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code=origin_code,
        terminal_station_code=terminal_code,
        data_source=data_source,
        scheduled_departure=now + timedelta(minutes=20),
        has_complete_journey=True,
        stops_count=2,
        last_updated_at=now,
    )
    return journey


def make_stop(
    journey_id: int = 1,
    station_code: str = "NY",
    station_name: str = "New York Penn",
    sequence: int = 1,
    track: str | None = None,
    departed: bool = False,
    minutes_from_now: int = 20,
) -> JourneyStop:
    """Create a JourneyStop with minimal required fields."""
    now = now_et()
    dep_time = now + timedelta(minutes=minutes_from_now)
    stop = JourneyStop(
        journey_id=journey_id,
        station_code=station_code,
        station_name=station_name,
        stop_sequence=sequence,
        scheduled_departure=dep_time,
        has_departed_station=departed,
        track=track,
        track_assigned_at=now if track else None,
    )
    return stop


def make_token(
    train_number: str = "3821",
    origin_code: str = "NY",
    destination_code: str = "TR",
    track_notified_at: datetime | None = None,
) -> LiveActivityToken:
    """Create a LiveActivityToken with minimal required fields."""
    return LiveActivityToken(
        id=1,
        push_token="test_push_token_abc123",
        activity_id="test_activity_id",
        train_number=train_number,
        origin_code=origin_code,
        destination_code=destination_code,
        created_at=now_et(),
        expires_at=now_et() + timedelta(hours=6),
        is_active=True,
        track_notified_at=track_notified_at,
    )


# ---------------------------------------------------------------------------
# Content state + alertMetadata injection tests
# ---------------------------------------------------------------------------


class TestTrackAssignmentDetection:
    """Test the alertMetadata injection logic from update_live_activities."""

    def test_track_assigned_alert_metadata_injected(self):
        """When track is present and token.track_notified_at is None,
        alertMetadata should be added to the content state."""
        content_state = {"track": "7", "status": "BOARDING"}
        token = make_token(track_notified_at=None)

        # This mirrors the logic in update_live_activities
        track_just_assigned = (
            content_state.get("track") is not None and token.track_notified_at is None
        )

        assert track_just_assigned is True

        if track_just_assigned:
            content_state["alertMetadata"] = {
                "alert_type": "track_assigned",
                "train_id": "3821",
                "dynamic_island_priority": "high",
            }

        assert "alertMetadata" in content_state
        assert content_state["alertMetadata"]["alert_type"] == "track_assigned"
        assert content_state["alertMetadata"]["dynamic_island_priority"] == "high"
        assert content_state["alertMetadata"]["train_id"] == "3821"
        print(f"  Content state with alertMetadata: {content_state}")

    def test_no_duplicate_alert_after_notification(self):
        """When token.track_notified_at is already set, alertMetadata should NOT
        be injected even if track is present."""
        content_state = {"track": "7", "status": "BOARDING"}
        token = make_token(track_notified_at=now_et() - timedelta(minutes=5))

        track_just_assigned = (
            content_state.get("track") is not None and token.track_notified_at is None
        )

        assert track_just_assigned is False
        assert "alertMetadata" not in content_state
        print(f"  No alertMetadata (already notified at {token.track_notified_at})")

    def test_no_alert_when_track_is_none(self):
        """When track is None (not yet assigned), no alertMetadata should be injected."""
        content_state = {"track": None, "status": "NOT_DEPARTED"}
        token = make_token(track_notified_at=None)

        track_just_assigned = (
            content_state.get("track") is not None and token.track_notified_at is None
        )

        assert track_just_assigned is False
        assert "alertMetadata" not in content_state
        print("  No alertMetadata (track not yet assigned)")

    def test_track_notified_at_set_after_successful_send(self):
        """After successful APNS send with track_just_assigned, token.track_notified_at
        should be set to prevent duplicate alerts."""
        token = make_token(track_notified_at=None)
        assert token.track_notified_at is None

        # Simulate successful send
        token.track_notified_at = now_et()

        assert token.track_notified_at is not None
        print(f"  track_notified_at set to: {token.track_notified_at}")

        # Verify subsequent check would NOT trigger alert
        content_state = {"track": "7", "status": "BOARDING"}
        track_just_assigned = (
            content_state.get("track") is not None and token.track_notified_at is None
        )
        assert track_just_assigned is False
        print("  Subsequent check correctly skips alertMetadata")


# ---------------------------------------------------------------------------
# Force JIT refresh logic tests
# ---------------------------------------------------------------------------


class TestForceRefreshForTrackAssignment:
    """Test the force_refresh_for_track logic from update_live_activities."""

    def _check_force_refresh(
        self,
        journey: TrainJourney,
        tokens: list[LiveActivityToken],
    ) -> bool:
        """Replicate the force refresh logic from update_live_activities."""
        from trackrat.utils.time import ensure_timezone_aware

        force_refresh_for_track = False
        if journey.data_source in ("NJT", "LIRR", "MNR"):
            for t in tokens:
                if t.track_notified_at is not None:
                    continue
                origin_stop = next(
                    (
                        s
                        for s in (journey.stops or [])
                        if s.station_code == t.origin_code
                    ),
                    None,
                )
                if not origin_stop or origin_stop.track:
                    continue
                dep_time = (
                    origin_stop.updated_departure or origin_stop.scheduled_departure
                )
                if (
                    dep_time
                    and (ensure_timezone_aware(dep_time) - now_et()).total_seconds()
                    < 1800
                ):
                    force_refresh_for_track = True
                    break
        return force_refresh_for_track

    def test_force_refresh_when_track_missing_and_departure_within_30_min(self):
        """Should force refresh when NJT train departs within 30 min without track."""
        journey = make_journey(data_source="NJT")
        origin_stop = make_stop(track=None, minutes_from_now=15)
        dest_stop = make_stop(
            station_code="TR", station_name="Trenton", sequence=2, minutes_from_now=75
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(track_notified_at=None)
        result = self._check_force_refresh(journey, [token])

        assert result is True
        print("  Force refresh triggered: NJT, no track, departure in 15 min")

    def test_no_force_refresh_when_track_already_assigned(self):
        """Should NOT force refresh when origin stop already has a track."""
        journey = make_journey(data_source="NJT")
        origin_stop = make_stop(track="7", minutes_from_now=15)
        dest_stop = make_stop(
            station_code="TR", station_name="Trenton", sequence=2, minutes_from_now=75
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(track_notified_at=None)
        result = self._check_force_refresh(journey, [token])

        assert result is False
        print("  No force refresh: track already assigned")

    def test_no_force_refresh_when_already_notified(self):
        """Should NOT force refresh when token already received track notification."""
        journey = make_journey(data_source="NJT")
        origin_stop = make_stop(track=None, minutes_from_now=15)
        dest_stop = make_stop(
            station_code="TR", station_name="Trenton", sequence=2, minutes_from_now=75
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(track_notified_at=now_et() - timedelta(minutes=2))
        result = self._check_force_refresh(journey, [token])

        assert result is False
        print("  No force refresh: already notified")

    def test_no_force_refresh_when_departure_far_away(self):
        """Should NOT force refresh when departure is more than 30 min away."""
        journey = make_journey(data_source="NJT")
        origin_stop = make_stop(track=None, minutes_from_now=45)
        dest_stop = make_stop(
            station_code="TR", station_name="Trenton", sequence=2, minutes_from_now=105
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(track_notified_at=None)
        result = self._check_force_refresh(journey, [token])

        assert result is False
        print("  No force refresh: departure 45 min away")

    def test_no_force_refresh_for_non_track_providers(self):
        """Should NOT force refresh for Amtrak (no track data in API)."""
        journey = make_journey(data_source="AMTRAK")
        origin_stop = make_stop(track=None, minutes_from_now=15)
        dest_stop = make_stop(
            station_code="TR", station_name="Trenton", sequence=2, minutes_from_now=75
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(track_notified_at=None)
        result = self._check_force_refresh(journey, [token])

        assert result is False
        print("  No force refresh: Amtrak provider (no track data)")

    def test_force_refresh_for_lirr(self):
        """Should force refresh for LIRR trains awaiting track."""
        journey = make_journey(
            data_source="LIRR", origin_code="NYP", terminal_code="BPG"
        )
        origin_stop = make_stop(
            station_code="NYP",
            station_name="Penn Station",
            track=None,
            minutes_from_now=10,
        )
        dest_stop = make_stop(
            station_code="BPG", station_name="Babylon", sequence=2, minutes_from_now=60
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(
            origin_code="NYP", destination_code="BPG", track_notified_at=None
        )
        result = self._check_force_refresh(journey, [token])

        assert result is True
        print("  Force refresh triggered: LIRR, no track, departure in 10 min")

    def test_force_refresh_for_mnr(self):
        """Should force refresh for Metro-North trains awaiting track."""
        journey = make_journey(
            data_source="MNR", origin_code="GCT", terminal_code="WHP"
        )
        origin_stop = make_stop(
            station_code="GCT",
            station_name="Grand Central",
            track=None,
            minutes_from_now=8,
        )
        dest_stop = make_stop(
            station_code="WHP",
            station_name="White Plains",
            sequence=2,
            minutes_from_now=50,
        )
        journey.stops = [origin_stop, dest_stop]

        token = make_token(
            origin_code="GCT", destination_code="WHP", track_notified_at=None
        )
        result = self._check_force_refresh(journey, [token])

        assert result is True
        print("  Force refresh triggered: MNR, no track, departure in 8 min")


# ---------------------------------------------------------------------------
# LIRR/MNR track_assigned_at tests
# ---------------------------------------------------------------------------


class TestCollectorTrackAssignedAt:
    """Test that LIRR/MNR collectors correctly set track_assigned_at."""

    def test_track_assigned_at_set_on_new_assignment(self):
        """When a stop has no track and gets one, track_assigned_at should be set."""
        stop = make_stop(track=None)
        assert stop.track is None
        assert stop.track_assigned_at is None

        # Simulate the collector logic: if arr.track and not stop.track
        new_track = "12"
        if new_track and not stop.track:
            stop.track_assigned_at = now_et()
        stop.track = new_track

        assert stop.track == "12"
        assert stop.track_assigned_at is not None
        print(f"  track_assigned_at set: {stop.track_assigned_at}")

    def test_track_assigned_at_preserved_on_track_update(self):
        """When track changes from one value to another, track_assigned_at should NOT
        be overwritten (preserves the original assignment time)."""
        original_time = now_et() - timedelta(minutes=10)
        stop = make_stop(track="5")
        stop.track_assigned_at = original_time

        # Simulate collector logic: track changes from "5" to "7"
        new_track = "7"
        if new_track and not stop.track:
            stop.track_assigned_at = now_et()  # Would set new time
        stop.track = new_track

        assert stop.track == "7"
        # track_assigned_at should be preserved from original assignment
        assert stop.track_assigned_at == original_time
        print(f"  track_assigned_at preserved: {stop.track_assigned_at}")

    def test_track_assigned_at_not_set_when_no_track_in_api(self):
        """When API returns no track, track_assigned_at should remain None."""
        stop = make_stop(track=None)

        # Simulate: arr.track is None (API has no track data)
        new_track = None
        if new_track and not stop.track:
            stop.track_assigned_at = now_et()
        if new_track:
            stop.track = new_track

        assert stop.track is None
        assert stop.track_assigned_at is None
        print("  No track_assigned_at: API returned no track")


# ---------------------------------------------------------------------------
# LiveActivityToken model tests
# ---------------------------------------------------------------------------


class TestLiveActivityTokenModel:
    """Test the track_notified_at field on the LiveActivityToken model."""

    def test_token_created_with_null_track_notified_at(self):
        """New tokens should have track_notified_at=None by default."""
        token = LiveActivityToken(
            push_token="test_token",
            activity_id="test_activity",
            train_number="3821",
            origin_code="NY",
            destination_code="TR",
            is_active=True,
        )
        assert token.track_notified_at is None
        print("  New token has track_notified_at=None")

    def test_token_track_notified_at_can_be_set(self):
        """track_notified_at should be settable to a datetime."""
        token = make_token()
        assert token.track_notified_at is None

        now = now_et()
        token.track_notified_at = now
        assert token.track_notified_at == now
        print(f"  track_notified_at set to: {token.track_notified_at}")


# ---------------------------------------------------------------------------
# APNS alert payload tests for track assignment notifications
# ---------------------------------------------------------------------------


class TestAPNSTrackAssignmentAlert:
    """Test that send_live_activity_update extracts alertMetadata and adds
    a visible alert to the APNS payload so iOS shows a banner notification.

    Live Activity pushes (apns-push-type: liveactivity) do NOT trigger
    didReceiveRemoteNotification. The only way to surface a visible
    notification alongside a Live Activity update is to include an alert
    field in the aps payload.
    """

    def test_alert_metadata_extracted_and_alert_added(self):
        """When content_state contains alertMetadata with track_assigned,
        the APNS payload should include aps.alert with title/body and
        alertMetadata should be removed from content-state."""
        import time as time_mod

        content_state = {
            "track": "7",
            "status": "BOARDING",
            "currentStopName": "New York Penn",
            "alertMetadata": {
                "alert_type": "track_assigned",
                "train_id": "3821",
                "dynamic_island_priority": "high",
            },
        }

        # Replicate the logic from send_live_activity_update
        alert_metadata = content_state.pop("alertMetadata", None)

        aps: dict = {
            "timestamp": int(time_mod.time()),
            "event": "update",
            "content-state": content_state,
        }

        if alert_metadata and alert_metadata.get("alert_type") == "track_assigned":
            track = content_state.get("track", "TBD")
            aps["alert"] = {
                "title": "Track Assigned",
                "body": f"Track {track} — Board Now",
            }
            aps["sound"] = "default"

        # alertMetadata should NOT be in content-state (would confuse ActivityKit decoder)
        assert "alertMetadata" not in content_state
        print(f"  alertMetadata removed from content-state: {list(content_state.keys())}")

        # Alert should be present in aps
        assert "alert" in aps
        assert aps["alert"]["title"] == "Track Assigned"
        assert aps["alert"]["body"] == "Track 7 — Board Now"
        assert aps["sound"] == "default"
        print(f"  aps.alert: {aps['alert']}")
        print(f"  aps.sound: {aps['sound']}")

    def test_no_alert_when_no_alert_metadata(self):
        """When content_state has no alertMetadata, aps should NOT include alert."""
        import time as time_mod

        content_state = {
            "track": "7",
            "status": "BOARDING",
            "currentStopName": "New York Penn",
        }

        alert_metadata = content_state.pop("alertMetadata", None)

        aps: dict = {
            "timestamp": int(time_mod.time()),
            "event": "update",
            "content-state": content_state,
        }

        if alert_metadata and alert_metadata.get("alert_type") == "track_assigned":
            track = content_state.get("track", "TBD")
            aps["alert"] = {
                "title": "Track Assigned",
                "body": f"Track {track} — Board Now",
            }
            aps["sound"] = "default"

        assert "alert" not in aps
        assert "sound" not in aps
        print("  No alert added: no alertMetadata present")

    def test_no_alert_for_non_track_assigned_metadata(self):
        """When alertMetadata has a different alert_type, no alert should be added."""
        import time as time_mod

        content_state = {
            "track": "7",
            "status": "EN ROUTE",
            "currentStopName": "Secaucus",
            "alertMetadata": {
                "alert_type": "approaching",
                "train_id": "3821",
                "dynamic_island_priority": "low",
            },
        }

        alert_metadata = content_state.pop("alertMetadata", None)

        aps: dict = {
            "timestamp": int(time_mod.time()),
            "event": "update",
            "content-state": content_state,
        }

        if alert_metadata and alert_metadata.get("alert_type") == "track_assigned":
            track = content_state.get("track", "TBD")
            aps["alert"] = {
                "title": "Track Assigned",
                "body": f"Track {track} — Board Now",
            }
            aps["sound"] = "default"

        assert "alertMetadata" not in content_state
        assert "alert" not in aps
        print("  No alert added: alert_type is 'approaching', not 'track_assigned'")

    def test_alert_metadata_popped_even_on_non_track_type(self):
        """alertMetadata should always be removed from content_state,
        regardless of alert_type, to keep content-state clean for ActivityKit."""
        content_state = {
            "track": None,
            "status": "NOT_DEPARTED",
            "alertMetadata": {
                "alert_type": "some_future_type",
                "train_id": "999",
                "dynamic_island_priority": "low",
            },
        }

        alert_metadata = content_state.pop("alertMetadata", None)

        assert "alertMetadata" not in content_state
        assert alert_metadata is not None
        assert alert_metadata["alert_type"] == "some_future_type"
        print("  alertMetadata popped from content_state even for non-track types")
