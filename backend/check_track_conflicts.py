#!/usr/bin/env python3
"""
Script to scan for trains where the actual track assigned was marked as occupied
in the feature data.
"""

import sys
import logging
from pathlib import Path

# Add the trackcast package to the path
sys.path.insert(0, str(Path(__file__).parent))

from trackcast.config import settings
from trackcast.db.connection import db_session
from trackcast.db.models import Train, ModelData, PredictionData

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_track_conflicts():
    """
    Check for trains where the actual assigned track was marked as occupied
    in the feature data.
    """
    
    with db_session() as session:
        # Query trains that have both track assignments and model data
        query = (
            session.query(Train, ModelData)
            .join(ModelData, Train.model_data_id == ModelData.id)
            .filter(Train.track.isnot(None))
            .filter(Train.track != '')
            .filter(ModelData.track_usage_features.isnot(None))
        )
        
        trains_with_data = query.all()
        logger.info(f"Found {len(trains_with_data)} trains with both track assignments and feature data")
        
        conflicts = []
        
        for train, model_data in trains_with_data:
            # Get the actual assigned track
            actual_track = train.track
            
            # Get the track usage features
            track_features = model_data.track_usage_features
            
            if not track_features:
                continue
                
            # Check if the Is_Track_{actual_track}_Occupied feature exists and is True
            occupied_feature_name = f"Is_Track_{actual_track}_Occupied"
            
            if occupied_feature_name in track_features:
                is_occupied = track_features[occupied_feature_name]
                
                if is_occupied:
                    conflicts.append({
                        'train_id': train.train_id,
                        'internal_id': train.id,
                        'departure_time': train.departure_time,
                        'line': train.line,
                        'destination': train.destination,
                        'actual_track': actual_track,
                        'origin_station': train.origin_station_code,
                        'data_source': train.data_source,
                        'is_occupied': is_occupied
                    })
        
        # Report track assignment conflicts
        if conflicts:
            logger.warning(f"Found {len(conflicts)} potential track assignment conflicts!")
            print(f"\n=== TRACK ASSIGNMENT CONFLICTS FOUND ===")
            print(f"Found {len(conflicts)} trains where the assigned track was marked as occupied in features:\n")
            
            for i, conflict in enumerate(conflicts, 1):
                print(f"{i}. Train {conflict['train_id']} (Internal ID: {conflict['internal_id']})")
                print(f"   Departure: {conflict['departure_time']}")
                print(f"   Line: {conflict['line']}")
                print(f"   Destination: {conflict['destination']}")
                print(f"   Origin Station: {conflict['origin_station']}")
                print(f"   Data Source: {conflict['data_source']}")
                print(f"   Assigned Track: {conflict['actual_track']}")
                print(f"   Track Occupied Feature: {conflict['is_occupied']}")
                print()
            
            # Summary statistics
            tracks_involved = set(c['actual_track'] for c in conflicts)
            lines_involved = set(c['line'] for c in conflicts)
            origins_involved = set(c['origin_station'] for c in conflicts)
            
            print(f"Summary:")
            print(f"- Total assignment conflicts: {len(conflicts)}")
            print(f"- Tracks involved: {sorted(tracks_involved)}")
            print(f"- Lines involved: {sorted(lines_involved)}")
            print(f"- Origin stations involved: {sorted(origins_involved)}")
            
        else:
            logger.info("No track assignment conflicts found - all trains with assigned tracks were correctly marked as unoccupied in features")
            print("\n✅ No track assignment conflicts found!")
            print("All trains with assigned tracks have their track marked as unoccupied in the features.")
        
        # Now check for prediction conflicts - where occupied tracks have significant prediction probability
        print(f"\n=== CHECKING PREDICTION CONFLICTS ===")
        prediction_conflicts = check_prediction_conflicts(session)
        
        # Additional statistics
        total_trains = len(trains_with_data)
        conflict_rate = (len(conflicts) / total_trains * 100) if total_trains > 0 else 0
        
        print(f"\nOverall Statistics:")
        print(f"- Total trains analyzed: {total_trains}")
        print(f"- Trains with assignment conflicts: {len(conflicts)}")
        print(f"- Assignment conflict rate: {conflict_rate:.2f}%")
        print(f"- Trains with prediction conflicts: {len(prediction_conflicts)}")


def check_prediction_conflicts(session, min_probability=0.01):
    """
    Check for trains where occupied tracks have significant prediction probabilities.
    
    Args:
        session: Database session
        min_probability: Minimum probability threshold (default 1%)
        
    Returns:
        List of prediction conflicts
    """
    logger.info("Checking for prediction conflicts (occupied tracks with significant prediction probability)")
    
    # Query trains that have both model data and prediction data
    query = (
        session.query(Train, ModelData, PredictionData)
        .join(ModelData, Train.model_data_id == ModelData.id)
        .join(PredictionData, Train.prediction_data_id == PredictionData.id)
        .filter(ModelData.track_usage_features.isnot(None))
        .filter(PredictionData.track_probabilities.isnot(None))
    )
    
    trains_with_predictions = query.all()
    logger.info(f"Found {len(trains_with_predictions)} trains with both feature and prediction data")
    
    prediction_conflicts = []
    
    for train, model_data, prediction_data in trains_with_predictions:
        # Get the track usage features
        track_features = model_data.track_usage_features
        track_probabilities = prediction_data.track_probabilities
        
        if not track_features or not track_probabilities:
            continue
        
        # Find all occupied tracks for this train
        occupied_tracks = []
        for feature_name, value in track_features.items():
            if feature_name.startswith("Is_Track_") and feature_name.endswith("_Occupied") and value:
                # Extract track number from feature name
                track = feature_name.replace("Is_Track_", "").replace("_Occupied", "")
                occupied_tracks.append(track)
        
        # Check if any occupied tracks have significant prediction probability
        conflicting_tracks = []
        for track in occupied_tracks:
            if track in track_probabilities:
                probability = track_probabilities[track]
                if probability > min_probability:
                    conflicting_tracks.append({
                        'track': track,
                        'probability': probability,
                        'is_occupied': True
                    })
        
        if conflicting_tracks:
            prediction_conflicts.append({
                'train_id': train.train_id,
                'internal_id': train.id,
                'departure_time': train.departure_time,
                'line': train.line,
                'destination': train.destination,
                'origin_station': train.origin_station_code,
                'data_source': train.data_source,
                'actual_track': train.track,
                'conflicting_tracks': conflicting_tracks,
                'top_predicted_track': prediction_data.top_track,
                'top_probability': prediction_data.top_probability
            })
    
    # Report prediction conflicts
    if prediction_conflicts:
        logger.warning(f"Found {len(prediction_conflicts)} prediction conflicts!")
        print(f"\nFound {len(prediction_conflicts)} trains with occupied tracks having significant prediction probability (>{min_probability*100}%):\n")
        
        for i, conflict in enumerate(prediction_conflicts, 1):
            print(f"{i}. Train {conflict['train_id']} (Internal ID: {conflict['internal_id']})")
            print(f"   Departure: {conflict['departure_time']}")
            print(f"   Line: {conflict['line']}")
            print(f"   Destination: {conflict['destination']}")
            print(f"   Origin Station: {conflict['origin_station']}")
            print(f"   Data Source: {conflict['data_source']}")
            print(f"   Actual Track: {conflict['actual_track']}")
            print(f"   Top Predicted Track: {conflict['top_predicted_track']} ({conflict['top_probability']:.3f})")
            print(f"   Occupied tracks with significant predictions:")
            for track_info in conflict['conflicting_tracks']:
                print(f"     - Track {track_info['track']}: {track_info['probability']:.3f} ({track_info['probability']*100:.1f}%)")
            print()
        
        # Summary statistics for prediction conflicts
        all_conflicting_tracks = []
        for conflict in prediction_conflicts:
            all_conflicting_tracks.extend([t['track'] for t in conflict['conflicting_tracks']])
        
        unique_conflicting_tracks = set(all_conflicting_tracks)
        tracks_with_high_probs = set()
        max_prob_per_track = {}
        
        for conflict in prediction_conflicts:
            for track_info in conflict['conflicting_tracks']:
                track = track_info['track']
                prob = track_info['probability']
                if prob > 0.05:  # 5% threshold for "high" probability
                    tracks_with_high_probs.add(track)
                if track not in max_prob_per_track or prob > max_prob_per_track[track]:
                    max_prob_per_track[track] = prob
        
        print(f"Prediction Conflict Summary:")
        print(f"- Total prediction conflicts: {len(prediction_conflicts)}")
        print(f"- Unique tracks with conflicts: {sorted(unique_conflicting_tracks)}")
        print(f"- Tracks with >5% probability when occupied: {sorted(tracks_with_high_probs)}")
        print(f"- Max probabilities per track: {dict(sorted(max_prob_per_track.items()))}")
        
    else:
        logger.info("No prediction conflicts found - occupied tracks have appropriately low prediction probabilities")
        print("\n✅ No prediction conflicts found!")
        print(f"All occupied tracks have prediction probabilities ≤ {min_probability*100}%.")
    
    return prediction_conflicts


if __name__ == "__main__":
    try:
        check_track_conflicts()
    except Exception as e:
        logger.error(f"Error running track conflict check: {e}")
        sys.exit(1)