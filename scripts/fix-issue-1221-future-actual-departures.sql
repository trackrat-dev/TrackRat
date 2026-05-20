-- One-shot cleanup for issue #1221.
--
-- Background: a bug in the NJT journey collector's three-tier departure
-- inference (Tier 3 time-inference + Tier 2 sequential cascade, locked
-- in by the never-overwrite freeze) wrote future timestamps into
-- journey_stops.actual_departure for severely delayed trains, and marked
-- stops as has_departed_station=True without real evidence of departure.
--
-- The collector fix prevents new poisoning. This script repairs rows
-- that were already corrupted before the fix shipped. It is safe to run
-- multiple times — every WHERE clause is conservative and matches only
-- structurally impossible states.
--
-- Run inside a transaction and inspect the row counts before committing.
-- Example:
--   BEGIN;
--   \i scripts/fix-issue-1221-future-actual-departures.sql
--   -- review the NOTICE output, then either COMMIT; or ROLLBACK;
--
-- The collector loop re-evaluates each cell every cycle, so any stop
-- this script resets will be re-marked correctly on the next collection
-- if NJT actually shows the train has departed.

DO $$
DECLARE
  cleared_actual_count INTEGER;
  cleared_flag_count   INTEGER;
BEGIN
  -- 1. Clear any actual_departure that sits in the future. These can
  --    never be valid — a train cannot have "actually departed" at a
  --    time that has not happened yet. The corruption source was Tier 2
  --    writing the live arrival estimate (TIME field) into actual_departure
  --    at intermediate stops for not-yet-departed trains.
  UPDATE journey_stops
     SET actual_departure = NULL
   WHERE actual_departure > NOW();
  GET DIAGNOSTICS cleared_actual_count = ROW_COUNT;
  RAISE NOTICE 'issue_1221_cleanup: cleared % future actual_departure values', cleared_actual_count;

  -- 2. Reset has_departed_station=True where every available signal says
  --    the train has NOT actually departed:
  --      - NJT's current DEPARTED flag is "NO"
  --      - No real arrival or departure timestamp was ever captured
  --      - NJT's live arrival estimate (updated_arrival) is still in
  --        the future — meaning NJT itself says the train hasn't reached
  --        this stop yet.
  --    This is the same condition the collector's new live-estimate
  --    guard uses to suppress Tier 3, applied retroactively.
  UPDATE journey_stops
     SET has_departed_station = FALSE,
         departure_source = NULL
   WHERE has_departed_station = TRUE
     AND raw_njt_departed_flag = 'NO'
     AND actual_departure IS NULL
     AND actual_arrival IS NULL
     AND updated_arrival IS NOT NULL
     AND updated_arrival > NOW();
  GET DIAGNOSTICS cleared_flag_count = ROW_COUNT;
  RAISE NOTICE 'issue_1221_cleanup: reset % bogus has_departed_station=TRUE rows', cleared_flag_count;

  -- 3. After step 2, some train_journeys.actual_departure values may now
  --    refer to a stop whose has_departed_station is FALSE. The next
  --    collection cycle re-derives journey.actual_departure from the
  --    first truly-departed stop (see journey.py:2222-2243), so leave
  --    the journey-level field for the collector to self-correct.
END $$;
