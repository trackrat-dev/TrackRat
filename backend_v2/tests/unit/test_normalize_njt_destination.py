"""Tests for ``normalize_njt_destination`` — the helper that bridges NJT's
two destination formats so SCHEDULED and OBSERVED rows for the same physical
train compare equal.

Background (regression-protects issue #1329):
  NJT's daily ``getTrainSchedule`` API (used for schedule generation) returns
  the full official station name as ``DESTINATION`` (e.g. "TRENTON TRANSIT
  CENTER"), while the real-time discovery feed returns the short common name
  for the same station (e.g. "Trenton"). Without normalization, the SCHEDULED
  row created from the schedule API never matches the OBSERVED row created
  from the real-time feed — the discovery-time merge in
  ``collectors/njt/discovery.py`` misses it (creating a duplicate journey),
  and the departures dedup safety net in ``services/departure.py`` also
  misses it (leaving a stale "Train TBD" row visible alongside the real
  train, as reported by a user for train 3865 NY->Trenton).
"""

from __future__ import annotations

from trackrat.utils.train import normalize_njt_destination


class TestNormalizeNjtDestination:
    def test_strips_transit_center_suffix(self) -> None:
        assert normalize_njt_destination("TRENTON TRANSIT CENTER") == "trenton"

    def test_short_name_unchanged_other_than_case(self) -> None:
        assert normalize_njt_destination("Trenton") == "trenton"

    def test_schedule_and_realtime_forms_match(self) -> None:
        assert normalize_njt_destination(
            "TRENTON TRANSIT CENTER"
        ) == normalize_njt_destination("Trenton")

    def test_other_transit_center_stations_also_match(self) -> None:
        assert normalize_njt_destination(
            "PENNSAUKEN TRANSIT CENTER"
        ) == normalize_njt_destination("Pennsauken")

    def test_strips_whitespace(self) -> None:
        assert normalize_njt_destination("  Trenton  ") == "trenton"

    def test_none_returns_empty_string(self) -> None:
        assert normalize_njt_destination(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        assert normalize_njt_destination("") == ""

    def test_does_not_strip_suffix_mid_string(self) -> None:
        """Only a trailing ' transit center' should be stripped, not an
        occurrence elsewhere in the destination."""
        assert (
            normalize_njt_destination("Transit Center Junction")
            == "transit center junction"
        )

    def test_distinct_destinations_remain_distinct(self) -> None:
        assert normalize_njt_destination(
            "TRENTON TRANSIT CENTER"
        ) != normalize_njt_destination("Hamilton")
