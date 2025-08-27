"""
Proposed implementation for honest predictions - only predict when we have real data.
This is a sketch showing how the logic would change.
"""

async def add_predictions_to_stops_honest(self, db, journey, stops):
    """
    Add predictions only when we have sufficient real data.
    Skip predictions otherwise and restart from scheduled times.
    """
    
    # Track the current prediction baseline
    prediction_base_time = None
    prediction_base_index = None
    
    # Find starting point (user origin or first departed stop)
    start_index = self._find_start_index(stops, user_origin)
    
    for i in range(start_index, len(stops) - 1):
        from_stop = stops[i]
        to_stop = stops[i + 1]
        
        # Skip if already departed
        if to_stop.has_departed_station:
            continue
            
        # Get recent ACTUAL segment times (no fallbacks!)
        segment_times = await self._get_recent_segment_times(
            db, from_stop.station_code, to_stop.station_code, journey.data_source
        )
        
        # ONLY predict if we have sufficient real data
        if len(segment_times) >= self.MIN_SAMPLES:
            # We have real data - make a prediction
            
            # Determine the baseline time for this prediction
            if prediction_base_time is None or prediction_base_index != i:
                # Start fresh from this stop's scheduled time
                if from_stop.actual_departure:
                    prediction_base_time = from_stop.actual_departure
                elif from_stop.scheduled_departure:
                    prediction_base_time = from_stop.scheduled_departure
                else:
                    # Can't establish baseline, skip
                    continue
                prediction_base_index = i
            
            # Calculate transit time using median
            transit_minutes = statistics.median(segment_times)
            
            # Apply prediction
            predicted_time = prediction_base_time + timedelta(minutes=transit_minutes)
            
            # Store prediction
            to_stop.predicted_arrival = predicted_time
            to_stop.predicted_arrival_samples = len(segment_times)
            
            # Update baseline for next segment
            prediction_base_time = predicted_time
            prediction_base_index = i + 1
            
            logger.info(
                "✅ Real prediction made",
                station=to_stop.station_code,
                samples=len(segment_times),
                transit_minutes=transit_minutes,
                predicted_arrival=predicted_time.isoformat()
            )
        else:
            # Insufficient data - NO PREDICTION
            to_stop.predicted_arrival = None
            to_stop.predicted_arrival_samples = 0
            
            # Reset baseline for next segment - will start fresh from next stop's scheduled time
            prediction_base_time = None
            prediction_base_index = None
            
            logger.info(
                "⏭️ Skipping prediction - insufficient real data",
                station=to_stop.station_code,
                samples_found=len(segment_times),
                samples_required=self.MIN_SAMPLES,
                reason="honest_predictions_only"
            )
    
    return stops

"""
Benefits of this approach:

1. **Honesty**: Only show predictions when we have real insights
2. **Clarity**: Users know predictions are data-driven, not just schedules
3. **Value**: Every prediction represents actual value over scheduled times
4. **Resilience**: Can restart predictions after gaps in data
5. **Trust**: Builds user confidence in the system

Example scenario:

Train 3840: HL → PJ → NB → ED → ME → NP → NY

With sparse data:
- PJ→NB: No prediction (only 1 sample)
- NB→ED: Predicted based on NB's scheduled time + real data
- ED→ME: No prediction (no recent data)  
- ME→NP: Predicted based on ME's scheduled time + real data
- NP→NY: Continues from NP prediction

Result: Users see predictions only where we add value!
"""