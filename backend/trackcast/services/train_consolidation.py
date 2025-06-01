"""
Train consolidation service for merging duplicate train records from multiple sources.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from trackcast.db.models import Train, TrainStop
from trackcast.exceptions import TrackCastError

logger = logging.getLogger(__name__)


class TrainConsolidationService:
    """Service for consolidating train records from multiple sources."""

    def __init__(self):
        """Initialize the consolidation service."""
        self.time_tolerance = timedelta(minutes=2)  # For matching stop times
        
    def consolidate_trains(self, trains: List[Train]) -> List[Dict]:
        """
        Consolidate multiple train records into unified journey representations.
        
        Args:
            trains: List of Train objects to consolidate
            
        Returns:
            List of consolidated train dictionaries
        """
        if not trains:
            return []
            
        # Group trains by potential journeys
        journey_groups = self._group_trains_by_journey(trains)
        
        # Consolidate each journey group
        consolidated_trains = []
        for journey_id, train_group in journey_groups.items():
            consolidated = self._consolidate_journey_group(train_group)
            consolidated_trains.append(consolidated)
            
        return consolidated_trains
    
    def _group_trains_by_journey(self, trains: List[Train]) -> Dict[str, List[Train]]:
        """
        Group trains that represent the same physical journey.
        
        Returns:
            Dictionary mapping journey IDs to lists of related trains
        """
        journey_groups = defaultdict(list)
        processed = set()
        
        for i, train1 in enumerate(trains):
            if i in processed:
                continue
                
            # Start a new journey group with this train
            journey_trains = [train1]
            processed.add(i)
            
            # Find all other trains that match this journey
            for j, train2 in enumerate(trains):
                if j <= i or j in processed:
                    continue
                    
                if self._trains_match(train1, train2):
                    journey_trains.append(train2)
                    processed.add(j)
            
            # Generate journey ID and store group
            journey_id = self._get_journey_id(journey_trains)
            journey_groups[journey_id] = journey_trains
            
        return dict(journey_groups)
    
    def _trains_match(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains represent the same physical journey.
        
        Args:
            train1: First train to compare
            train2: Second train to compare
            
        Returns:
            True if trains are the same journey, False otherwise
        """
        # Primary match: Same train ID
        if train1.train_id != train2.train_id:
            return False
            
        # Check if trains share the same journey by comparing stop times
        if not self._same_journey(train1, train2):
            return False
            
        # Route validation: Check if they share the same route pattern
        if not self._same_route_pattern(train1, train2):
            return False
            
        return True
    
    def _same_journey(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains are part of the same journey by comparing their stops.
        Since departure_time is relative to origin_station_code, we need to find
        a common reference point in their stop schedules.
        """
        # Check if stops are loaded
        if not hasattr(train1, 'stops') or not hasattr(train2, 'stops'):
            logger.warning(f"Trains {train1.train_id} and {train2.train_id} missing stop data")
            return False
            
        if not train1.stops or not train2.stops:
            return False
            
        # Find common stops between both trains
        common_stops_found = 0
        for stop1 in train1.stops:
            for stop2 in train2.stops:
                if stop1.station_code == stop2.station_code:
                    # Check if scheduled times match (within tolerance for API differences)
                    if stop1.scheduled_time and stop2.scheduled_time:
                        time_diff = abs(stop1.scheduled_time - stop2.scheduled_time)
                        if time_diff <= self.time_tolerance:
                            common_stops_found += 1
                            if common_stops_found >= 3:  # Need at least 3 common stops
                                return True
        
        return False
    
    def _same_route_pattern(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains follow the same route pattern.
        
        Args:
            train1: First train to compare
            train2: Second train to compare
            
        Returns:
            True if routes match, False otherwise
        """
        if not hasattr(train1, 'stops') or not hasattr(train2, 'stops'):
            return False
            
        # Extract ordered station codes
        route1 = [stop.station_code for stop in train1.stops if stop.station_code]
        route2 = [stop.station_code for stop in train2.stops if stop.station_code]
        
        # Find common stations and check order
        common_stations = []
        for station in route1:
            if station in route2:
                common_stations.append(station)
        
        # Need at least 3 common stations
        if len(common_stations) < 3:
            return False
            
        # Check if common stations appear in the same order in both routes
        idx1 = 0
        idx2 = 0
        for station in common_stations:
            # Find station in route1
            while idx1 < len(route1) and route1[idx1] != station:
                idx1 += 1
            # Find station in route2  
            while idx2 < len(route2) and route2[idx2] != station:
                idx2 += 1
                
            if idx1 >= len(route1) or idx2 >= len(route2):
                return False
                
        return True
    
    def _get_journey_id(self, trains: List[Train]) -> str:
        """
        Generate a unique journey identifier based on train_id and the earliest stop time.
        This helps group trains from different origins into the same journey.
        """
        if not trains:
            raise ValueError("Cannot generate journey ID for empty train list")
            
        train_id = trains[0].train_id
        
        # Find the earliest scheduled stop across all trains
        earliest_time = None
        for train in trains:
            if hasattr(train, 'stops') and train.stops:
                for stop in train.stops:
                    if stop.scheduled_time:
                        if earliest_time is None or stop.scheduled_time < earliest_time:
                            earliest_time = stop.scheduled_time
        
        # If no stops found, use the earliest departure time
        if earliest_time is None:
            earliest_time = min(train.departure_time for train in trains)
            
        journey_date = earliest_time.date()
        return f"{train_id}_{journey_date.isoformat()}"
    
    def _consolidate_journey_group(self, trains: List[Train]) -> Dict:
        """
        Consolidate a group of trains representing the same journey.
        
        Args:
            trains: List of trains on the same journey
            
        Returns:
            Consolidated train dictionary
        """
        if not trains:
            raise ValueError("Cannot consolidate empty train list")
            
        # Sort trains by their origin departure time
        trains.sort(key=lambda t: t.departure_time)
        
        # Use the earliest train as the base
        base_train = trains[0]
        
        # Merge data from all sources
        consolidated = {
            "train_id": base_train.train_id,
            "consolidated_id": self._get_journey_id(trains),
            "origin_station": {
                "code": base_train.origin_station_code,
                "name": base_train.origin_station_name,
                "departure_time": base_train.departure_time.isoformat()
            },
            "destination": base_train.destination,
            "line": base_train.line,
            "line_code": base_train.line_code,
            
            # Data sources information
            "data_sources": self._build_data_sources(trains),
            
            # Merged fields using priority rules
            "track_assignment": self._merge_track_assignment(trains),
            "status_summary": self._merge_status(trains),
            
            # Position tracking
            "current_position": self._calculate_current_position(trains),
            
            # Merged stops with departure status from all sources
            "stops": self._merge_stops(trains),
            
            # Metadata
            "consolidation_metadata": {
                "source_count": len(trains),
                "last_update": max(t.updated_at for t in trains).isoformat(),
                "confidence_score": self._calculate_confidence_score(trains)
            }
        }
        
        # Add prediction data if available
        prediction_data = self._get_best_prediction(trains)
        if prediction_data:
            consolidated["prediction_data"] = prediction_data
            
        return consolidated
    
    def _build_data_sources(self, trains: List[Train]) -> List[Dict]:
        """Build list of data sources contributing to this consolidated train."""
        sources = []
        for train in trains:
            source_info = {
                "origin": train.origin_station_code,
                "data_source": train.data_source,
                "last_update": train.updated_at.isoformat(),
                "status": train.status,
                "track": train.track,
                "delay_minutes": train.delay_minutes,
                "db_id": train.id
            }
            sources.append(source_info)
        return sources
    
    def _merge_track_assignment(self, trains: List[Train]) -> Dict:
        """
        Merge track assignment data using priority rules.
        Priority: True origin station > Most recent > NJ Transit > Amtrak
        
        The "true origin" is the station where the journey actually starts 
        (earliest stop in the route), not just the first train in our list.
        """
        track_info = {
            "track": None,
            "assigned_at": None,
            "assigned_by": None,
            "source": None
        }
        
        # Find the true origin station (where the journey actually starts)
        true_origin = self._find_true_origin_station(trains)
        
        # Priority 1: Check if true origin station has a track assignment
        true_origin_train = None
        for train in trains:
            if train.origin_station_code == true_origin:
                true_origin_train = train
                break
        
        # If true origin exists and has a track (even empty), use it and stop
        if true_origin_train is not None:
            if true_origin_train.track and true_origin_train.track.strip():
                track_info["track"] = true_origin_train.track
                track_info["assigned_at"] = true_origin_train.track_assigned_at.isoformat() if true_origin_train.track_assigned_at else None
                track_info["assigned_by"] = true_origin_train.origin_station_code
                track_info["source"] = true_origin_train.data_source
            # If true origin exists but has no track, leave track_info empty (don't fallback)
            return track_info
        
        # Priority 2: If no track from true origin, use most recent assignment
        if not track_info["track"]:
            candidate_trains = [t for t in trains if t.track and t.track.strip()]
            if candidate_trains:
                # Sort by track assignment time (most recent first)
                recent_train = max(candidate_trains, 
                                 key=lambda t: t.track_assigned_at if t.track_assigned_at else t.updated_at)
                track_info["track"] = recent_train.track
                track_info["assigned_at"] = recent_train.track_assigned_at.isoformat() if recent_train.track_assigned_at else None
                track_info["assigned_by"] = recent_train.origin_station_code
                track_info["source"] = recent_train.data_source
                
        return track_info
    
    def _find_true_origin_station(self, trains: List[Train]) -> Optional[str]:
        """
        Find the true origin station where the journey actually starts.
        This is the station with the earliest scheduled stop time across all trains.
        """
        earliest_station = None
        earliest_time = None
        
        for train in trains:
            if hasattr(train, 'stops') and train.stops:
                for stop in train.stops:
                    if stop.scheduled_time:
                        if earliest_time is None or stop.scheduled_time < earliest_time:
                            earliest_time = stop.scheduled_time
                            earliest_station = stop.station_code
        
        return earliest_station
    
    def _merge_status(self, trains: List[Train]) -> Dict:
        """
        Merge status information from all sources.
        Priority: Most recent update > Most progressed > Amtrak > NJ Transit
        """
        # Get the most recent status
        latest_train = max(trains, key=lambda t: t.updated_at)
        
        # Calculate maximum delay (conservative approach)
        max_delay = 0
        for train in trains:
            if train.delay_minutes is not None and train.delay_minutes > max_delay:
                max_delay = train.delay_minutes
                
        # Determine current status
        current_status = latest_train.status
        if any(t.status == "DEPARTED" for t in trains):
            current_status = "In Transit"
        elif any(t.status == "BOARDING" for t in trains):
            current_status = "Boarding"
            
        return {
            "current_status": current_status,
            "delay_minutes": max_delay,
            "on_time_performance": "Delayed" if max_delay > 5 else "On Time"
        }
    
    def _calculate_current_position(self, trains: List[Train]) -> Optional[Dict]:
        """Calculate the train's current position based on departed flags."""
        # Collect all stops with their departed status
        all_stops = []
        for train in trains:
            if hasattr(train, 'stops') and train.stops:
                all_stops.extend(train.stops)
                
        if not all_stops:
            return None
            
        # Build consolidated stop status
        stop_status = {}
        for stop in all_stops:
            if stop.station_code not in stop_status:
                stop_status[stop.station_code] = {
                    "station_name": stop.station_name,
                    "scheduled_time": stop.scheduled_time,
                    "departed": False
                }
            # If any source says departed, mark as departed
            if stop.departed:
                stop_status[stop.station_code]["departed"] = True
                
        # Find last departed and next station
        sorted_stops = sorted(stop_status.items(), key=lambda x: x[1]["scheduled_time"] or datetime.min)
        last_departed = None
        next_station = None
        
        for i, (code, info) in enumerate(sorted_stops):
            if info["departed"]:
                last_departed = (code, info)
            elif last_departed and not next_station:
                next_station = (code, info)
                break
                
        if not last_departed:
            # Train hasn't departed yet
            return {
                "status": "Not yet departed",
                "next_station": {
                    "code": sorted_stops[0][0],
                    "name": sorted_stops[0][1]["station_name"],
                    "scheduled_arrival": sorted_stops[0][1]["scheduled_time"].isoformat()
                } if sorted_stops else None
            }
            
        position = {
            "last_departed_station": {
                "code": last_departed[0],
                "name": last_departed[1]["station_name"],
                "scheduled_departure": last_departed[1]["scheduled_time"].isoformat()
            }
        }
        
        if next_station:
            position["next_station"] = {
                "code": next_station[0],
                "name": next_station[1]["station_name"],
                "scheduled_arrival": next_station[1]["scheduled_time"].isoformat()
            }
            # Could calculate segment progress here if we had real-time position data
            
        return position
    
    def _merge_stops(self, trains: List[Train]) -> List[Dict]:
        """Merge stop information from all sources."""
        # Collect all stops
        stop_map = {}
        
        for train in trains:
            if not hasattr(train, 'stops') or not train.stops:
                continue
                
            for stop in train.stops:
                key = stop.station_code
                if key not in stop_map:
                    stop_map[key] = {
                        "station_code": stop.station_code,
                        "station_name": stop.station_name,
                        "scheduled_time": stop.scheduled_time.isoformat() if stop.scheduled_time else None,
                        "departure_time": stop.departure_time.isoformat() if stop.departure_time else None,
                        "pickup_only": stop.pickup_only,
                        "dropoff_only": stop.dropoff_only,
                        "departed": stop.departed,
                        "departed_confirmed_by": [],
                        "stop_status": stop.stop_status
                    }
                    
                # Update departed status - if any source says departed, it's departed
                if stop.departed:
                    stop_map[key]["departed"] = True
                    stop_map[key]["departed_confirmed_by"].append(train.origin_station_code)
                    
                # Update actual times if available
                if stop.departure_time and not stop_map[key]["departure_time"]:
                    stop_map[key]["departure_time"] = stop.departure_time.isoformat()
                    
        # Sort stops by scheduled time
        # Use datetime.min for None values to ensure proper sorting
        sorted_stops = sorted(stop_map.values(), key=lambda s: datetime.fromisoformat(s["scheduled_time"]) if s["scheduled_time"] else datetime.min)
        return sorted_stops
    
    def _get_best_prediction(self, trains: List[Train]) -> Optional[Dict]:
        """Get the best prediction data from available sources."""
        # Find trains with predictions
        trains_with_predictions = [t for t in trains if t.prediction_data]
        
        if not trains_with_predictions:
            return None
            
        # Use prediction from origin station if available
        for train in trains_with_predictions:
            if train.origin_station_code == trains[0].origin_station_code:
                return self._serialize_prediction(train.prediction_data)
                
        # Otherwise use most recent prediction
        latest = max(trains_with_predictions, key=lambda t: t.updated_at)
        return self._serialize_prediction(latest.prediction_data)
    
    def _serialize_prediction(self, prediction_data) -> Dict:
        """Serialize prediction data object to dictionary."""
        if not prediction_data:
            return None
            
        return {
            "track_probabilities": prediction_data.track_probabilities,
            "prediction_factors": prediction_data.prediction_factors,
            "model_version": prediction_data.model_version,
            "created_at": prediction_data.created_at.isoformat()
        }
    
    def _calculate_confidence_score(self, trains: List[Train]) -> float:
        """
        Calculate confidence score for the consolidation.
        Higher score means more confident in the consolidation accuracy.
        """
        score = 1.0
        
        # More sources = higher confidence
        score = min(1.0, 0.5 + (len(trains) * 0.1))
        
        # Consistent data = higher confidence
        statuses = set(t.status for t in trains if t.status)
        if len(statuses) > 1:
            score *= 0.9  # Small penalty for inconsistent statuses
            
        tracks = set(t.track for t in trains if t.track)
        if len(tracks) > 1:
            score *= 0.8  # Larger penalty for inconsistent tracks
            
        return round(score, 2)