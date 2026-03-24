import { TripOption, TripLeg } from '../types';
import { formatTime } from '../utils/date';

interface TransferTripCardProps {
  trip: TripOption;
  onLegClick: (leg: TripLeg) => void;
}

function LegRow({ leg, onLegClick }: { leg: TripLeg; onLegClick: () => void }) {
  const departureTime = leg.boarding.actual_time || leg.boarding.updated_time || leg.boarding.scheduled_time;
  const arrivalTime = leg.alighting.actual_time || leg.alighting.updated_time || leg.alighting.scheduled_time;

  return (
    <button
      onClick={onLegClick}
      className="w-full flex items-center gap-3 px-4 py-2 text-left hover:bg-white/5 rounded-lg transition-colors"
    >
      <div
        className="w-1 h-9 rounded-full flex-shrink-0"
        style={{ backgroundColor: leg.line.color }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary truncate">
            {leg.line.name}
          </span>
          {leg.is_cancelled && (
            <span className="text-xs text-error font-medium">Cancelled</span>
          )}
        </div>
        <div className="text-xs text-text-muted truncate">
          {leg.boarding.name} → {leg.alighting.name}
        </div>
      </div>
      <div className="text-xs text-text-muted whitespace-nowrap">
        {departureTime ? formatTime(departureTime) : '--:--'}
        {' → '}
        {arrivalTime ? formatTime(arrivalTime) : '--:--'}
      </div>
      <span className="text-text-muted/50 text-xs">›</span>
    </button>
  );
}

export function TransferTripCard({ trip, onLegClick }: TransferTripCardProps) {
  if (trip.legs.length < 2 || trip.transfers.length < 1) return null;

  const leg1 = trip.legs[0];
  const leg2 = trip.legs[1];
  const transfer = trip.transfers[0];

  const durationDisplay = trip.total_duration_minutes < 60
    ? `${trip.total_duration_minutes} min`
    : `${Math.floor(trip.total_duration_minutes / 60)}h ${trip.total_duration_minutes % 60}m`;

  const walkDescription = transfer.same_station
    ? 'Same station'
    : transfer.walk_minutes <= 1
    ? 'Short walk'
    : `${transfer.walk_minutes} min walk`;

  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl py-3 transition-all">
      <LegRow leg={leg1} onLegClick={() => onLegClick(leg1)} />

      {/* Transfer indicator */}
      <div className="flex items-center gap-2 px-4 py-1">
        <div className="w-1 flex flex-col items-center gap-0.5 flex-shrink-0">
          <div className="w-px h-2 bg-text-muted/20" />
          <span className="text-text-muted/40 text-[10px]">
            {transfer.same_station ? '↓' : '🚶'}
          </span>
          <div className="w-px h-2 bg-text-muted/20" />
        </div>
        <span className="text-xs text-text-muted/60 ml-2">
          {walkDescription}
          {!transfer.same_station && ` at ${transfer.to_station.name}`}
        </span>
      </div>

      <LegRow leg={leg2} onLegClick={() => onLegClick(leg2)} />

      {/* Trip summary footer */}
      <div className="flex items-center justify-between px-4 pt-2 mt-1 border-t border-text-muted/10">
        <span className="text-xs font-medium text-text-muted">
          {durationDisplay}
        </span>
        <span className="text-xs text-text-muted/70">
          {formatTime(trip.departure_time)} → {formatTime(trip.arrival_time)}
        </span>
      </div>
    </div>
  );
}
