# NYC Subway GTFS-RT feed sample

Raw protobuf responses from all 8 MTA subway GTFS-RT feeds, captured
2026-08-02 16:53 UTC (12:53 ET, a Sunday afternoon with the 1 short-turning at
14 St and the 5/A/G/M running mid-route origins). Gzipped; 468 trip updates
across 22 route_ids.

They exist so `tests/unit/collectors/subway/test_trip_id_encoding.py` can
validate the NYCT trip_id origin-time encoding against bytes MTA actually
served, rather than against hand-written ids — the encoding gates origin
inference (issue #1704), and an unvalidated rule there would decline
legitimate origins across the whole subway feed.

To re-capture (feed URLs are `SUBWAY_GTFS_RT_FEED_URLS` in
`src/trackrat/config/stations/subway.py`):

```bash
for feed in gtfs gtfs-ace gtfs-bdfm gtfs-g gtfs-jz gtfs-l gtfs-nqrw gtfs-si; do
  curl -s "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F$feed" \
    | gzip -9 > "$feed.pb.gz"
done
```

Rename the downloads to the feed-group keys the test expects (`1234567S`,
`ACE`, `BDFM`, `G`, `JZ`, `L`, `NQRW`, `SIR`). The test derives "now" from each
feed's own header timestamp, so a fresh capture stays deterministic.
