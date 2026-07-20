import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Train, TripSearchResponse } from '../types';
import { apiService } from '../services/api';
import { formatTime } from '../utils/date';
import { buildTrainUrl } from '../utils/routes';
import { tripLegToTrain } from '../utils/trips';
import { usePolling } from '../utils/usePolling';
import { TrainCard } from './TrainCard';

interface Props {
  from: string;
  to: string;
  /** Resolved data source for the page; scopes the timeline to one feed. */
  dataSource?: string;
  /**
   * Line codes to scope the timeline to (line-detail view). Lines that share
   * terminal stations (e.g. NJT Main/Bergen HB↔SF) would otherwise show a
   * combined board for the same from/to pair.
   */
  lineCodes?: string[];
}

const RECENT_WINDOW_MINUTES = 120;
const RECENT_FETCH_LIMIT = 5;
const UPCOMING_FETCH_LIMIT = 10;
const MAX_RECENT = 3;
const MAX_UPCOMING = 3;

/** A single line in the timeline: either a train row or the "now" divider. */
export type TimelineRow =
  | { kind: 'train'; train: Train; departed: boolean }
  | { kind: 'now' };

const trainKey = (train: Train): string => `${train.train_id}:${train.journey_date}`;

/**
 * Merge recently-departed and upcoming trains into a single chronological
 * timeline with a "now" divider between them.
 *
 * `recent` is expected most-recent-first (as `/recent-departures` returns it);
 * it is reversed for display so the section reads oldest-at-top with the most
 * recent departure just above the divider. `upcoming` is expected soonest-first.
 * A train appearing in both feeds (a delayed train straddling "now") is shown
 * only once, as a recent/departed row.
 */
export function buildDeparturesTimeline(
  recent: Train[],
  upcoming: Train[],
  opts: { maxRecent?: number; maxUpcoming?: number } = {}
): TimelineRow[] {
  const { maxRecent = MAX_RECENT, maxUpcoming = MAX_UPCOMING } = opts;

  const shownRecent = recent.slice(0, maxRecent);
  const recentKeys = new Set(shownRecent.map(trainKey));

  const recentRows: TimelineRow[] = [...shownRecent]
    .reverse()
    .map((train) => ({ kind: 'train', train, departed: true }));

  const upcomingRows: TimelineRow[] = upcoming
    .filter((train) => !recentKeys.has(trainKey(train)))
    .slice(0, maxUpcoming)
    .map((train) => ({ kind: 'train', train, departed: false }));

  return [...recentRows, { kind: 'now' }, ...upcomingRows];
}

/** Thin accent hairline with a centered "NOW · h:mm a" label. */
function NowDivider() {
  const label = formatTime(new Date().toISOString());
  return (
    <div className="flex items-center gap-2 py-1" role="separator" aria-label={`Now, ${label}`}>
      <div className="flex-1 h-px bg-accent/50" />
      <span className="text-[10px] font-bold text-accent whitespace-nowrap tracking-wide">
        NOW · {label}
      </span>
      <div className="flex-1 h-px bg-accent/50" />
    </div>
  );
}

interface ViewProps {
  rows: TimelineRow[];
  from: string;
  to: string;
  onSelect: (train: Train) => void;
}

/**
 * Presentational timeline. Kept separate from data fetching so it can be
 * rendered and tested directly with constructed rows (no API mocking).
 */
export function DeparturesTimelineView({ rows, from, to, onSelect }: ViewProps) {
  // "No more trains" when nothing sits after the NOW divider.
  const nowIndex = rows.findIndex((r) => r.kind === 'now');
  const hasUpcoming = nowIndex >= 0 && nowIndex < rows.length - 1;

  return (
    <div className="mb-4 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
      <h4 className="text-sm font-semibold text-text-primary mb-3">Departures</h4>
      <div className="space-y-2">
        {rows.map((row) =>
          row.kind === 'now' ? (
            <NowDivider key="now" />
          ) : (
            <TrainCard
              key={`${row.departed ? 'recent' : 'upcoming'}-${trainKey(row.train)}`}
              train={row.train}
              from={from}
              to={to}
              departed={row.departed}
              onClick={() => onSelect(row.train)}
            />
          )
        )}
        {!hasUpcoming && (
          <div className="text-sm text-text-muted text-center py-1">No more trains scheduled</div>
        )}
      </div>
      <Link
        to={`/trains/${from}/${to}`}
        className="block mt-3 text-xs text-accent hover:text-accent/80 font-medium text-center"
      >
        View All Departures →
      </Link>
    </div>
  );
}

const isAbortError = (err: unknown): boolean =>
  err instanceof DOMException && err.name === 'AbortError';

/** Extract direct, non-cancelled upcoming trains scoped to the page's data source. */
export function directUpcomingTrains(response: TripSearchResponse, dataSource?: string): Train[] {
  return response.trips
    .filter((t) => t.is_direct)
    .map(tripLegToTrain)
    .filter((t) => !t.is_cancelled && (!dataSource || t.data_source === dataSource));
}

/**
 * Route Status departures timeline: recently-departed trains (dimmed) above a
 * NOW divider, upcoming trains below. Polls every 30s independently of the
 * page's one-shot history metrics.
 */
export function DeparturesTimeline({ from, to, dataSource, lineCodes }: Props) {
  const navigate = useNavigate();
  const [recent, setRecent] = useState<Train[]>([]);
  const [upcoming, setUpcoming] = useState<Train[]>([]);
  const [loaded, setLoaded] = useState(false);

  usePolling(
    async (signal) => {
      // Re-throw aborts so usePolling can distinguish cancellation from a real
      // failure; swallow real failures per-feed so one outage doesn't blank both.
      const swallow = (err: unknown) => {
        if (isAbortError(err)) throw err;
        return null;
      };

      const lineScoped = !!lineCodes && lineCodes.length > 0;
      // In line mode, upcoming trains come from /trains/departures, which applies
      // the line filter server-side BEFORE its limit — so a shared-terminal
      // sibling can't crowd this line's next train out of the result set (issue
      // #1567 / PR #1585 review). Non-line mode keeps /trips/search, which is
      // station-equivalence aware and needs no line scoping.
      const upcomingReq = lineScoped
        ? apiService
            .getDepartures(from, {
              to,
              dataSources: dataSource,
              lines: lineCodes,
              hideDeparted: true,
              limit: UPCOMING_FETCH_LIMIT,
              signal,
            })
            .catch(swallow)
        : apiService.searchTrips(from, to, UPCOMING_FETCH_LIMIT, undefined, signal).catch(swallow);

      const [recentRes, upcomingRes] = await Promise.all([
        apiService
          .getRecentDepartures(from, {
            to,
            windowMinutes: RECENT_WINDOW_MINUTES,
            dataSources: dataSource,
            lines: lineCodes,
            limit: RECENT_FETCH_LIMIT,
            signal,
          })
          .catch(swallow),
        upcomingReq,
      ]);

      if (recentRes) setRecent(recentRes.departures);
      if (upcomingRes) {
        // getDepartures → DeparturesResponse (already line/source-filtered
        // server-side; drop cancelled to match the /trips/search path).
        // searchTrips → TripSearchResponse (filter to direct, non-cancelled here).
        setUpcoming(
          'departures' in upcomingRes
            ? upcomingRes.departures.filter((t) => !t.is_cancelled)
            : directUpcomingTrains(upcomingRes, dataSource)
        );
      }
      setLoaded(true);
    },
    // lineCodes comes from the static route topology (stable reference per
    // line id), so it is safe as a dependency without serialization.
    [from, to, dataSource, lineCodes]
  );

  // Nothing to show until the first poll resolves, or when the route has no
  // recent or upcoming trains at all (mirrors the old widget hiding itself).
  if (!loaded || (recent.length === 0 && upcoming.length === 0)) return null;

  const rows = buildDeparturesTimeline(recent, upcoming);

  return (
    <DeparturesTimelineView
      rows={rows}
      from={from}
      to={to}
      onSelect={(train) =>
        navigate(
          buildTrainUrl({
            trainId: train.train_id,
            from,
            to,
            date: train.journey_date,
            dataSource: train.data_source,
          })
        )
      }
    />
  );
}
