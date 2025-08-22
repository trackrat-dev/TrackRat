#!/usr/bin/env python3
"""
Train a Random Forest model for NY Penn Station track predictions.

This script:
1. Loads training data from CSV
2. Encodes categorical features
3. Trains a Random Forest model
4. Evaluates performance
5. Saves the model and encoders

Input: data/ny_penn_track_training_data.csv
Output: 
  - ml/models/ny_track_predictor.pkl (trained model)
  - ml/models/ny_label_encoders.pkl (feature encoders)
  - ml/models/ny_track_classes.pkl (possible track values)
  - ml/reports/ny_model_performance.json (performance metrics)
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


def load_and_prepare_data(csv_path: str):
    """Load CSV and prepare features."""
    print(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} samples")
    
    # Remove any samples with invalid data
    df = df[df['platform'].notna()]
    df = df[df['platform'] != '']
    
    # Handle missing values
    df['minutes_since_track_used'] = df['minutes_since_track_used'].fillna(-1)
    df['minutes_since_platform_used'] = df['minutes_since_platform_used'].fillna(-1)
    
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
    
    # Define feature columns
    feature_columns = [
        'hour_of_day',
        'day_of_week', 
        'is_amtrak',
        'line_code_encoded',
        'destination_encoded',
        'minutes_since_track_used',
        'minutes_since_platform_used'
    ]
    
    # Extract features and target (now predicting platform instead of track)
    X = df[feature_columns].values
    y = df['platform'].values
    
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


def evaluate_model(model, X_test, y_test, platform_classes):
    """Evaluate model performance."""
    
    print("\nEvaluating model...")
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    
    # Calculate top-3 accuracy
    top3_correct = 0
    for i, true_platform in enumerate(y_test):
        # Get top 3 predicted platforms
        proba_row = y_proba[i]
        top3_indices = np.argsort(proba_row)[-3:]
        top3_platforms = [platform_classes[idx] for idx in top3_indices]
        if true_platform in top3_platforms:
            top3_correct += 1
    
    top3_accuracy = top3_correct / len(y_test)
    
    # Get classification report
    report = classification_report(y_test, y_pred, output_dict=True)
    
    # Print results
    print(f"\nTop-1 Accuracy: {accuracy:.3f}")
    print(f"Top-3 Accuracy: {top3_accuracy:.3f}")
    
    # Performance by platform
    print("\nPer-platform performance:")
    for platform in sorted(set(y_test)):
        if platform in report:
            precision = report[platform]['precision']
            recall = report[platform]['recall']
            support = report[platform]['support']
            print(f"  Platform {platform}: Precision={precision:.2f}, Recall={recall:.2f}, N={support}")
    
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


def save_model_artifacts(model, encoders, platform_classes, performance, feature_importance):
    """Save all model artifacts."""
    
    models_dir = Path("ml/models")
    reports_dir = Path("ml/reports")
    
    # Ensure directories exist
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model
    model_path = models_dir / "ny_track_predictor.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\nModel saved to {model_path}")
    
    # Save encoders
    encoders_path = models_dir / "ny_label_encoders.pkl"
    with open(encoders_path, 'wb') as f:
        pickle.dump(encoders, f)
    print(f"Encoders saved to {encoders_path}")
    
    # Save platform classes
    classes_path = models_dir / "ny_track_classes.pkl"
    with open(classes_path, 'wb') as f:
        pickle.dump(platform_classes, f)
    print(f"Platform classes saved to {classes_path}")
    
    # Save performance report
    report = {
        'model_type': 'RandomForestClassifier',
        'n_training_samples': performance.get('n_training_samples'),
        'n_test_samples': performance.get('n_test_samples'),
        'top1_accuracy': performance['top1_accuracy'],
        'top3_accuracy': performance['top3_accuracy'],
        'feature_importance': feature_importance,
        'per_platform_metrics': performance['classification_report']
    }
    
    report_path = reports_dir / "ny_model_performance.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Performance report saved to {report_path}")


def main():
    """Main training pipeline."""
    
    print("=" * 60)
    print("NY Penn Station Track Predictor Training")
    print("=" * 60)
    
    # Load data
    df = load_and_prepare_data("data/ny_penn_track_training_data.csv")
    
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
    
    # Get unique platform classes
    platform_classes = sorted(set(y))
    print(f"Number of platforms: {len(platform_classes)}")
    
    # Train model
    model = train_model(X_train, y_train)
    
    # Ensure model knows all platform classes
    model.classes_ = np.array(platform_classes)
    
    # Evaluate model
    performance = evaluate_model(model, X_test, y_test, platform_classes)
    performance['n_training_samples'] = len(X_train)
    performance['n_test_samples'] = len(X_test)
    
    # Analyze feature importance
    feature_importance = analyze_feature_importance(model, feature_names)
    
    # Save everything
    save_model_artifacts(model, encoders, platform_classes, performance, feature_importance)
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    
    # Print summary
    print(f"\nModel Performance Summary:")
    print(f"  Top-1 Accuracy: {performance['top1_accuracy']:.1%}")
    print(f"  Top-3 Accuracy: {performance['top3_accuracy']:.1%}")
    print(f"\nMost important features:")
    for feature, importance in list(feature_importance.items())[:3]:
        print(f"  - {feature}: {importance:.3f}")


if __name__ == "__main__":
    main()