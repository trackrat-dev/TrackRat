#!/usr/bin/env python3
"""
Train Random Forest models for track predictions across multiple stations.

This script:
1. Loads training data from CSV
2. Encodes categorical features
3. Trains a Random Forest model (predicting individual tracks)
4. Evaluates performance
5. Saves the model and encoders

Usage:
    python train_track_predictor.py          # Train for all stations with data
    python train_track_predictor.py NY       # Train for specific station
    python train_track_predictor.py NP TR    # Train for multiple stations

Input: data/{station_code}_track_training_data.csv
Output: 
  - ml/models/{station_code}_track_predictor.pkl (trained model)
  - ml/models/{station_code}_label_encoders.pkl (feature encoders)
  - ml/models/{station_code}_track_classes.pkl (possible track values)
  - ml/reports/{station_code}_model_performance.json (performance metrics)
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trackrat.config.station_configs import (
    get_station_config,
    get_ml_enabled_stations,
)


def load_and_prepare_data(csv_path: str):
    """Load CSV and prepare features."""
    print(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} samples")
    
    # Remove any samples with invalid data
    df = df[df['track'].notna()]
    df = df[df['track'] != '']
    
    # Handle missing values
    df['minutes_since_track_used'] = df['minutes_since_track_used'].fillna(-1)
    
    print(f"After cleaning: {len(df)} samples")
    
    return df


def encode_features(df):
    """Encode categorical features and prepare for training."""
    
    # Initialize encoders
    line_encoder = LabelEncoder()
    destination_encoder = LabelEncoder()
    
    # Handle unknown values
    df['line_code'] = df['line_code'].fillna('UNKNOWN')
    df['destination'] = df['destination'].fillna('UNKNOWN')
    
    # Encode categorical features
    df['line_code_encoded'] = line_encoder.fit_transform(df['line_code'])
    df['destination_encoded'] = destination_encoder.fit_transform(df['destination'])
    
    # Store encoders for later use
    encoders = {
        'line_code': line_encoder,
        'destination': destination_encoder
    }
    
    return df, encoders


def prepare_features_and_target(df):
    """Extract feature matrix and target vector."""
    
    # Define feature columns (6 features only)
    feature_columns = [
        'hour_of_day',
        'day_of_week', 
        'is_amtrak',
        'line_code_encoded',
        'destination_encoded',
        'minutes_since_track_used'
    ]
    
    print(f"Using {len(feature_columns)} features: {feature_columns}")
    
    # Extract features and target (predicting individual tracks)
    X = df[feature_columns].values
    y = df['track'].values
    
    return X, y, feature_columns


def train_model(X_train, y_train):
    """Train Random Forest model."""
    
    print("\nTraining Random Forest model...")
    
    # Initialize model with balanced parameters
    model = RandomForestClassifier(
        n_estimators=100,      # Number of trees
        max_depth=15,          # Limit depth to prevent overfitting
        min_samples_split=10,  # Minimum samples to split a node
        min_samples_leaf=5,    # Minimum samples in leaf
        class_weight='balanced', # Handle imbalanced track usage
        random_state=42,       # For reproducibility
        n_jobs=-1             # Use all CPU cores
    )
    
    # Train the model
    model.fit(X_train, y_train)
    
    return model


def evaluate_model(model, X_test, y_test, track_classes):
    """Evaluate model performance."""
    
    print("\nEvaluating model...")
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    
    # Calculate top-3 accuracy
    top3_correct = 0
    for i, true_track in enumerate(y_test):
        # Get top 3 predicted tracks
        proba_row = y_proba[i]
        top3_indices = np.argsort(proba_row)[-3:]
        top3_tracks = [track_classes[idx] for idx in top3_indices]
        if true_track in top3_tracks:
            top3_correct += 1
    
    top3_accuracy = top3_correct / len(y_test)
    
    # Get classification report
    report = classification_report(y_test, y_pred, output_dict=True)
    
    # Print results
    print(f"\nTop-1 Accuracy: {accuracy:.3f}")
    print(f"Top-3 Accuracy: {top3_accuracy:.3f}")
    
    # Performance by track
    print("\nPer-track performance:")
    for track in sorted(set(y_test), key=lambda x: int(str(x)) if str(x).isdigit() else 999):
        if track in report:
            precision = report[track]['precision']
            recall = report[track]['recall']
            support = report[track]['support']
            print(f"  Track {track}: Precision={precision:.2f}, Recall={recall:.2f}, N={support}")
    
    return {
        'top1_accuracy': float(accuracy),
        'top3_accuracy': float(top3_accuracy),
        'classification_report': report
    }


def analyze_feature_importance(model, feature_names):
    """Analyze and print feature importance."""
    
    print("\nFeature Importance:")
    importances = model.feature_importances_
    
    # Sort features by importance
    feature_importance = list(zip(feature_names, importances))
    feature_importance.sort(key=lambda x: x[1], reverse=True)
    
    for feature, importance in feature_importance:
        print(f"  {feature}: {importance:.4f}")
    
    return dict(feature_importance)


def save_model_artifacts(station_code, model, encoders, track_classes, performance, feature_importance):
    """Save all model artifacts for a specific station."""
    
    models_dir = Path("ml/models")
    reports_dir = Path("ml/reports")
    
    # Ensure directories exist
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Use lowercase station code for file names
    station_prefix = station_code.lower()
    
    # Save model
    model_path = models_dir / f"{station_prefix}_track_predictor.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\nModel saved to {model_path}")
    
    # Save encoders
    encoders_path = models_dir / f"{station_prefix}_label_encoders.pkl"
    with open(encoders_path, 'wb') as f:
        pickle.dump(encoders, f)
    print(f"Encoders saved to {encoders_path}")
    
    # Save track classes
    classes_path = models_dir / f"{station_prefix}_track_classes.pkl"
    with open(classes_path, 'wb') as f:
        pickle.dump(track_classes, f)
    print(f"Track classes saved to {classes_path}")
    
    # Save performance report
    report = {
        'station_code': station_code,
        'model_type': 'RandomForestClassifier',
        'n_training_samples': performance.get('n_training_samples'),
        'n_test_samples': performance.get('n_test_samples'),
        'top1_accuracy': performance['top1_accuracy'],
        'top3_accuracy': performance['top3_accuracy'],
        'feature_importance': feature_importance,
        'per_track_metrics': performance['classification_report']
    }
    
    report_path = reports_dir / f"{station_prefix}_model_performance.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Performance report saved to {report_path}")


def train_model_for_station(station_code: str):
    """Train model for a specific station."""
    
    print("\n" + "=" * 60)
    print(f"{station_code} Station Track Predictor Training")
    print("=" * 60)
    
    # Check if CSV exists
    csv_path = f"data/{station_code.lower()}_track_training_data.csv"
    if not Path(csv_path).exists():
        print(f"No training data found at {csv_path}")
        print("Please run export_track_training_data.py first")
        return False
    
    # Load data
    df = load_and_prepare_data(csv_path)
    
    if len(df) < 100:
        print(f"Not enough samples ({len(df)} < 100) for training")
        return False
    
    # Encode features
    df, encoders = encode_features(df)
    
    # Prepare features and target
    X, y, feature_names = prepare_features_and_target(df)
    
    # Split data - use stratify only if we have enough samples per class
    min_class_size = pd.Series(y).value_counts().min()
    use_stratify = min_class_size >= 2
    
    if use_stratify:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print(f"Using stratified split (min class size: {min_class_size})")
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"Using random split (min class size: {min_class_size} is too small for stratification)")
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Get unique track classes - sort properly (numeric first, then alphabetic)
    track_classes = sorted(set(y), key=lambda x: (not str(x).isdigit(), int(str(x)) if str(x).isdigit() else str(x)))
    print(f"Number of tracks: {len(track_classes)}")
    print(f"Tracks: {track_classes}")
    
    # Train model
    model = train_model(X_train, y_train)
    
    # Ensure model knows all track classes
    model.classes_ = np.array(track_classes)
    
    # Evaluate model
    performance = evaluate_model(model, X_test, y_test, track_classes)
    performance['n_training_samples'] = len(X_train)
    performance['n_test_samples'] = len(X_test)
    
    # Analyze feature importance
    feature_importance = analyze_feature_importance(model, feature_names)
    
    # Save everything
    save_model_artifacts(station_code, model, encoders, track_classes, performance, feature_importance)
    
    # Print summary
    print(f"\nModel Performance Summary for {station_code}:")
    print(f"  Top-1 Accuracy: {performance['top1_accuracy']:.1%}")
    print(f"  Top-3 Accuracy: {performance['top3_accuracy']:.1%}")
    
    return True


def main():
    """Main training pipeline for multiple stations."""
    
    # Get station codes from command line or use all with data
    if len(sys.argv) > 1:
        station_codes = sys.argv[1:]
        print(f"Training models for specified stations: {', '.join(station_codes)}")
    else:
        # Find all stations with training data
        data_dir = Path("data")
        if not data_dir.exists():
            print("No data directory found. Please run export_track_training_data.py first")
            return
        
        # Look for CSV files
        csv_files = list(data_dir.glob("*_track_training_data.csv"))
        station_codes = []
        for csv_file in csv_files:
            # Extract station code from filename
            station_code = csv_file.stem.replace("_track_training_data", "").upper()
            if station_code != "NY_PENN":  # Handle old naming
                station_codes.append(station_code)
        
        if not station_codes:
            print("No training data files found in data/ directory")
            return
        
        print(f"Found training data for {len(station_codes)} stations: {', '.join(sorted(station_codes))}")
    
    # Train models for each station
    successful_trains = []
    failed_trains = []
    
    for station_code in station_codes:
        try:
            success = train_model_for_station(station_code)
            if success:
                successful_trains.append(station_code)
            else:
                failed_trains.append(station_code)
        except Exception as e:
            print(f"Error training model for {station_code}: {e}")
            failed_trains.append(station_code)
    
    # Print final summary
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    
    if successful_trains:
        print(f"\nSuccessfully trained models: {len(successful_trains)}")
        print(f"  Stations: {', '.join(successful_trains)}")
    
    if failed_trains:
        print(f"\nFailed to train models: {len(failed_trains)}")
        print(f"  Stations: {', '.join(failed_trains)}")


if __name__ == "__main__":
    main()