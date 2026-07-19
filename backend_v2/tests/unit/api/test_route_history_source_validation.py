"""API-level tests for the ``/routes/history`` ``data_source`` allow-list.

The endpoint validates ``data_source`` against a hard-coded ``valid_sources``
list in ``trackrat.api.routes`` and returns a 400 ("data_source must be one
of: ...") for anything else. A newly-added transit system must be added to
that list or its Route Status history request gets a 400 even though the rest
of the app already treats it as a real system.

These exercise only the validation branch, which fires before any database
access, so they run against the mocked ``client`` fixture without Postgres.
"""

import pytest


class TestRouteHistorySourceValidation:
    """`/routes/history` must accept every real transit source, reject bogus ones."""

    @pytest.mark.parametrize(
        "data_source",
        [
            "NJT",
            "AMTRAK",
            "PATH",
            "PATCO",
            "LIRR",
            "MNR",
            "SUBWAY",
            "METRA",
            "WMATA",
            "BART",
            "MBTA",
            "SEPTA_RR",
            "SEPTA_METRO",
        ],
    )
    def test_real_source_passes_validation(self, client, data_source):
        """A real source must never hit the 400 "must be one of" validation error.

        SEPTA_RR / SEPTA_METRO are the regression guard: they are live systems
        (present in congestion, summary, alert, and station configs) so their
        Route Status history request must clear ``valid_sources``. Downstream
        status varies with data, but it must not be the validation 400.
        """
        resp = client.get(
            "/api/v2/routes/history",
            params={
                "from_station": "NY",
                "to_station": "TR",
                "data_source": data_source,
            },
        )
        assert resp.status_code != 400, resp.text
        assert "must be one of" not in resp.json().get("detail", "")

    def test_unknown_source_is_rejected(self, client):
        """An unrecognized source still returns the 400 validation error."""
        resp = client.get(
            "/api/v2/routes/history",
            params={
                "from_station": "NY",
                "to_station": "TR",
                "data_source": "NOT_A_REAL_SOURCE",
            },
        )
        assert resp.status_code == 400, resp.text
        assert "must be one of" in resp.json()["detail"]
