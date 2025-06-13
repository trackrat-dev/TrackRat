"""
Feature engineering functions from model.py adapted for TrackCast pipeline.
"""

import logging
import pickle
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

logger = logging.getLogger(__name__)


def load_track_data_from_csv(
    data_dir: str = "output/processed_data",
) -> Tuple[pd.DataFrame, List[str], List[str], List[str]]:
    """
    Load preprocessed track data files from CSV (adapted from model.py).

    Args:
        data_dir: Directory containing CSV files

    Returns:
        Tuple of (dataframe, tracks, train_lines, feature_columns)
    """
    import glob

    file_pattern = str(Path(data_dir) / "*.csv")
    all_files = [f for f in glob.glob(file_pattern) if "unassigned_trains" not in f]

    if not all_files:
        raise ValueError(f"No files found matching {file_pattern}")

    logger.info(f"Loading {len(all_files)} CSV files...")
    dataframes = []
    for file in all_files:
        try:
            df = pd.read_csv(file)
            dataframes.append(df)
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")

    if not dataframes:
        raise ValueError("No valid data files could be loaded")

    raw_data = pd.concat(dataframes, ignore_index=True)

    logger.info(f"Loaded {len(raw_data)} records from {len(all_files)} files.")

    # Check for missing values
    missing_values = raw_data.isnull().sum()
    if missing_values.sum() > 0:
        logger.warning(f"Missing values detected: {missing_values[missing_values > 0]}")

    if "Timestamp" in raw_data.columns:
        raw_data["Timestamp"] = pd.to_datetime(raw_data["Timestamp"])

    tracks = sorted(raw_data["Track"].unique())
    logger.info(f"Found {len(tracks)} unique tracks.")

    # Handle train lines
    if "Line" in raw_data.columns:
        train_lines = sorted(raw_data["Line"].unique())
        logger.info(f"Found {len(train_lines)} train lines.")
    else:
        line_cols = [col for col in raw_data.columns if col.startswith("Line_")]
        if line_cols:
            train_lines = [col.replace("Line_", "") for col in line_cols]
            logger.info(f"Found {len(train_lines)} lines from one-hot encoded columns.")
        else:
            logger.warning("No line information found. Creating placeholder.")
            train_lines = ["Unknown"]

    # Identify feature columns
    exclude_cols = {"Track", "Timestamp", "Train_ID"}
    feature_cols = [col for col in raw_data.columns if col not in exclude_cols]

    return raw_data, tracks, train_lines, feature_cols


def add_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add historical features (simplified version from model.py).

    Args:
        df: Input dataframe

    Returns:
        DataFrame with historical features (currently just returns copy)
    """
    logger.info("Historical track features have been simplified.")
    return df.copy()


def build_track_distributions(
    df: pd.DataFrame, tracks: List[str]
) -> Tuple[Dict, Dict, Dict, Dict, Dict, Dict]:
    """
    Build dictionaries mapping Train IDs, Lines, and Destinations to their track usage percentages
    and sample counts (adapted from model.py).

    Args:
        df: DataFrame with train records
        tracks: List of track identifiers

    Returns:
        Tuple of (train_id_dist, line_dist, dest_dist, train_id_total_counts, line_total_counts, dest_total_counts)
    """
    logger.info("Building track usage distribution maps...")

    # Initialize counters
    train_id_counts = defaultdict(lambda: defaultdict(int))
    line_counts = defaultdict(lambda: defaultdict(int))
    dest_counts = defaultdict(lambda: defaultdict(int))

    # Count occurrences
    for _, row in df.iterrows():
        train_id = str(row["Train_ID"])
        line = str(row["Line"])
        destination = str(row.get("Destination", "Unknown"))
        track = str(row["Track"])

        # Skip rows with missing track
        if pd.isna(track) or track == "":
            continue

        # Count this occurrence
        train_id_counts[train_id][track] += 1
        line_counts[line][track] += 1
        dest_counts[destination][track] += 1

    # Convert counts to percentages
    train_id_dist = {}
    line_dist = {}
    dest_dist = {}

    # Store total counts for each category
    train_id_total_counts = {}
    line_total_counts = {}
    dest_total_counts = {}

    # Process Train ID distributions
    for train_id, track_counts in train_id_counts.items():
        total = sum(track_counts.values())
        train_id_total_counts[train_id] = total
        train_id_dist[train_id] = {track: count / total for track, count in track_counts.items()}

    # Process Line distributions
    for line, track_counts in line_counts.items():
        total = sum(track_counts.values())
        line_total_counts[line] = total
        line_dist[line] = {track: count / total for track, count in track_counts.items()}

    # Process Destination distributions
    for dest, track_counts in dest_counts.items():
        total = sum(track_counts.values())
        dest_total_counts[dest] = total
        dest_dist[dest] = {track: count / total for track, count in track_counts.items()}

    logger.info(
        f"Built distributions for {len(train_id_dist)} train IDs, {len(line_dist)} lines, {len(dest_dist)} destinations"
    )

    return (
        train_id_dist,
        line_dist,
        dest_dist,
        train_id_total_counts,
        line_total_counts,
        dest_total_counts,
    )


def add_track_percentage_features(df: pd.DataFrame, tracks: List[str]) -> pd.DataFrame:
    """
    Add historical track usage percentage features based on Train ID, Line, and Destination
    (adapted from model.py).

    Args:
        df: DataFrame with train records
        tracks: List of all possible track values

    Returns:
        DataFrame with added percentage and count features
    """
    logger.info("Adding track usage percentage features and count features...")

    # Build distributions and counts
    train_id_dist, line_dist, dest_dist, train_id_counts, line_counts, dest_counts = (
        build_track_distributions(df, tracks)
    )

    # Create new dataframe to avoid SettingWithCopyWarning
    feature_df = df.copy()

    # Add percentage features for each record
    for i, row in feature_df.iterrows():
        train_id = str(row["Train_ID"])
        line = str(row["Line"])
        destination = str(row.get("Destination", "Unknown"))

        # Add count features
        feature_df.at[i, "TrainID_Count"] = train_id_counts.get(train_id, 0)
        feature_df.at[i, "Line_Count"] = line_counts.get(line, 0)
        feature_df.at[i, "Dest_Count"] = dest_counts.get(destination, 0)

        # Add percentage features for each track
        for track in tracks:
            # Train ID percentages
            feature_df.at[i, f"TrainID_Track_{track}_Pct"] = train_id_dist.get(train_id, {}).get(
                str(track), 0.0
            )

            # Line percentages
            feature_df.at[i, f"Line_Track_{track}_Pct"] = line_dist.get(line, {}).get(
                str(track), 0.0
            )

            # Destination percentages
            feature_df.at[i, f"Dest_Track_{track}_Pct"] = dest_dist.get(destination, {}).get(
                str(track), 0.0
            )

    # Log the number of features added
    num_pct_features = len(tracks) * 3  # 3 types of percentages for each track
    logger.info(f"Added {num_pct_features} track percentage features and 3 count features")

    return feature_df


def prepare_model_data_from_csv(
    df: pd.DataFrame, tracks: List[str], feature_cols: List[str], output_dir: str = "output"
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    int,
    int,
    List[str],
    Optional[np.ndarray],
    StandardScaler,
]:
    """
    Prepare data for model training with scaling and encoding (adapted from model.py).

    Args:
        df: DataFrame with train data
        tracks: List of track identifiers
        feature_cols: List of feature column names
        output_dir: Output directory for saving artifacts

    Returns:
        Tuple of training/test splits and metadata
    """
    logger.info("Encoding target variable...")
    target_encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    y_encoded = target_encoder.fit_transform(df["Track"].values.reshape(-1, 1))

    # Split categorical and numerical features
    categorical_cols = []
    if "Line" in df.columns and "Line" in feature_cols:
        categorical_cols.append("Line")
    if "Destination" in df.columns and "Destination" in feature_cols:
        categorical_cols.append("Destination")

    numerical_cols = [
        col for col in feature_cols if col not in categorical_cols and not col.startswith("Line_")
    ]
    numerical_cols = [col for col in numerical_cols if col in df.columns]

    if not numerical_cols:
        raise ValueError("No valid numerical features found")

    logger.info(
        f"Processing {len(numerical_cols)} numerical features and {len(categorical_cols)} categorical features."
    )

    # Process numerical features
    X_numerical = df[numerical_cols].copy()

    # Handle non-numeric values
    for col in X_numerical.columns:
        non_numeric = pd.to_numeric(X_numerical[col], errors="coerce").isna()
        if non_numeric.any():
            logger.warning(
                f"Column {col} has {non_numeric.sum()} non-numeric values. Replacing with mean."
            )
            col_mean = pd.to_numeric(X_numerical[col], errors="coerce").mean()
            X_numerical.loc[non_numeric, col] = col_mean

    # Scale numerical features
    scaler = StandardScaler()
    X_numerical_scaled = scaler.fit_transform(X_numerical)

    if np.isnan(X_numerical_scaled).any():
        logger.error("NaN values found after scaling numerical features! Replacing with 0.")
        X_numerical_scaled = np.nan_to_num(X_numerical_scaled)

    # Process categorical features
    X_categorical = pd.DataFrame()
    encoders = {}
    encoded_cat_cols = []

    for col in categorical_cols:
        if col in df.columns:
            logger.info(f"Encoding categorical feature: {col}")
            encoders[col] = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
            encoded = encoders[col].fit_transform(df[col].values.reshape(-1, 1))
            current_encoded_cols = [f"{col}_{cat}" for cat in encoders[col].categories_[0]]
            encoded_df = pd.DataFrame(encoded, columns=current_encoded_cols)
            encoded_cat_cols.extend(current_encoded_cols)

            X_categorical = pd.concat([X_categorical, encoded_df], axis=1)

    # Handle existing one-hot encoded Line features
    line_cols = [col for col in feature_cols if col.startswith("Line_") and col in df.columns]
    pre_encoded_line_features = []
    if line_cols:
        logger.info(f"Using {len(line_cols)} pre-encoded line features.")
        pre_encoded_line_features = df[line_cols].values

    # Combine features
    feature_components = [X_numerical_scaled]
    feature_names = numerical_cols.copy()

    if not X_categorical.empty:
        feature_components.append(X_categorical.values)
        feature_names.extend(encoded_cat_cols)
        logger.info(f"Added {X_categorical.shape[1]} newly encoded categorical features.")

    if len(pre_encoded_line_features) > 0:
        feature_components.append(pre_encoded_line_features)
        feature_names.extend(line_cols)
        logger.info(f"Added {len(line_cols)} pre-encoded line features.")

    X_all = np.column_stack(feature_components)
    logger.info(f"Combined feature matrix shape: {X_all.shape}")

    # Handle class weights
    unique_labels, counts = np.unique(np.argmax(y_encoded, axis=1), return_counts=True)
    total_samples = np.sum(counts)
    n_classes = len(unique_labels)
    class_weights = total_samples / (n_classes * counts)

    # Create intermediate training data file
    intermediate_df = pd.DataFrame(X_all, columns=feature_names)
    intermediate_df["Track"] = df["Track"].values

    # Add original metadata if available
    if "Train_ID" in df.columns:
        intermediate_df["Train_ID"] = df["Train_ID"].values
    if "Line" in df.columns:
        intermediate_df["Line"] = df["Line"].values
    if "Destination" in df.columns:
        intermediate_df["Destination"] = df["Destination"].values
    if "Timestamp" in df.columns:
        intermediate_df["Timestamp"] = df["Timestamp"].values

    # Save intermediate data
    output_path = Path(output_dir) / "model_artifacts"
    output_path.mkdir(parents=True, exist_ok=True)

    intermediate_df.to_csv(output_path / "intermediate_training_data.csv", index=False)
    logger.info(
        f"Saved intermediate training data to {output_path / 'intermediate_training_data.csv'}"
    )

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_encoded, test_size=0.2, random_state=42, stratify=np.argmax(y_encoded, axis=1)
    )
    logger.info(f"Training set: {X_train.shape}, Test set: {X_test.shape}")

    # Save preprocessing artifacts
    import joblib

    model_artifacts_dir = output_path
    joblib.dump(scaler, model_artifacts_dir / "scaler.pkl")
    joblib.dump(encoders, model_artifacts_dir / "encoders.pkl")
    joblib.dump(target_encoder, model_artifacts_dir / "target_encoder.pkl")
    joblib.dump(tracks, model_artifacts_dir / "tracks.pkl")

    with open(model_artifacts_dir / "feature_names.txt", "w") as f:
        f.write("\n".join(feature_names))

    return (
        X_train,
        X_test,
        y_train,
        y_test,
        X_all.shape[1],
        y_encoded.shape[1],
        feature_names,
        class_weights,
        scaler,
    )


def create_all_trains_json(csv_path: str, output_dir: str) -> bool:
    """
    Create JSON file from all_trains.csv (adapted from model.py).

    Args:
        csv_path: Path to the CSV file
        output_dir: Output directory

    Returns:
        True if successful, False otherwise
    """
    try:
        import json

        if not Path(csv_path).exists():
            logger.error(f"CSV file not found: {csv_path}")
            return False

        # Load CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded CSV with {len(df)} records")

        # Convert to JSON records
        records = df.to_dict("records")

        # Save JSON
        json_path = Path(output_dir) / "model_artifacts" / "all_trains.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)

        with open(json_path, "w") as f:
            json.dump(records, f, indent=2)

        logger.info(f"Successfully created JSON file: {json_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating JSON file: {e}")
        return False


# Class weights calculation helper
def calculate_class_weights(y_encoded: np.ndarray) -> np.ndarray:
    """
    Calculate class weights for imbalanced datasets.

    Args:
        y_encoded: One-hot encoded target labels

    Returns:
        Array of class weights
    """
    unique_labels, counts = np.unique(np.argmax(y_encoded, axis=1), return_counts=True)
    total_samples = np.sum(counts)
    n_classes = len(unique_labels)
    class_weights = total_samples / (n_classes * counts)

    logger.info(f"Calculated class weights for {n_classes} classes: {class_weights}")
    return class_weights
