# LIRR Congestion Data — Remaining Work

## Port Washington Branch: Zero Congestion Data

**Status:** Not yet investigated
**Severity:** High — entire branch missing from congestion map

### What we know

- All 13 other LIRR branches have full congestion segment coverage
- Port Washington is the only branch with 0/12 unique stations appearing
- Departures API shows PW trains exist but ALL are `observation_type: "SCHEDULED"` with `actual_time: null`
- This means the LIRR real-time collector is not producing `TrainJourney`/`JourneyStop` DB records for PW trains
- The GTFS static service returns PW departures but does not write to the database — it returns API response objects directly

### Most likely cause

The MTA GTFS-RT feed may not include Port Washington branch trips. PW is the only LIRR branch that doesn't route through Jamaica, so it may be on a separate feed or simply absent from the real-time data.

### Next steps

1. **Query the staging database** to confirm no OBSERVED PW records exist:
   ```sql
   SELECT line_code, observation_type, COUNT(*)
   FROM train_journeys
   WHERE data_source = 'LIRR'
   GROUP BY line_code, observation_type
   ORDER BY line_code;
   ```

2. **Fetch the raw MTA GTFS-RT LIRR feed** and check if PW trips (route_id for Port Washington) are present

3. **Add debug logging** to the LIRR collector to track which route_ids are seen per collection cycle

4. **If PW is absent from GTFS-RT:** Generate `TrainJourney`/`JourneyStop` records from GTFS static data for PW trains (similar to PATCO's schedule-only approach), so congestion data based on scheduled times appears on the map

5. **If PW is present but not being processed:** Trace why the collector drops PW trips

### Key files

- `backend_v2/src/trackrat/collectors/lirr/collector.py` — LIRR real-time collector
- `backend_v2/src/trackrat/collectors/lirr/client.py` — GTFS-RT feed client
- `backend_v2/src/trackrat/services/gtfs.py` — GTFS static schedule service
- `backend_v2/src/trackrat/services/congestion.py` — congestion SQL query

## SAN Station Filter (Minor)

The congestion endpoint in `backend_v2/src/trackrat/api/routes.py:343-355` filters out all segments containing station code `"SAN"` to work around a San Diego / Sanford collision. This is a blunt fix that could be replaced with proper L-prefix disambiguation if Amtrak station codes are ever normalized the same way LIRR codes were.
