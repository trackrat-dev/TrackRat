-- Tables scrubbed from a staging database cloned off the production disk.
--
-- SINGLE SOURCE OF TRUTH. Two consumers read this file, and they must never
-- drift apart (issue #1710):
--
--   1. infra_v2/terraform/compute.tf embeds it into the staging VM startup
--      script via file(), so the boot-time scrub runs before the API container
--      starts. This is the copy that actually protects production users.
--   2. scripts/scrub-staging-db.sh reads it at runtime as a manual backstop
--      for local or hand-managed database work.
--
-- Adding a PII-bearing table here covers both paths at once.
--
-- CONSTRAINT: the contents are interpolated into a double-quoted shell string
-- inside compute.tf's startup script, so this file must not contain double
-- quotes, dollar signs, backticks, or backslashes -- any of those would break
-- the staging VM boot. Enforced by
-- backend_v2/tests/unit/test_staging_scrub_sql.py.
--
-- Why each table:
--
-- device_tokens (CASCADE -> route_alert_subscriptions, route_preferences)
--   Contains production APNS tokens. If not scrubbed, staging sends real push
--   notifications to production users' phones within minutes of startup.
--
-- live_activity_tokens
--   Contains production APNS Live Activity push tokens. Staging's scheduler
--   would send Live Activity updates to real users every minute, potentially
--   showing wrong data or ending their active Live Activities.
--
-- cached_api_responses
--   Stale production caches could mask bugs in staging cache generation.
--
-- scheduler_task_runs
--   Contains production instance hostnames and last_successful_run timestamps.
--   If not scrubbed, staging's freshness-check logic may skip scheduled runs
--   for up to their full interval (thinking tasks already ran recently).

TRUNCATE TABLE device_tokens CASCADE;
TRUNCATE TABLE live_activity_tokens;
TRUNCATE TABLE cached_api_responses;
TRUNCATE TABLE scheduler_task_runs;
