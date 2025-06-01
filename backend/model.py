#!/usr/bin/env python3
#

import pandas as pd
import numpy as np
import os
import glob
import json
from datetime import datetime, timedelta
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, precision_recall_fscore_support
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import random
from collections import defaultdict
import logging
from sklearn.manifold import TSNE

# Define custom JSON encoder to handle NumPy types
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (float, np.float64)) and np.isnan(obj):
            return 0.0
        return super(NpEncoder, self).default(obj)

# Set up minimal logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set random seed for reproducibility
torch.manual_seed(42)
np.random.seed(42)

class TrackDataset(Dataset):
    """PyTorch Dataset for track prediction data."""
    
    def __init__(self, features, targets):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)
        
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

class TrackPredictor(nn.Module):
    """Feed-forward neural network for track prediction."""
    
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(TrackPredictor, self).__init__()
        logger.warning(f"Creating model with input_dim={input_dim}, hidden_dim={hidden_dim}, output_dim={output_dim}")
        # Remove softmax from the model definition to get logits
        self.features = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
        self.temperature = nn.Parameter(torch.ones(1) * 1.0)
        total_params = sum(p.numel() for p in self.parameters())
        logger.warning(f"Model created with {total_params} total parameters")
    
    def forward(self, x, apply_softmax=True, apply_temperature=False):
        """Forward pass with options for temperature scaling and softmax"""
        logits = self.features(x)
        
        if apply_temperature:
            # Apply temperature scaling - divide logits by temperature
            logits = logits / self.temperature
            
        if apply_softmax:
            # Apply softmax to convert logits to probabilities
            return F.softmax(logits, dim=1)
        else:
            # Return raw logits (needed for CrossEntropyLoss)
            return logits
    
    def calibrate(self, val_loader, criterion, device='cpu'):
        """
        Tune the temperature parameter on validation data to improve probability calibration.
        This is done after the main training is complete.
        """
        self.eval()  # Set to evaluation mode
        
        # Create a temperature optimization criterion and optimizer
        # We optimize only the temperature parameter
        optimizer = optim.LBFGS([self.temperature], lr=0.01, max_iter=50)
        
        # Define the temperature scaling loss
        def eval():
            optimizer.zero_grad()
            loss = 0
            batch_count = 0
            
            # We need gradients for temperature but not for model parameters
            for inputs, targets in val_loader:
                inputs = inputs.to(device)
                targets = targets.to(device)
                
                # Get raw logits (no softmax) - no gradient needed for logits
                with torch.no_grad():
                    logits = self.features(inputs)
                
                # Apply temperature scaling - WITH gradient for temperature
                scaled_logits = logits / self.temperature
                
                # Calculate loss
                batch_loss = criterion(scaled_logits, targets)
                loss += batch_loss * inputs.size(0)
                batch_count += inputs.size(0)
            
            loss = loss / batch_count
            loss.backward()
            return loss
        
        # Optimize the temperature parameter
        optimizer.step(eval)
        
        # Make sure temperature is positive
        self.temperature.data.clamp_(min=0.01)
        
        logger.warning(f"Temperature scaling parameter: {self.temperature.item():.4f}")
        return self.temperature.item()

def load_track_data(data_dir="output/processed_data"):
    """Load preprocessed track data files."""
    file_pattern = os.path.join(data_dir, "*.csv")
    all_files = [f for f in glob.glob(file_pattern) if "unassigned_trains" not in f]
    
    if not all_files:
        logger.error(f"No files found matching {file_pattern}")
        raise ValueError(f"No files found matching {file_pattern}")
    
    logger.warning(f"Loading {len(all_files)} CSV files...")
    dataframes = []
    for file in all_files:
        try:
            df = pd.read_csv(file)
            dataframes.append(df)
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")
    
    if not dataframes:
        logger.error("No valid data files could be loaded")
        raise ValueError("No valid data files could be loaded")
    
    raw_data = pd.concat(dataframes, ignore_index=True)
    
    # Minimal data logging
    logger.warning(f"Loaded {len(raw_data)} records from {len(all_files)} files.")
    
    # Check for missing values
    missing_values = raw_data.isnull().sum()
    if missing_values.sum() > 0:
        logger.warning(f"Missing values detected: {missing_values[missing_values > 0]}")
    
    if 'Timestamp' in raw_data.columns:
        raw_data['Timestamp'] = pd.to_datetime(raw_data['Timestamp'])
    
    tracks = sorted(raw_data['Track'].unique())
    logger.warning(f"Found {len(tracks)} unique tracks.")
    
    # Handle train lines
    if 'Line' in raw_data.columns:
        train_lines = sorted(raw_data['Line'].unique())
        logger.warning(f"Found {len(train_lines)} train lines.")
    else:
        line_cols = [col for col in raw_data.columns if col.startswith('Line_')]
        if line_cols:
            train_lines = [col.replace('Line_', '') for col in line_cols]
            logger.warning(f"Found {len(train_lines)} lines from one-hot encoded columns.")
        else:
            logger.warning("No line information found. Creating placeholder.")
            train_lines = ['Unknown']
            raw_data['Line'] = 'Unknown'
    
    # Optional: load tracks from file
    tracks_file = os.path.join(data_dir, "tracks.txt")
    if os.path.exists(tracks_file):
        with open(tracks_file, 'r') as f:
            tracks = f.read().splitlines()
            logger.warning(f"Loaded tracks from file: {tracks}")
    
    # Clean the data
    df = raw_data.copy()
    original_length = len(df)
    
    # Clean Destination field - strip airplane symbol, -SEC suffix, and trailing whitespace
    if 'Destination' in df.columns:
        # Count before cleaning to check impact
        unique_destinations_before = df['Destination'].nunique()
        
        # Remove HTML airplane entity, -SEC suffix, and trim whitespace
        df['Destination'] = df['Destination'].astype(str).str.replace('&#9992', '', regex=False)
        df['Destination'] = df['Destination'].str.replace('-SEC', '', regex=False)
        df['Destination'] = df['Destination'].str.strip()
        
        # Log cleaning results
        unique_destinations_after = df['Destination'].nunique()
        logger.warning(f"Cleaned Destination field: reduced from {unique_destinations_before} to {unique_destinations_after} unique values")
    
    df = df[df['Track'].notna() & (df['Track'] != 'N/A')]
    if len(df) < original_length:
        logger.warning(f"Removed {original_length - len(df)} rows with empty or N/A track values")
    
    track_dist = df['Track'].value_counts()
    low_count_tracks = track_dist[track_dist < 5]
    if not low_count_tracks.empty:
        logger.warning(f"Some tracks have very few examples (<5): {low_count_tracks}")
    
    # Define feature columns dynamically based on what's available
    feature_cols = [
        col for col in df.columns
        if any(x in col for x in ['Hour_', 'Day_Of_Week_', 'Is_Weekend', 'Is_Morning_Rush', 'Is_Evening_Rush'])
        or col.startswith('Track_') and col.endswith('_Last_Used')
        or col.startswith('Is_') and col.endswith('_Occupied')
        or col.startswith('Destination_')
        or col.startswith('Line_') # Include pre-encoded lines
        or col.startswith('TrainID_Track_') and col.endswith('_Pct')
        or col.startswith('Line_Track_') and col.endswith('_Pct')
        or col.startswith('Dest_Track_') and col.endswith('_Pct')
    ]
    
    # Add Line and Destination if they exist as direct columns
    if 'Line' in df.columns and 'Line' not in feature_cols:
         feature_cols.append('Line')
    if 'Destination' in df.columns and 'Destination' not in feature_cols:
         feature_cols.append('Destination')
    
    # Ensure all feature columns exist in the DataFrame
    existing_cols = [col for col in feature_cols if col in df.columns]
    
    if len(existing_cols) < len(feature_cols):
        missing = set(feature_cols) - set(existing_cols)
        logger.warning(f"Some expected features are missing: {missing}")
    
    logger.warning(f"Using {len(existing_cols)} features for the model.")
    
    return df, tracks, train_lines, existing_cols


def add_historical_features(df):
    """Simplified historical features function (removed historical_track and track_consistency features)."""
    logger.warning("Historical track features have been removed from the model.")
    
    # Simply return a copy of the original dataframe without adding historical features
    return df.copy()


def build_track_distributions(df, tracks):
    """
    Build dictionaries mapping Train IDs, Lines, and Destinations to their track usage percentages
    and sample counts.
    
    Returns:
        tuple: (train_id_dist, line_dist, dest_dist, train_id_total_counts, line_total_counts, dest_total_counts)
    """
    logger.warning("Building track usage distribution maps...")
    
    # Initialize counters
    train_id_counts = defaultdict(lambda: defaultdict(int))
    line_counts = defaultdict(lambda: defaultdict(int))
    dest_counts = defaultdict(lambda: defaultdict(int))
    
    # Count occurrences
    for _, row in df.iterrows():
        train_id = str(row['Train_ID'])
        line = str(row['Line'])
        destination = str(row.get('Destination', 'Unknown'))
        track = str(row['Track'])
        
        # Skip rows with missing track
        if pd.isna(track) or track == '':
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
        if total > 0:
            train_id_dist[train_id] = {track: count/total for track, count in track_counts.items()}
            train_id_total_counts[train_id] = total
    
    # Process Line distributions
    for line, track_counts in line_counts.items():
        total = sum(track_counts.values())
        if total > 0:
            line_dist[line] = {track: count/total for track, count in track_counts.items()}
            line_total_counts[line] = total
    
    # Process Destination distributions
    for dest, track_counts in dest_counts.items():
        total = sum(track_counts.values())
        if total > 0:
            dest_dist[dest] = {track: count/total for track, count in track_counts.items()}
            dest_total_counts[dest] = total
    
    # Log stats
    logger.warning(f"Built distributions for {len(train_id_dist)} Train IDs, {len(line_dist)} Lines, and {len(dest_dist)} Destinations")
    
    return train_id_dist, line_dist, dest_dist, train_id_total_counts, line_total_counts, dest_total_counts


def add_track_percentage_features(df, tracks):
    """
    Add historical track usage percentage features based on Train ID, Line, and Destination.
    Also add count features to indicate the sample size for each percentage.
    
    Args:
        df: DataFrame with train records
        tracks: List of all possible track values
        
    Returns:
        DataFrame with added percentage and count features
    """
    logger.warning("Adding track usage percentage features and count features...")
    
    # Build distributions and counts
    train_id_dist, line_dist, dest_dist, train_id_counts, line_counts, dest_counts = build_track_distributions(df, tracks)
    
    # Create new dataframe to avoid SettingWithCopyWarning
    feature_df = df.copy()
    
    # Add percentage features for each record
    for i, row in feature_df.iterrows():
        train_id = str(row['Train_ID'])
        line = str(row['Line'])
        destination = str(row.get('Destination', 'Unknown'))
        
        # Add count features
        feature_df.at[i, 'TrainID_Count'] = train_id_counts.get(train_id, 0)
        feature_df.at[i, 'Line_Count'] = line_counts.get(line, 0)
        feature_df.at[i, 'Dest_Count'] = dest_counts.get(destination, 0)
        
        # Add percentage features for each track
        for track in tracks:
            # Train ID percentages
            feature_df.at[i, f'TrainID_Track_{track}_Pct'] = train_id_dist.get(train_id, {}).get(str(track), 0.0)
            
            # Line percentages  
            feature_df.at[i, f'Line_Track_{track}_Pct'] = line_dist.get(line, {}).get(str(track), 0.0)
            
            # Destination percentages
            feature_df.at[i, f'Dest_Track_{track}_Pct'] = dest_dist.get(destination, {}).get(str(track), 0.0)
    
    # Log the number of features added
    num_pct_features = len(tracks) * 3  # 3 types of percentages for each track
    logger.warning(f"Added {num_pct_features} track percentage features and 3 count features")
    
    return feature_df

def prepare_model_data(df, tracks, feature_cols, output_dir="output"):
    """Prepare data for model training with scaling and encoding."""
    # Encode target variable (track)
    logger.warning("Encoding target variable...")
    target_encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    y_encoded = target_encoder.fit_transform(df['Track'].values.reshape(-1, 1))
    
    
    # Split categorical and numerical features
    categorical_cols = []
    if 'Line' in df.columns and 'Line' in feature_cols:
        categorical_cols.append('Line')
    if 'Destination' in df.columns and 'Destination' in feature_cols:
        categorical_cols.append('Destination')
        
    numerical_cols = [col for col in feature_cols if col not in categorical_cols and not col.startswith('Line_')] # Exclude pre-encoded lines
    numerical_cols = [col for col in numerical_cols if col in df.columns] # Ensure they exist
    
    if not numerical_cols:
        logger.error("No numerical features found!")
        raise ValueError("No valid numerical features found")
    
    logger.warning(f"Processing {len(numerical_cols)} numerical features and {len(categorical_cols)} categorical features.")
    
    # Process numerical features
    X_numerical = df[numerical_cols].copy()
    
    # Handle non-numeric values simply
    for col in X_numerical.columns:
        non_numeric = pd.to_numeric(X_numerical[col], errors='coerce').isna()
        if non_numeric.any():
            logger.warning(f"Column {col} has {non_numeric.sum()} non-numeric values. Replacing with mean.")
            col_mean = pd.to_numeric(X_numerical[col], errors='coerce').mean()
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
            logger.warning(f"Encoding categorical feature: {col}")
            encoders[col] = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
            encoded = encoders[col].fit_transform(df[col].values.reshape(-1, 1))
            current_encoded_cols = [f"{col}_{cat}" for cat in encoders[col].categories_[0]]
            encoded_df = pd.DataFrame(encoded, columns=current_encoded_cols)
            encoded_cat_cols.extend(current_encoded_cols)
            
            X_categorical = pd.concat([X_categorical, encoded_df], axis=1)
    
    # Handle existing one-hot encoded Line features
    line_cols = [col for col in feature_cols if col.startswith('Line_') and col in df.columns]
    pre_encoded_line_features = []
    if line_cols:
        logger.warning(f"Using {len(line_cols)} pre-encoded line features.")
        pre_encoded_line_features = df[line_cols].values
    
    # Combine features
    feature_components = [X_numerical_scaled]
    feature_names = numerical_cols.copy()
    
    if not X_categorical.empty:
        feature_components.append(X_categorical.values)
        feature_names.extend(encoded_cat_cols)
        logger.warning(f"Added {X_categorical.shape[1]} newly encoded categorical features.")
    
    if len(pre_encoded_line_features) > 0:
         feature_components.append(pre_encoded_line_features)
         feature_names.extend(line_cols)
         logger.warning(f"Added {len(line_cols)} pre-encoded line features.")
    
    if len(feature_components) > 1:
        X_all = np.hstack(feature_components)
    else:
        X_all = X_numerical_scaled # Only numerical features
    
    logger.warning(f"Final feature matrix shape: {X_all.shape}")
    
    # Check for NaN values in final feature matrix
    if np.isnan(X_all).any():
        logger.error("NaN values found in final feature matrix! Replacing with 0.")
        X_all = np.nan_to_num(X_all)
    
    # Check class imbalance for weighting
    class_counts = np.sum(y_encoded, axis=0)
    min_class = np.min(class_counts)
    max_class = np.max(class_counts)
    imbalance_ratio = max_class / min_class if min_class > 0 else float('inf')
    class_weights = None
    if imbalance_ratio > 5:
        logger.warning(f"Significant class imbalance detected (Ratio: {imbalance_ratio:.2f}). Applying class weights.")
        class_weights = 1.0 / class_counts
        class_weights[class_counts == 0] = 0 # Handle zero counts
        class_weights = class_weights / np.sum(class_weights) * len(class_counts)
        logger.warning(f"Calculated class weights.")
    
    # Save intermediate training data to CSV for debugging
    logger.warning("Saving intermediate training data to CSV for debugging...")
    
    # Create a DataFrame from the feature matrix
    intermediate_df = pd.DataFrame(X_all, columns=feature_names)
    
    # Add the target tracks (get the actual track values, not one-hot encoded)
    track_indices = np.argmax(y_encoded, axis=1)
    track_values = [tracks[idx] for idx in track_indices]
    intermediate_df['Target_Track'] = track_values
    
    # Add original metadata if available in the original dataframe
    if 'Train_ID' in df.columns:
        intermediate_df['Train_ID'] = df['Train_ID'].values
    if 'Line' in df.columns:
        intermediate_df['Line'] = df['Line'].values  
    if 'Destination' in df.columns:
        intermediate_df['Destination'] = df['Destination'].values
    if 'Timestamp' in df.columns:
        intermediate_df['Timestamp'] = df['Timestamp'].values
    
    # Save to the output directory in model_artifacts
    os.makedirs(os.path.join(output_dir, "model_artifacts"), exist_ok=True)
    output_path = os.path.join(output_dir, "model_artifacts", "intermediate_training_data.csv")
    intermediate_df.to_csv(output_path, index=False)
    logger.warning(f"Saved intermediate training data to {output_path}")
    
    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_encoded, test_size=0.2, random_state=42, stratify=np.argmax(y_encoded, axis=1)
    )
    logger.warning(f"Training set: {X_train.shape}, Test set: {X_test.shape}")
    
    # Save preprocessing artifacts
    model_artifacts_dir = os.path.join(output_dir, "model_artifacts")
    os.makedirs(model_artifacts_dir, exist_ok=True)
    joblib.dump(scaler, os.path.join(model_artifacts_dir, "scaler.pkl"))
    joblib.dump(encoders, os.path.join(model_artifacts_dir, "encoders.pkl"))
    joblib.dump(target_encoder, os.path.join(model_artifacts_dir, "target_encoder.pkl"))
    joblib.dump(tracks, os.path.join(model_artifacts_dir, "tracks.pkl"))
    
    with open(os.path.join(model_artifacts_dir, "feature_names.txt"), 'w') as f:
        f.write('\n'.join(feature_names))
    
    return X_train, X_test, y_train, y_test, X_all.shape[1], y_encoded.shape[1], feature_names, class_weights, scaler

def train_model(X_train, y_train, X_test, y_test, input_dim, output_dim, feature_names=None, class_weights=None,
                hidden_dim=64, batch_size=32, num_epochs=300, learning_rate=0.001, output_dir="output", 
                df=None, train_indices=None, test_indices=None, train_lines=None, tracks=None, X_all=None, scaler=None):
    """Train the PyTorch model."""
    # Create datasets and dataloaders
    train_dataset = TrackDataset(X_train, y_train)
    test_dataset = TrackDataset(X_test, y_test)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size)
    
    model = TrackPredictor(input_dim, hidden_dim, output_dim)
    logger.warning("Training track prediction model...")
    
    # Use weighted loss if weights are provided
    if class_weights is not None:
        logger.warning("Using weighted CrossEntropyLoss.")
        weight_tensor = torch.tensor(class_weights, dtype=torch.float32)
        criterion = nn.CrossEntropyLoss(weight=weight_tensor)
    else:
        criterion = nn.CrossEntropyLoss()
    
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=20 # verbose parameter removed
    )
    
    train_losses, val_losses, train_accuracies, val_accuracies = [], [], [], []
    best_val_acc = 0
    best_state_dict = None
    
    for epoch in range(num_epochs):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for inputs, targets in train_loader:
            # For training, get logits (apply_softmax=False) without temperature scaling
            logits = model(inputs, apply_softmax=False, apply_temperature=False)
            # CrossEntropyLoss expects logits, not softmax probabilities
            loss = criterion(logits, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * inputs.size(0)
            # Get predictions from logits
            _, predicted = torch.max(logits, 1)
            _, target_class = torch.max(targets, 1)
            train_correct += (predicted == target_class).sum().item()
            train_total += targets.size(0)
        
        train_loss /= len(train_loader.dataset)
        train_accuracy = train_correct / train_total
        train_losses.append(train_loss)
        train_accuracies.append(train_accuracy)
        
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for inputs, targets in test_loader:
                # For validation, get logits (apply_softmax=False) without temperature scaling
                logits = model(inputs, apply_softmax=False, apply_temperature=False)
                # CrossEntropyLoss expects logits, not softmax probabilities
                loss = criterion(logits, targets)
                val_loss += loss.item() * inputs.size(0)
                # Get predictions from logits
                _, predicted = torch.max(logits, 1)
                _, target_class = torch.max(targets, 1)
                val_correct += (predicted == target_class).sum().item()
                val_total += targets.size(0)
        
        val_loss /= len(test_loader.dataset)
        val_accuracy = val_correct / val_total
        val_losses.append(val_loss)
        val_accuracies.append(val_accuracy)
        
        scheduler.step(val_loss)
        
        if val_accuracy > best_val_acc:
            best_val_acc = val_accuracy
            best_state_dict = model.state_dict().copy()
            # no_improvement_count = 0
        # else:
            # no_improvement_count += 1
        
        if (epoch + 1) % 20 == 0: # Log less frequently
            logger.warning(f"Epoch {epoch+1}/{num_epochs}: Val Acc: {val_accuracy:.4f}")
        
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)
        logger.warning(f"Using best model with validation accuracy {best_val_acc:.4f}")
    
    # Save model
    model_artifacts_dir = os.path.join(output_dir, "model_artifacts")
    os.makedirs(model_artifacts_dir, exist_ok=True)
    model_save_path = os.path.join(model_artifacts_dir, "track_predictor_model.pt")
    torch.save(model.state_dict(), model_save_path)
    logger.warning(f"Saved model to {model_save_path}")
    
    # Calibrate model on validation data before final evaluation
    logger.warning("Calibrating model with temperature scaling...")
    # Create a validation set from the test data (we'll still keep a true test set for final evaluation)
    val_size = int(0.5 * len(test_dataset))
    val_indices = np.random.choice(len(test_dataset), val_size, replace=False)
    val_inputs = torch.stack([test_dataset[i][0] for i in val_indices])
    val_targets = torch.stack([test_dataset[i][1] for i in val_indices])
    val_dataset = torch.utils.data.TensorDataset(val_inputs, val_targets)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    
    # Create a holdout test set for final evaluation
    test_mask = np.ones(len(test_dataset), dtype=bool)
    test_mask[val_indices] = False
    test_indices_holdout = np.where(test_mask)[0]
    test_inputs = torch.stack([test_dataset[i][0] for i in test_indices_holdout])
    test_targets = torch.stack([test_dataset[i][1] for i in test_indices_holdout])
    holdout_dataset = torch.utils.data.TensorDataset(test_inputs, test_targets)
    holdout_loader = DataLoader(holdout_dataset, batch_size=batch_size)
    
    # Calculate metrics before calibration
    model.eval()
    uncalibrated_predictions, uncalibrated_targets, uncalibrated_probs = [], [], []
    with torch.no_grad():
        for inputs, targets in holdout_loader:
            # Get probabilities
            outputs = model(inputs, apply_softmax=True, apply_temperature=False)
            _, predicted = torch.max(outputs, 1)
            _, target_class = torch.max(targets, 1)
            uncalibrated_predictions.extend(predicted.numpy())
            uncalibrated_targets.extend(target_class.numpy())
            uncalibrated_probs.append(outputs.numpy())
    
    uncalibrated_probs = np.vstack(uncalibrated_probs)
    uncalibrated_accuracy = accuracy_score(uncalibrated_targets, uncalibrated_predictions)
    
    # Calculate Expected Calibration Error (ECE) before calibration
    def calculate_ece(probs, targets, n_bins=10):
        """Calculate Expected Calibration Error"""
        confidences = np.max(probs, axis=1)
        predictions = np.argmax(probs, axis=1)
        accuracies = (predictions == targets)
        
        ece = 0.0
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        for bin_lower, bin_upper in zip(bin_boundaries[:-1], bin_boundaries[1:]):
            in_bin = np.logical_and(confidences > bin_lower, confidences <= bin_upper)
            bin_size = np.sum(in_bin)
            
            if bin_size > 0:
                bin_confidence = np.mean(confidences[in_bin])
                bin_accuracy = np.mean(accuracies[in_bin])
                ece += bin_size * np.abs(bin_accuracy - bin_confidence)
                
        return ece / len(targets)
    
    uncalibrated_ece = calculate_ece(uncalibrated_probs, uncalibrated_targets)
    logger.warning(f"Before calibration - Accuracy: {uncalibrated_accuracy:.4f}, ECE: {uncalibrated_ece:.4f}")
    
    # Perform temperature scaling calibration
    temperature = model.calibrate(val_loader, criterion)
    logger.warning(f"Calibrated temperature parameter: {temperature:.4f}")
    
    # Evaluate final model with temperature scaling
    model.eval()
    all_predictions, all_targets, all_probs = [], [], []
    
    # Store the actual indices used for prediction to match with original data
    holdout_indices = []
    current_idx = 0
    
    with torch.no_grad():
        for inputs, targets in holdout_loader:
            # Apply temperature scaling for final evaluation
            outputs = model(inputs, apply_softmax=True, apply_temperature=True)
            _, predicted = torch.max(outputs, 1)
            _, target_class = torch.max(targets, 1)
            all_predictions.extend(predicted.numpy())
            all_targets.extend(target_class.numpy())
            all_probs.append(outputs.numpy())
            
            # Track the actual indices used for predictions
            batch_size = inputs.shape[0]
            holdout_indices.extend(test_indices_holdout[current_idx:current_idx + batch_size])
            current_idx += batch_size
    
    all_probs = np.vstack(all_probs)
    final_accuracy = accuracy_score(all_targets, all_predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(all_targets, all_predictions, average='weighted', zero_division=0)
    cm = confusion_matrix(all_targets, all_predictions)
    class_report = classification_report(all_targets, all_predictions, output_dict=True, zero_division=0)
    
    # Calculate ECE after calibration
    calibrated_ece = calculate_ece(all_probs, all_targets)
    logger.warning(f"After calibration - Accuracy: {final_accuracy:.4f}, ECE: {calibrated_ece:.4f}")
    logger.warning(f"ECE reduction: {(uncalibrated_ece - calibrated_ece) / uncalibrated_ece * 100:.2f}%")
    
    # ADDITIONALLY run the final model on the latest data
    # Find the latest data file
    import glob
    track_data_files = sorted(glob.glob("track_data/track_data/New_York_Penn_Station_*.csv"))
    latest_data_path = track_data_files[-1] if track_data_files else None
    if latest_data_path:
        logger.warning(f"Running final model on latest data from {latest_data_path}")
    else:
        logger.warning("No latest data files found in track_data/track_data/")
    
    # Try to load the most recent processed data for more accurate feature values
    recent_processed_data = None
    try:
        processed_data_path = "processed_data/processed_data/track_data_final.csv"
        if os.path.exists(processed_data_path):
            # Load the last few rows (most recent data)
            recent_processed_data = pd.read_csv(processed_data_path, nrows=10)
            if len(recent_processed_data) > 0:
                # Sort by timestamp to ensure we get the most recent data
                if 'Timestamp' in recent_processed_data.columns:
                    recent_processed_data['Timestamp'] = pd.to_datetime(recent_processed_data['Timestamp'])
                    recent_processed_data = recent_processed_data.sort_values('Timestamp', ascending=False)
                # Get the most recent row
                recent_data = recent_processed_data.iloc[0]
                logger.warning(f"Loaded recent processed data from {processed_data_path}")
    except Exception as e:
        logger.warning(f"Could not load recent processed data: {e}")
        recent_processed_data = None
    
    if os.path.exists(latest_data_path):
        # Load latest data
        latest_df = pd.read_csv(latest_data_path)
        logger.warning(f"Loaded {len(latest_df)} trains from latest data")
        
        # Helper function to find similar train for feature values
        def find_similar_train_features(train_id, line, destination, df):
            """Find feature values from a similar train in historical data."""
            # First try exact match on train_id
            matches = df[df['Train_ID'] == train_id]
            if len(matches) > 0:
                return matches.iloc[-1]  # Return the most recent match
            
            # Next try to match by line
            matches = df[df['Line'] == line]
            if len(matches) > 0:
                return matches.iloc[-1]
            
            # Finally try to match by destination
            if destination and destination != 'Unknown':
                matches = df[df['Destination'] == destination]
                if len(matches) > 0:
                    return matches.iloc[-1]
            
            # If no matches found, return None
            return None
        
        # Prepare features for the latest data
        # Create a feature dataframe similar to what infer.py does
        latest_features = []
        
        for _, train in latest_df.iterrows():
            # Extract basic info
            timestamp = pd.to_datetime(train['Timestamp'])
            train_id = train['Train_ID']
            line = train['Line']
            destination = train.get('Destination', 'Unknown')
            
            # Remember if train has an assigned track for later
            train_has_track = not pd.isna(train['Track']) and train['Track'] != ''
            
            # Initialize feature dict
            features = {}
            
            # Add temporal features
            hour = timestamp.hour
            day_of_week = timestamp.dayofweek
            
            # Cyclic encoding of hour and day of week
            features['Hour_Sin'] = np.sin(2 * np.pi * hour/24)
            features['Hour_Cos'] = np.cos(2 * np.pi * hour/24)
            features['Day_Of_Week_Sin'] = np.sin(2 * np.pi * day_of_week/7)
            features['Day_Of_Week_Cos'] = np.cos(2 * np.pi * day_of_week/7)
            
            # Add other temporal flags
            features['Is_Weekend'] = 1 if day_of_week >= 5 else 0
            features['Is_Morning_Rush'] = 1 if 7 <= hour <= 10 else 0
            features['Is_Evening_Rush'] = 1 if 16 <= hour <= 19 else 0
            
            # Set track occupation features
            for track in tracks:
                track_str = str(track)
                # Get trains with this track assigned
                assigned_tracks = latest_df[latest_df['Track'] == track_str]
                if len(assigned_tracks) > 0:
                    features[f'Is_{track}_Occupied'] = 1
                    features[f'Track_{track}_Last_Used'] = 0  # Currently in use
                else:
                    features[f'Is_{track}_Occupied'] = 0
                    
                    # Try to get real track last used time from recent processed data
                    track_last_used_column = f"Track_{track}_Last_Used"
                    if recent_processed_data is not None and track_last_used_column in recent_data:
                        features[f'Track_{track}_Last_Used'] = recent_data[track_last_used_column]
                        logger.info(f"Using real Track_{track}_Last_Used value: {features[f'Track_{track}_Last_Used']}")
                    else:
                        # Only fall back to default if we couldn't find real data
                        features[f'Track_{track}_Last_Used'] = 30  # Default to 30 minutes
                        logger.warning(f"Using default value for Track_{track}_Last_Used")
            
            # One-hot encode Line
            for line_col in [col for col in feature_names if col.startswith('Line_')]:
                line_name = line_col.replace('Line_', '')
                if line == line_name:
                    features[line_col] = 1
                else:
                    features[line_col] = 0
            
            # Historical track features and Track_Consistency have been removed
            
            # Using the last sample in training data to fill in missing features
            # Get the last entry from the training data
            last_train_features = None
            if X_all is not None and len(X_all) > 0:
                last_train_features = X_all[-1]
            
            latest_features.append(features)
        
        if len(latest_features) > 0:
            # Convert to DataFrame
            latest_features_df = pd.DataFrame(latest_features)
            
            # Create a proper feature matrix that matches the model's expected features
            X_latest = np.zeros((len(latest_features_df), len(feature_names)))
            
            # Fill in values from latest_features_df where available
            for i, feature in enumerate(feature_names):
                if feature in latest_features_df.columns:
                    X_latest[:, i] = latest_features_df[feature].values
                else:
                    # Try to get missing feature values from different sources
                    feature_filled = False
                    
                    # Try to get values from similar trains for each sample
                    for idx, (_, train) in enumerate(latest_df.iterrows()):
                        train_id = train['Train_ID']
                        line = train['Line']
                        destination = train.get('Destination', 'Unknown')
                        
                        # Find a similar train for this specific instance
                        similar_train = find_similar_train_features(train_id, line, destination, df)
                        if similar_train is not None and feature in similar_train:
                            X_latest[idx, i] = similar_train[feature]
                            feature_filled = True
                            logger.info(f"Feature {feature} filled from similar train {similar_train['Train_ID']} for train {train_id}")
                    
                    # If we couldn't find values from similar trains, try recent processed data
                    if not feature_filled and recent_processed_data is not None and feature in recent_data:
                        X_latest[:, i] = recent_data[feature]
                        feature_filled = True
                        logger.warning(f"Feature {feature} filled from recent processed data")
                    
                    # If still not filled, use last training sample as a fallback
                    if not feature_filled and last_train_features is not None:
                        default_value = last_train_features[i]
                        X_latest[:, i] = default_value
                        logger.warning(f"Feature {feature} missing from latest data, using fallback value {default_value}")
                    
                    # As a last resort, use zero (should rarely get here with our improved sources)
                    if not feature_filled:
                        logger.warning(f"Feature {feature} missing and no suitable values found, using 0")
                        X_latest[:, i] = 0
            
            # Scale numerical features
            X_latest_scaled = X_latest.copy()
            
            # Apply the scaler to get properly scaled features
            numerical_indices = []
            for i, feature in enumerate(feature_names):
                # Skip one-hot encoded features
                if not feature.startswith('Line_') and not feature.startswith('Destination_'):
                    numerical_indices.append(i)
            
            if len(numerical_indices) > 0:
                # Extract just the numerical columns
                X_numerical = X_latest[:, numerical_indices]
                # Apply scaling
                X_numerical_scaled = scaler.transform(X_numerical)
                # Put the scaled values back
                for i, idx in enumerate(numerical_indices):
                    X_latest_scaled[:, idx] = X_numerical_scaled[:, i]
            
            # Make predictions
            X_latest_tensor = torch.tensor(X_latest_scaled, dtype=torch.float32)
            with torch.no_grad():
                # Apply temperature scaling for better calibrated probabilities
                latest_outputs = model(X_latest_tensor, apply_softmax=True, apply_temperature=True)
                _, latest_predicted = torch.max(latest_outputs, 1)
                latest_probs = latest_outputs.numpy()
            
            # Generate SHAP explanations for predictions
            logger.warning("Generating SHAP explanations for predictions...")
            try:
                # Create a background dataset - use a sample of the training data if available
                # For simplicity, we'll use X_all as background if it exists, otherwise use X_latest_scaled
                background_data = X_all[:min(100, len(X_all))] if X_all is not None and len(X_all) > 0 else X_latest_scaled[:min(5, len(X_latest_scaled))]
                
                # Convert to torch tensor
                background_tensor = torch.tensor(background_data, dtype=torch.float32)
                
                # Define a function to get model predictions with error handling
                def model_predict(x):
                    try:
                        with torch.no_grad():
                            tensor_x = torch.tensor(x, dtype=torch.float32)
                            if tensor_x.shape[1] != len(feature_names):
                                # Pad or truncate to match expected dimensions
                                if tensor_x.shape[1] < len(feature_names):
                                    padding = torch.zeros((tensor_x.shape[0], len(feature_names) - tensor_x.shape[1]), dtype=torch.float32)
                                    tensor_x = torch.cat([tensor_x, padding], dim=1)
                                else:
                                    tensor_x = tensor_x[:, :len(feature_names)]
                            result = model(tensor_x, apply_softmax=True, apply_temperature=True).numpy()
                            return result
                    except Exception as e:
                        logger.error(f"Error in model prediction: {e}")
                        # Return zeros as a fallback
                        return np.zeros((x.shape[0], len(tracks)))
                
                # Use a much simpler approach instead of trying to use SHAP libraries
                # This approach calculates basic feature importance directly
                logger.warning("Using direct feature importance calculation instead of SHAP")
                
                try:
                    # Create a very simple explanation approach based on feature values and model sensitivity
                    # This is more reliable than trying to use complex SHAP calculations that may fail
                    
                    # Step 1: First get the predictions for the baseline
                    X_tensor = torch.tensor(X_latest_scaled, dtype=torch.float32)
                    with torch.no_grad():
                        base_predictions = model(X_tensor, apply_softmax=True, apply_temperature=True).numpy()
                    
                    # Initialize storage for our direct feature importance values
                    # For each sample and each track, we'll store importance values for each feature
                    num_samples = X_latest_scaled.shape[0]
                    num_tracks = len(tracks)
                    num_features = len(feature_names)
                    
                    # Create a list of lists to store importance values
                    # Format will be: [track_idx][sample_idx] = array of feature importances
                    importance_values = []
                    
                    # For each track (class)
                    for track_idx in range(num_tracks):
                        track_importances = []
                        
                        # For each sample
                        for sample_idx in range(num_samples):
                            # Get baseline prediction probability for this track
                            baseline_prob = base_predictions[sample_idx, track_idx]
                            
                            # Calculate feature importances for this sample and track
                            feature_importances = np.zeros(num_features)
                            
                            # Calculate importance by perturbing each feature
                            for feat_idx in range(num_features):
                                # Create a perturbed sample
                                perturbed_sample = X_latest_scaled[sample_idx].copy()
                                
                                # Perturb this feature (set to zero)
                                perturbed_sample[feat_idx] = 0
                                
                                # Get prediction with this feature perturbed
                                perturbed_tensor = torch.tensor(perturbed_sample.reshape(1, -1), dtype=torch.float32)
                                with torch.no_grad():
                                    perturbed_pred = model(perturbed_tensor, apply_softmax=True, apply_temperature=True).numpy()
                                
                                # Calculate importance as difference in prediction
                                feature_importances[feat_idx] = baseline_prob - perturbed_pred[0, track_idx]
                            
                            track_importances.append(feature_importances)
                        
                        importance_values.append(track_importances)
                    
                    # Store as numpy arrays
                    shap_values = importance_values
                    
                except Exception as e:
                    logger.warning(f"Feature importance calculation failed: {e}")
                    # Return empty explanations instead of misleading default factors
                    shap_values = []
                
                # Store the feature importance values and other necessary data for later use
                shap_data = {
                    'shap_values': shap_values,
                    'feature_names': feature_names,
                    'prediction_idx': latest_predicted,
                    'tracks': tracks,
                    'probabilities': latest_probs
                }
                
                logger.warning(f"Generated feature importance explanations for {len(X_latest_scaled)} predictions")
            except Exception as e:
                logger.error(f"Error generating feature importance explanations: {e}")
                shap_data = None
            

            # Generate prediction factors based on feature importance values
            def generate_prediction_factors(sample_idx, pred_track_idx, shap_data, feature_values):
                if shap_data is None or 'shap_values' not in shap_data:
                    logger.warning("No feature importance data available.")
                    return {"prediction_factors": []}
                
                try:
                    # Get importance values - with safety checks for dimensions
                    imp_values = shap_data['shap_values']
                    feature_names = shap_data['feature_names']
                    tracks = shap_data['tracks']
                    
                    # Handle empty importance values (when calculation failed)
                    if not imp_values:
                        logger.warning("Empty feature importance values. Skipping explanation.")
                        return {"prediction_factors": []}
                    
                    # Verify the dimensions are correct
                    if not isinstance(imp_values, list) or len(imp_values) <= pred_track_idx:
                        logger.warning(f"Feature importance values dimension mismatch. Skipping explanation.")
                        return {"prediction_factors": []}
                    
                    # Get importance values for this specific track
                    track_imp_values = imp_values[pred_track_idx]
                    
                    # Check if sample_idx is within range
                    if sample_idx >= len(track_imp_values):
                        logger.warning(f"Sample index {sample_idx} out of bounds (max: {len(track_imp_values)-1}). Skipping explanation.")
                        return {"prediction_factors": []}
                    
                    # Get the importance values for this specific sample
                    sample_imp_values = track_imp_values[sample_idx]
                    
                    # Check if feature dimensions match
                    if len(sample_imp_values) != len(feature_names):
                        logger.warning(f"Feature dimension mismatch: Importance values ({len(sample_imp_values)}) vs feature names ({len(feature_names)}). Skipping explanation.")
                        return {"prediction_factors": []}
                    
                    # Pair feature names with their importance values and sort by absolute value
                    factor_pairs = [(feature_names[i], sample_imp_values[i]) for i in range(len(feature_names))]
                    sorted_factors = sorted(factor_pairs, key=lambda x: abs(x[1]), reverse=True)
                    
                    # Take up to 10 significant factors with significance > 3%
                    significant_factors = []
                    factor_idx = 0
                    while len(significant_factors) < 10 and factor_idx < len(sorted_factors):
                        feature_name, importance_value = sorted_factors[factor_idx]
                        
                        # Check if this is a "track available" factor which we want to skip
                        skip_available_track = False
                        if "Is_" in feature_name and "_Occupied" in feature_name and importance_value > 0:
                            # This is a "track is available" factor - skip it
                            skip_available_track = True
                        
                        # Only include factors with importance >= 0.01 (1%)
                        # And don't include "track is available" factors
                        if abs(importance_value) >= 0.01 and not skip_available_track:
                            # Get the explanation
                            explanation = get_factor_explanation(feature_name, importance_value, feature_values, pred_track_idx, tracks)
                            
                            factor = {
                                "feature": get_friendly_feature_name(feature_name),
                                "importance": round(abs(importance_value), 2),
                                "direction": "positive" if importance_value > 0 else "negative",
                                "explanation": explanation
                            }
                            significant_factors.append(factor)
                        
                        factor_idx += 1
                    
                    # Return only the prediction factors, no counterfactual insight
                    return {
                        "prediction_factors": significant_factors
                    }
                    
                except Exception as e:
                    logger.error(f"Error generating prediction factors: {e}")
                    # Return empty explanations instead of potentially misleading defaults
                    return {"prediction_factors": []}
            
            # We've removed the default factors generation function since we now return empty lists
            # This approach is more honest and prevents misleading explanations when SHAP or direct importance calculations fail
                
            # Helper function to convert raw feature names to user-friendly names
            def get_friendly_feature_name(feature_name):
                if "Track_" in feature_name and "_Last_Used" in feature_name:
                    return "track_recency"
                elif "Is_" in feature_name and "_Occupied" in feature_name:
                    return "current_track_occupancy"
                elif "Hour_" in feature_name:
                    return "time_of_day"
                elif "Day_Of_Week_" in feature_name:
                    return "day_of_week"
                elif "Is_Morning_Rush" in feature_name or "Is_Evening_Rush" in feature_name:
                    return "rush_hour_pattern"
                elif "Is_Weekend" in feature_name:
                    return "weekend_pattern"
                elif "TrainID_Track_" in feature_name and "_Pct" in feature_name:
                    return "train_historical_track_frequency"
                elif "Line_Track_" in feature_name and "_Pct" in feature_name:
                    return "line_historical_track_frequency"
                elif "Dest_Track_" in feature_name and "_Pct" in feature_name:
                    return "destination_historical_track_frequency"
                elif "Line_" in feature_name:
                    return "line_assignment_pattern"
                elif "Destination_" in feature_name:
                    return "destination_pattern"
                else:
                    return feature_name.lower().replace("_", "_")
            
            # Function to generate natural language explanation for a factor
            def get_factor_explanation(feature, importance, feature_values, track_idx, tracks):
                track = str(tracks[track_idx])
                explanation = ""
                
                # Handle different feature types
                if "Line_" in feature:
                    line_name = feature.replace("Line_", "")
                    value = feature_values.get(feature, 0)
                    if value > 0:
                        explanation = f"{line_name} trains are frequently assigned to Track {track}"
                    else:
                        explanation = f"{line_name} trains are rarely assigned to Track {track}"
                
                elif "Track_" in feature and "_Last_Used" in feature:
                    track_num = feature.split("_")[1]
                    # Convert track_num to integer if possible
                    try:
                        track_num = int(float(track_num))
                    except (ValueError, TypeError):
                        # Keep as is if conversion fails
                        pass
                        
                    if importance > 0:
                        explanation = f"Track {track_num} has not been used recently"
                    else:
                        explanation = f"Track {track_num} was recently used by another train"
                
                elif "Is_" in feature and "_Occupied" in feature:
                    track_num = feature.split("_")[1]
                    # Convert track_num to integer if possible
                    try:
                        track_num = int(float(track_num))
                    except (ValueError, TypeError):
                        # Keep as is if conversion fails
                        pass
                        
                    if importance > 0:
                        explanation = f"Track {track_num} is currently available"
                    else:
                        explanation = f"Track {track_num} is currently occupied"
                
                elif "Hour_" in feature or "Day_Of_Week_" in feature:
                    if importance > 0:
                        explanation = f"Time of day pattern favors Track {track}"
                    else:
                        explanation = f"Time of day pattern disfavors Track {track}"
                
                elif "Is_Morning_Rush" in feature or "Is_Evening_Rush" in feature:
                    rush_type = "morning" if "Morning" in feature else "evening"
                    value = feature_values.get(feature, 0)
                    if (value > 0 and importance > 0) or (value == 0 and importance < 0):
                        explanation = f"During {rush_type} rush hour, Track {track} is frequently used"
                    else:
                        explanation = f"Outside of {rush_type} rush hour, Track {track} is more likely"
                
                elif "Is_Weekend" in feature:
                    value = feature_values.get(feature, 0)
                    if (value > 0 and importance > 0) or (value == 0 and importance < 0):
                        explanation = f"On weekends, Track {track} is more commonly used"
                    else:
                        explanation = f"On weekdays, Track {track} is more commonly used"
                
                elif "Destination_" in feature:
                    dest = feature.replace("Destination_", "")
                    if importance > 0:
                        explanation = f"Trains to {dest} frequently use Track {track}"
                    else:
                        explanation = f"Trains to {dest} rarely use Track {track}"
                        
                elif "TrainID_Track_" in feature and "_Pct" in feature:
                    track_num = feature.split("_")[2]
                    try:
                        track_num = int(float(track_num))
                    except (ValueError, TypeError):
                        pass
                    
                    value = feature_values.get(feature, 0)
                    if value > 0.5:
                        explanation = f"This train often uses Track {track_num}"
                    elif value > 0.1:
                        explanation = f"This train occasionally uses Track {track_num}"
                    else:
                        explanation = f"This train rarely uses Track {track_num}"
                
                elif "Line_Track_" in feature and "_Pct" in feature:
                    track_num = feature.split("_")[2]
                    try:
                        track_num = int(float(track_num))
                    except (ValueError, TypeError):
                        pass
                    
                    value = feature_values.get(feature, 0)
                    if importance > 0:
                        explanation = f"Trains on this line use Track {track_num} {int(value*100)}% of the time"
                    else:
                        explanation = f"Trains on this line rarely use Track {track_num}"
                
                elif "Dest_Track_" in feature and "_Pct" in feature:
                    track_num = feature.split("_")[2]
                    try:
                        track_num = int(float(track_num))
                    except (ValueError, TypeError):
                        pass
                    
                    value = feature_values.get(feature, 0)
                    if importance > 0:
                        explanation = f"Trains to this destination use Track {track_num} {int(value*100)}% of the time"
                    else:
                        explanation = f"Trains to this destination rarely use Track {track_num}"
                
                else:
                    # Generic explanation
                    explanation = f"Feature '{feature}' {'increases' if importance > 0 else 'decreases'} likelihood of Track {track}"
                
                return explanation
            
            # We've removed the counterfactual insight generator as it's no longer used
            
            # Create a dataframe with the predictions
            latest_results = []
            
            for i, (_, train) in enumerate(latest_df.iterrows()):
                if i >= len(latest_predicted):
                    break
                    
                train_id = train['Train_ID']
                line = train['Line']
                destination = train.get('Destination', 'Unknown')
                
                # First try to get date from Trip_ID before using timestamp
                date_part = None
                if not pd.isna(train.get('Trip_ID', None)):
                    trip_id = str(train.get('Trip_ID', ''))
                    if '_' in trip_id:
                        parts = trip_id.split('_')
                        if len(parts) >= 1 and len(parts[0]) >= 10:  # Basic check for date format
                            try:
                                # Validate it's a proper date
                                pd.to_datetime(parts[0])
                                date_part = parts[0]
                            except:
                                date_part = None
                
                # Get the timestamp for date fallback if Trip_ID doesn't have a date
                timestamp = pd.to_datetime(train.get('Timestamp', pd.Timestamp.now()))
                departure_time = train['Departure_Time']
                
                # Create full datetime from departure time and date
                try:
                    # Check if departure_time already has date component
                    if isinstance(departure_time, str) and len(departure_time) <= 8:
                        # Only time component available (e.g., "08:30 AM")
                        departure_parts = departure_time.strip().split(' ')
                        time_part = departure_parts[0]
                        ampm_part = departure_parts[1] if len(departure_parts) > 1 else ''
                        
                        # Create full datetime string - prioritize date from Trip_ID
                        date_str = date_part if date_part else timestamp.strftime('%Y-%m-%d')
                        full_departure = f"{date_str} {time_part} {ampm_part}".strip()
                    else:
                        # Use as is - might already be full datetime
                        full_departure = departure_time
                except Exception as e:
                    # Fall back to original value if parsing fails
                    logger.warning(f"Error parsing departure time: {e}")
                    full_departure = departure_time
                
                departure = full_departure
                status = train['Status'] if not pd.isna(train['Status']) and str(train['Status']).strip() != '' else 'On Time'
                
                # Get top 10 predictions
                probs = latest_probs[i]
                top_indices = np.argsort(probs)[::-1][:10]
                top_tracks = [tracks[idx] for idx in top_indices]
                top_probs = [probs[idx] for idx in top_indices]
                
                # Generate Trip_ID if not in the original train data
                trip_id = ''
                if 'Trip_ID' in train and not pd.isna(train['Trip_ID']):
                    trip_id = train['Trip_ID']
                else:
                    # Create Trip_ID from Departure and Train_ID
                    try:
                        # Try to get date part from departure
                        date_part = ''
                        if isinstance(departure, str) and ' ' in departure:
                            date_parts = departure.split(' ')[0].split('-')
                            if len(date_parts) == 3:
                                # Looks like we have YYYY-MM-DD format
                                date_part = departure.split(' ')[0]
                        
                        # If we couldn't extract date, use today's date
                        if not date_part:
                            date_part = datetime.now().strftime('%Y-%m-%d')
                        
                        # Clean Train_ID
                        clean_train_id = str(train_id).strip()
                        
                        # Create Trip_ID
                        time_part = departure.split(' ')[-2] if ' ' in departure else departure
                        trip_id = f"{date_part}_{clean_train_id}_{time_part}"
                        
                        # Cleanup any double spaces or problematic characters
                        trip_id = trip_id.replace('  ', ' ').strip()
                    except Exception as e:
                        # If generation fails, create a basic Trip_ID
                        trip_id = f"{datetime.now().strftime('%Y-%m-%d')}_{train_id}"

                result = {
                    'Train_ID': train_id,
                    'Trip_ID': trip_id,
                    'Line': line,
                    'Destination': destination,
                    'Departure': departure,
                    'Status': status,
                    'Track': train['Track'] if not pd.isna(train['Track']) else '',
                    'Pred_Track_1': top_tracks[0],
                    'Prob_1': top_probs[0],
                    'Pred_Track_2': top_tracks[1] if len(top_tracks) > 1 else '',
                    'Prob_2': top_probs[1] if len(top_probs) > 1 else 0,
                    'Pred_Track_3': top_tracks[2] if len(top_tracks) > 2 else '',
                    'Prob_3': top_probs[2] if len(top_probs) > 2 else 0,
                    'Pred_Track_4': top_tracks[3] if len(top_tracks) > 3 else '',
                    'Prob_4': top_probs[3] if len(top_probs) > 3 else 0,
                    'Pred_Track_5': top_tracks[4] if len(top_tracks) > 4 else '',
                    'Prob_5': top_probs[4] if len(top_probs) > 4 else 0,
                    'Pred_Track_6': top_tracks[5] if len(top_tracks) > 5 else '',
                    'Prob_6': top_probs[5] if len(top_probs) > 5 else 0,
                    'Pred_Track_7': top_tracks[6] if len(top_tracks) > 6 else '',
                    'Prob_7': top_probs[6] if len(top_probs) > 6 else 0,
                    'Pred_Track_8': top_tracks[7] if len(top_tracks) > 7 else '',
                    'Prob_8': top_probs[7] if len(top_probs) > 7 else 0,
                    'Pred_Track_9': top_tracks[8] if len(top_tracks) > 8 else '',
                    'Prob_9': top_probs[8] if len(top_probs) > 8 else 0,
                    'Pred_Track_10': top_tracks[9] if len(top_tracks) > 9 else '',
                    'Prob_10': top_probs[9] if len(top_probs) > 9 else 0
                }
                
                # Add all track probabilities
                for j, track in enumerate(tracks):
                    result[f'Track_{track}_Prob'] = probs[j]
                
                # Add feature values dictionary for explanation generation
                feature_values = {}
                for j, feature in enumerate(feature_names):
                    if j < len(X_latest_scaled[i]):
                        feature_values[feature] = X_latest_scaled[i][j]
                
                # Add prediction factors if SHAP data is available
                if shap_data is not None and i < len(latest_predicted):
                    try:
                        track_idx = latest_predicted[i].item()
                        explanation_data = generate_prediction_factors(i, track_idx, shap_data, feature_values)
                        if explanation_data:
                            # Store the serializable version first
                            try:
                                # Stringify the prediction factors to JSON for DataFrame storage
                                result['prediction_factors_json'] = json.dumps(explanation_data['prediction_factors'])
                                
                                # For direct access in memory (not for DataFrame storage)
                                # We'll extract these when building the JSON output and avoid DataFrame issues
                                result['_prediction_factors'] = explanation_data['prediction_factors']
                            except Exception as json_error:
                                logger.error(f"Error serializing prediction factors: {json_error}")
                    except Exception as e:
                        logger.error(f"Error adding prediction factors to result: {e}")
                
                latest_results.append(result)
            
            # Save predictions to CSV and JSON
            if latest_results:
                latest_results_df = pd.DataFrame(latest_results)
                
                # Add source column to differentiate between test and latest data
                latest_results_df['Source'] = 'Latest Data'
                
                # Save separate latest predictions as CSV
                latest_predictions_path = os.path.join(output_dir, "model_artifacts", "latest_predictions.csv")
                latest_results_df.to_csv(latest_predictions_path, index=False)
                logger.warning(f"Saved {len(latest_results_df)} predictions on latest data to {latest_predictions_path}")
                
                # Save latest predictions as JSON
                latest_json_path = os.path.join(output_dir, "model_artifacts", "latest_predictions.json")
                
                # Create the JSON structure
                json_data = {
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "model_version": "1.0",
                        "prediction_count": len(latest_results_df)
                    },
                    "predictions": []
                }
                
                # Process each prediction for JSON format
                for _, row in latest_results_df.iterrows():
                    # Get track probability columns
                    track_prob_cols = [col for col in latest_results_df.columns if col.startswith('Track_') and col.endswith('_Prob')]
                    
                    # Extract track probabilities
                    all_track_probs = {}
                    for col in track_prob_cols:
                        track = col.replace('Track_', '').replace('_Prob', '')
                        # Handle NaN values - replace with 0
                        prob_value = row[col]
                        if pd.isna(prob_value):
                            prob_value = 0.0
                        all_track_probs[track] = float(prob_value)
                    
                    # Create the top predictions list
                    top_predictions = []
                    
                    # Helper function to add prediction to the list if valid
                    def add_prediction(track_column, prob_column):
                        if not pd.isna(row[track_column]) and row[track_column] != '' and float(row[prob_column]) > 0:
                            try:
                                # Convert track to integer before adding to JSON
                                track_int = int(float(row[track_column]))
                                top_predictions.append({
                                    "track": track_int,
                                    "probability": float(row[prob_column])
                                })
                            except (ValueError, TypeError):
                                # Fallback to string if conversion fails
                                top_predictions.append({
                                    "track": row[track_column],
                                    "probability": float(row[prob_column])
                                })
                    
                    # Add all 10 predictions
                    add_prediction('Pred_Track_1', 'Prob_1')
                    add_prediction('Pred_Track_2', 'Prob_2')
                    add_prediction('Pred_Track_3', 'Prob_3')
                    add_prediction('Pred_Track_4', 'Prob_4')
                    add_prediction('Pred_Track_5', 'Prob_5')
                    add_prediction('Pred_Track_6', 'Prob_6')
                    add_prediction('Pred_Track_7', 'Prob_7')
                    add_prediction('Pred_Track_8', 'Prob_8')
                    add_prediction('Pred_Track_9', 'Prob_9')
                    add_prediction('Pred_Track_10', 'Prob_10')
                    
                    # Create prediction entry
                    # Clean destination before adding to JSON
                    destination = str(row['Destination'])
                    destination = destination.replace('&#9992', '').replace('-SEC', '').strip()
                    
                    prediction = {
                        "train_id": row['Train_ID'],
                        "line": row['Line'],
                        "destination": destination,
                        "departure_time": row['Departure'],
                        "status": row['Status'].strip() if not pd.isna(row['Status']) and str(row['Status']).strip() != "" else "On Time",
                        "is_predicted": pd.isna(row.get('Track', None)) or row.get('Track', '') == '',  # Only mark as predicted if no track is assigned
                        "predictions": top_predictions,
                        "all_track_probabilities": all_track_probs
                    }
                    
                    # Handle current_track - convert to integer if possible
                    if pd.isna(row.get('Track', None)) or row.get('Track', '') == '' or row.get('Track', '') == 'TBD':
                        prediction["current_track"] = None
                    else:
                        try:
                            # Convert track to integer before adding to JSON
                            prediction["current_track"] = int(float(row.get('Track')))
                        except (ValueError, TypeError):
                            # Fallback to original value if conversion fails
                            prediction["current_track"] = row.get('Track')
                    
                    # Add Trip_ID if it exists
                    if 'Trip_ID' in row and not pd.isna(row['Trip_ID']) and row['Trip_ID'] != '':
                        prediction["trip_id"] = row['Trip_ID']
                    
                    # Add prediction factors if they exist in the dataframe - using the JSON string version
                    if 'prediction_factors_json' in row:
                        try:
                            # Check if it's a valid JSON string
                            pf_str = str(row['prediction_factors_json'])
                            if pf_str != 'nan' and pf_str != '' and not pf_str.startswith('<NA>'):
                                # Parse the JSON string back to an object
                                prediction["prediction_factors"] = json.loads(pf_str)
                        except Exception as e:
                            logger.warning(f"Error processing prediction factors JSON: {e}")
                            
                    # Fallback: if we have the raw _prediction_factors object stored
                    elif '_prediction_factors' in row and not isinstance(row['_prediction_factors'], float):
                        try:
                            prediction["prediction_factors"] = row['_prediction_factors']
                        except Exception as e:
                            logger.warning(f"Error processing raw prediction factors: {e}")
                    
                    # We're no longer including counterfactual insights
                    
                    json_data["predictions"].append(prediction)
                
                # Using the NpEncoder class defined at the top of the file
                
                # Write to file
                with open(latest_json_path, 'w') as f:
                    json.dump(json_data, f, indent=2, cls=NpEncoder)
                
                logger.warning(f"Saved {len(latest_results_df)} predictions as JSON to {latest_json_path}")
                
                # Also save combined train records to all_trains.csv
                all_trains_path = os.path.join(output_dir, "model_artifacts", "all_trains.csv")
                all_json_path = os.path.join(output_dir, "model_artifacts", "all_trains.json")
                
                # If all_trains.csv already exists from previous data, append to it
                if os.path.exists(all_trains_path):
                    # Read existing train records
                    existing_trains = pd.read_csv(all_trains_path)
                    if 'Source' not in existing_trains.columns:
                        existing_trains['Source'] = 'Previous Data'
                        
                    # Append latest train records
                    combined_trains = pd.concat([existing_trains, latest_results_df], ignore_index=True)
                    combined_trains.to_csv(all_trains_path, index=False)
                    logger.warning(f"Appended {len(latest_results_df)} latest train records to {all_trains_path}")
                else:
                    # Just save latest train records
                    latest_results_df.to_csv(all_trains_path, index=False)
                    logger.warning(f"Created new all_trains.csv with {len(latest_results_df)} train records from latest data")
                
                # Get the updated all_trains data for creating JSON
                all_trains_df = combined_trains if 'combined_trains' in locals() else latest_results_df
                
                # Create the JSON structure
                all_json_data = {
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "model_version": "1.0",
                        "train_count": len(all_trains_df)
                    },
                    "trains": []
                }
                
                # Process each train record for JSON format
                for _, row in all_trains_df.iterrows():
                    # Get all track probability columns
                    track_prob_cols = [col for col in all_trains_df.columns if col.startswith('Prob_')]
                    
                    # Extract track probabilities
                    all_track_probs = {}
                    for col in track_prob_cols:
                        track = col.replace('Prob_', '')
                        # Handle NaN values - replace with 0
                        prob_value = row[col]
                        if pd.isna(prob_value):
                            prob_value = 0.0
                        all_track_probs[track] = float(prob_value)
                    
                    # Get top 3 predictions based on probability values
                    probs_dict = {track: prob for track, prob in all_track_probs.items()}
                    sorted_probs = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
                    
                    # Create the top tracks list
                    top_tracks = []
                    for i, (track, prob) in enumerate(sorted_probs[:3]):
                        if prob > 0:
                            # Convert track to integer before adding to JSON
                            try:
                                # Remove decimal part if it exists
                                track_int = int(float(track))
                                top_tracks.append({
                                    "track": track_int,
                                    "probability": float(prob)
                                })
                            except (ValueError, TypeError):
                                # Fallback to string if conversion fails
                                top_tracks.append({
                                    "track": track,
                                    "probability": float(prob)
                                })
                    
                    # Extract train information
                    train_id = str(row.get('Train_ID', '')) if not pd.isna(row.get('Train_ID', None)) else ''
                    
                    # Check if Trip_ID exists, if not, we'll create one
                    has_trip_id = 'Trip_ID' in row and not pd.isna(row.get('Trip_ID', None))
                    
                    # Extract line from Train_ID or determine based on destination
                    line = str(row.get('Line', '')) if not pd.isna(row.get('Line', None)) else ''
                    
                    # If line is empty, derive it from other data
                    if line == '':
                        # Try to extract from Trip_ID pattern: 2025-05-01_6613_08:02 AM
                        if not pd.isna(row.get('Trip_ID', None)):
                            trip_id = str(row.get('Trip_ID', ''))
                            if '_' in trip_id:
                                # Common line prefixes based on Train_ID ranges
                                if train_id.startswith('A') or train_id.startswith('P'):
                                    line = 'Amtrak'
                                elif train_id.isdigit():
                                    train_num = int(train_id)
                                    if 6000 <= train_num <= 7000:
                                        line = 'Morristown Line'
                                    elif 5000 <= train_num <= 6000:
                                        line = 'Raritan Valley'
                                    elif 3000 <= train_num <= 4000:
                                        line = 'Northeast Corridor'
                                    elif 2000 <= train_num <= 3000:
                                        line = 'North Jersey Coast'
                                    else:
                                        # Default to identifying by destination
                                        if 'Dover' in str(row.get('Destination', '')):
                                            line = 'Morristown Line'
                                        elif 'Trenton' in str(row.get('Destination', '')):
                                            line = 'Northeast Corridor'
                                        elif 'Long Branch' in str(row.get('Destination', '')):
                                            line = 'North Jersey Coast'
                                        elif 'Raritan' in str(row.get('Destination', '')):
                                            line = 'Raritan Valley'
                                            
                    destination = str(row.get('Destination', '')) if not pd.isna(row.get('Destination', None)) else ''
                    
                    # Get basic departure information
                    departure = str(row.get('Departure', '')) if not pd.isna(row.get('Departure', None)) else ''
                    
                    # Generate Trip_ID if it doesn't exist
                    trip_id = ''
                    if has_trip_id:
                        trip_id = str(row.get('Trip_ID', ''))
                    
                    # Handle departure time - try different column names that might exist
                    if departure == '' and not pd.isna(row.get('Departure_Time', None)):
                        departure = str(row.get('Departure_Time', ''))
                    
                    # Try to extract departure time from Trip_ID if it's still empty
                    if departure == '' and not pd.isna(row.get('Trip_ID', None)):
                        trip_id = str(row.get('Trip_ID', ''))
                        if '_' in trip_id:
                            parts = trip_id.split('_')
                            if len(parts) >= 3:
                                # Extract time part and date from pattern like: 2025-05-01_6613_08:02 AM
                                date_part = parts[0]
                                departure_time = parts[-1].strip()
                                
                                # If we have a valid date part, create a full datetime
                                if date_part and len(date_part) >= 10:  # Basic check for YYYY-MM-DD format
                                    departure = f"{date_part} {departure_time}"
                                else:
                                    departure = departure_time
                    
                    # Check if we need to add date information to the departure time
                    if departure and len(departure) <= 8:  # Simple check for time only format (HH:MM AM/PM)
                        # First try to extract date from Trip_ID
                        date_part = None
                        if 'Trip_ID' in row and not pd.isna(row.get('Trip_ID', None)):
                            trip_id = str(row.get('Trip_ID', ''))
                            if '_' in trip_id:
                                parts = trip_id.split('_')
                                if len(parts) >= 1 and len(parts[0]) >= 10:  # Date should be in first part
                                    try:
                                        # Validate it's a proper date
                                        pd.to_datetime(parts[0])
                                        date_part = parts[0]
                                    except:
                                        date_part = None
                        
                        # If Trip_ID doesn't contain a date, try using Timestamp column
                        if date_part is None and not pd.isna(row.get('Timestamp', None)):
                            try:
                                timestamp = pd.to_datetime(row.get('Timestamp'))
                                date_part = timestamp.strftime('%Y-%m-%d')
                            except:
                                date_part = None
                        
                        # Last resort: use current date but log a warning
                        if date_part is None:
                            logger.warning("WARNING: Using current date for departure time - this is likely incorrect")
                            date_part = datetime.now().strftime('%Y-%m-%d')
                        
                        # Add the date part to the departure time
                        departure = f"{date_part} {departure}"
                    
                    status = str(row.get('Status', '')) if not pd.isna(row.get('Status', None)) and str(row.get('Status', '')).strip() != '' else 'On Time'
                    
                    # If we don't have a Trip_ID yet, generate one
                    if not trip_id:
                        try:
                            # Try to get date part from departure 
                            date_part = ''
                            if ' ' in departure:
                                date_parts = departure.split(' ')[0].split('-')
                                if len(date_parts) == 3:
                                    # Looks like we have YYYY-MM-DD format
                                    date_part = departure.split(' ')[0]
                            
                            # If we couldn't extract date, use today's date
                            if not date_part:
                                date_part = datetime.now().strftime('%Y-%m-%d')
                            
                            # Clean Train_ID
                            clean_train_id = str(train_id).strip()
                            
                            # Create Trip_ID
                            if ' ' in departure:
                                time_part = departure.split(' ')[-2] if len(departure.split(' ')) > 2 else departure.split(' ')[-1]
                            else:
                                time_part = departure
                            
                            trip_id = f"{date_part}_{clean_train_id}_{time_part}"
                            
                            # Cleanup any double spaces or problematic characters
                            trip_id = trip_id.replace('  ', ' ').strip()
                        except Exception as e:
                            # If generation fails, create a basic Trip_ID
                            trip_id = f"{datetime.now().strftime('%Y-%m-%d')}_{train_id}"
                    
                    # Create JSON entry for train record
                    train_record = {
                        "train_id": train_id,
                        "trip_id": trip_id,
                        "line": line,
                        "destination": destination,
                        "departure_time": departure,
                        "status": status.strip() if status and status.strip() != "" else "On Time",
                        "track": None if pd.isna(row.get('True_Track', None)) or row.get('True_Track', '') == '' else row.get('True_Track'),
                        "model_tracks": top_tracks,
                        "all_track_probabilities": all_track_probs
                    }
                    
                    # Add prediction factors if they exist in the dataframe - using the JSON string version
                    if 'prediction_factors_json' in row:
                        try:
                            # Check if it's a valid JSON string
                            pf_str = str(row['prediction_factors_json'])
                            if pf_str != 'nan' and pf_str != '' and not pf_str.startswith('<NA>'):
                                # Parse the JSON string back to an object
                                train_record["prediction_factors"] = json.loads(pf_str)
                        except Exception as e:
                            logger.warning(f"Error processing prediction factors JSON: {e}")
                            
                    # Fallback: if we have the raw _prediction_factors object stored
                    elif '_prediction_factors' in row and not isinstance(row['_prediction_factors'], float):
                        try:
                            train_record["prediction_factors"] = row['_prediction_factors']
                        except Exception as e:
                            logger.warning(f"Error processing raw prediction factors: {e}")
                    
                    # We're no longer including counterfactual insights
                    
                    all_json_data["trains"].append(train_record)
                
                # Write the JSON file
                with open(all_json_path, 'w') as f:
                    json.dump(all_json_data, f, indent=2, cls=NpEncoder)
                
                logger.warning(f"Saved {len(all_trains_df)} historical train records as JSON to {all_json_path}")
            else:
                logger.warning("No predictions generated for latest data")
        else:
            logger.warning("No unassigned trains found in the latest data")
    else:
        logger.warning(f"Latest data file not found: {latest_data_path}")
    
    # Save best model predictions for test set
    test_predictions_df = pd.DataFrame({
        'True_Track_Index': all_targets,
        'Predicted_Track_Index': all_predictions
    })
    
    # Add metadata if available - preserve ALL original metadata
    # Use holdout_indices which are the actual indices used in predictions
    if 'holdout_indices' in locals() and df is not None and len(holdout_indices) == len(all_predictions):
        # Use the actual indices used for predictions
        test_indices_to_use = holdout_indices 
        logger.warning(f"Using {len(holdout_indices)} actual holdout indices for metadata")
        
        # Get the test samples from the original dataframe with ALL columns
        test_df = df.iloc[test_indices_to_use].reset_index(drop=True)
        
        # Add all fields from original data to test predictions
        for field in test_df.columns:
            if field != 'Track' and field not in test_predictions_df.columns:  # Avoid overwriting existing columns
                try:
                    test_predictions_df[field] = test_df[field].values
                    logger.info(f"Added original field {field} to test predictions")
                except Exception as e:
                    logger.warning(f"Error adding {field} to test predictions: {e}")
        
        # Set flag indicating we have original metadata
        has_original_metadata = True
        logger.warning("Successfully preserved original metadata for test predictions")
        
    elif test_indices is not None and df is not None and len(test_indices) == len(all_predictions):
        logger.warning("Using full test indices for metadata")
        
        # Get the test samples from the original dataframe with ALL columns
        test_df = df.iloc[test_indices].reset_index(drop=True)
        
        # Add all fields from original data to test predictions
        for field in test_df.columns:
            if field != 'Track' and field not in test_predictions_df.columns:  # Avoid overwriting existing columns
                try:
                    test_predictions_df[field] = test_df[field].values
                    logger.info(f"Added original field {field} to test predictions")
                except Exception as e:
                    logger.warning(f"Error adding {field} to test predictions: {e}")
        
        # Set flag indicating we have original metadata
        has_original_metadata = True
        logger.warning("Successfully preserved original metadata for test predictions")

    # Add actual track labels instead of just indices
    if tracks is not None:
        test_predictions_df['True_Track'] = test_predictions_df['True_Track_Index'].apply(lambda idx: tracks[idx] if idx < len(tracks) else 'Unknown')
        test_predictions_df['Predicted_Track'] = test_predictions_df['Predicted_Track_Index'].apply(lambda idx: tracks[idx] if idx < len(tracks) else 'Unknown')
    else:
        # If tracks is not provided, just use the indices as strings
        test_predictions_df['True_Track'] = test_predictions_df['True_Track_Index'].astype(str)
        test_predictions_df['Predicted_Track'] = test_predictions_df['Predicted_Track_Index'].astype(str)
    
    # Add a 'Correct' column indicating whether the prediction was correct
    test_predictions_df['Correct'] = (test_predictions_df['True_Track'] == test_predictions_df['Predicted_Track']).astype(int)
    logger.warning(f"Added 'Correct' column to predictions: {test_predictions_df['Correct'].mean():.4f} accuracy")
    
    # Add prediction probabilities
    if tracks is not None:
        for i, track in enumerate(tracks):
            if i < all_probs.shape[1]:
                test_predictions_df[f'Prob_{track}'] = all_probs[:, i]
    else:
        # Use numerical indices if tracks not provided
        for i in range(all_probs.shape[1]):
            test_predictions_df[f'Prob_Track_{i}'] = all_probs[:, i]
    
    # Reorder columns to put important metadata first
    ordered_columns = []
    
    # Start with the most important metadata
    for field in ['Timestamp', 'Train_ID', 'Trip_ID', 'Line', 'Destination']:
        if field in test_predictions_df.columns:
            ordered_columns.append(field)
    
    # Add track info next
    track_cols = ['True_Track', 'Predicted_Track', 'True_Track_Index', 'Predicted_Track_Index']
    for col in track_cols:
        if col in test_predictions_df.columns:
            ordered_columns.append(col)
    
    # Add all remaining columns (probabilities, etc.)
    for col in test_predictions_df.columns:
        if col not in ordered_columns:
            ordered_columns.append(col)
    
    # Reorder the dataframe
    test_predictions_df = test_predictions_df[ordered_columns]
    
    # Save predictions to CSV
    predictions_path = os.path.join(output_dir, "model_artifacts", "test_predictions.csv")
    test_predictions_df.to_csv(predictions_path, index=False)
    logger.warning(f"Saved best model predictions on test set to {predictions_path}")
    
    # Also save test predictions as JSON
    test_json_path = os.path.join(output_dir, "model_artifacts", "test_predictions.json")
    
    # Only generate synthetic data if real data is missing
    # First check if we have original metadata
    has_original_metadata = ('Train_ID' in test_predictions_df.columns and 
                           'Line' in test_predictions_df.columns and
                           'Destination' in test_predictions_df.columns)
    
    if has_original_metadata:
        logger.info("Using original metadata for test predictions - no need for synthetic data")
    else:
        logger.warning("Original metadata missing - generating synthetic data for test predictions")
        
        # Generate synthetic Train_IDs if needed
        if 'Train_ID' not in test_predictions_df.columns:
            # Create synthetic Train_IDs based on index
            # Pattern: Even indices get number 3000-7000, odd indices get A/P + number
            logger.warning("Generating synthetic Train_IDs for test predictions")
            train_ids = []
            for i in range(len(test_predictions_df)):
                if i % 2 == 0:
                    train_id = str(3000 + (i % 4000))  # Range from 3000-7000
                else:
                    prefix = 'A' if i % 4 == 1 else 'P'
                    train_id = f"{prefix}{100 + (i % 900)}"  # A100-A999 or P100-P999
                train_ids.append(train_id)
            test_predictions_df['Train_ID'] = train_ids
            
        # Generate synthetic Trip_IDs if needed
        if 'Trip_ID' not in test_predictions_df.columns:
            # Create Trip_IDs with format: 2025-MM-DD_TrainID_HH:MM AM/PM
            logger.warning("Generating synthetic Trip_IDs for test predictions")
            import random
            
            # Generate random timestamps across a month
            base_date = datetime(2025, 5, 1)
            trip_ids = []
            
            for i, train_id in enumerate(test_predictions_df['Train_ID']):
                # Random date within a month
                random_days = random.randint(0, 29)
                random_date = base_date + timedelta(days=random_days)
                date_str = random_date.strftime("%Y-%m-%d")
                
                # Random time
                hour = random.randint(5, 22)  # 5 AM to 10 PM
                minute = random.choice([0, 15, 30, 45])
                am_pm = "AM" if hour < 12 else "PM"
                if hour > 12:
                    hour -= 12
                if hour == 0:
                    hour = 12
                time_str = f"{hour:02d}:{minute:02d} {am_pm}"
                
                # Combine into Trip_ID
                trip_id = f"{date_str}_{train_id}_{time_str}"
                trip_ids.append(trip_id)
            
            test_predictions_df['Trip_ID'] = trip_ids
        
    # Generate destinations based on track patterns if needed, only if we don't have original metadata
    if has_original_metadata:
        # We already have original metadata
        pass
    elif 'Destination' not in test_predictions_df.columns:
        # Common destinations by track pattern
        logger.warning("Generating synthetic destinations for test predictions")
        destination_map = {
            # NJ Transit
            '1': 'Trenton',
            '2': 'New York',
            '3': 'Long Branch',
            '4': 'Dover',
            '5': 'Newark',
            '6': 'Hoboken',
            '7': 'Montclair',
            '8': 'Bay Head',
            '9': 'Gladstone',
            '10': 'Secaucus',
            # Amtrak
            '11': 'Washington DC',
            '12': 'Boston',
            '13': 'Philadelphia',
            '14': 'Albany',
            '15': 'Richmond',
            '16': 'Pittsburgh',
            '18': 'Chicago'
        }
        
        destinations = []
        for _, row in test_predictions_df.iterrows():
            # Use the true track to determine destination
            track = str(row['True_Track']).replace('.0', '')
            train_id = str(row.get('Train_ID', ''))
            
            # Add Amtrak symbols for Amtrak trains
            if train_id.startswith('A') or train_id.startswith('P'):
                if track in destination_map:
                    destination = f"{destination_map[track]} &#9992"
                else:
                    destination = "Washington DC &#9992"
            else:
                if track in destination_map:
                    destination = destination_map[track]
                else:
                    destination = "New York"
            
            destinations.append(destination)
            
        test_predictions_df['Destination'] = destinations
        
    # Generate Line data if needed, only if we don't have original metadata
    if has_original_metadata:
        # We already have original metadata
        pass
    elif 'Line' not in test_predictions_df.columns:
        logger.warning("Generating synthetic line data for test predictions")
        lines = []
        for _, row in test_predictions_df.iterrows():
            train_id = str(row.get('Train_ID', ''))
            destination = str(row.get('Destination', ''))
            
            # Determine line based on train_id and destination
            if train_id.startswith('A') or train_id.startswith('P'):
                line = 'Amtrak'
            else:
                # Based on train number range
                train_num = int(train_id) if train_id.isdigit() else 0
                if 6000 <= train_num <= 7000:
                    line = 'Morristown Line'
                elif 5000 <= train_num <= 6000:
                    line = 'Raritan Valley'
                elif 3000 <= train_num <= 4000:
                    line = 'Northeast Corridor'
                elif 2000 <= train_num <= 3000:
                    line = 'North Jersey Coast'
                else:
                    # Based on destination
                    if 'Dover' in destination:
                        line = 'Morristown Line'
                    elif 'Trenton' in destination:
                        line = 'Northeast Corridor'
                    elif 'Long Branch' in destination or 'Bay Head' in destination:
                        line = 'North Jersey Coast'
                    elif 'Raritan' in destination:
                        line = 'Raritan Valley'
                    elif 'Gladstone' in destination:
                        line = 'Gladstone Branch'
                    elif 'Montclair' in destination:
                        line = 'Montclair-Boonton'
                    else:
                        line = 'Northeast Corridor'
            
            lines.append(line)
            
        test_predictions_df['Line'] = lines
        
    # Generate departure times if needed, only if we don't have original metadata
    if has_original_metadata:
        # We already have original metadata with departure times
        pass
    elif 'Departure_Time' not in test_predictions_df.columns and 'Trip_ID' in test_predictions_df.columns:
        logger.warning("Extracting departure times from Trip_IDs")
        departure_times = []
        
        for trip_id in test_predictions_df['Trip_ID']:
            if '_' in trip_id:
                parts = trip_id.split('_')
                if len(parts) >= 3:
                    # Extract time part from pattern like: 2025-05-01_6613_08:02 AM
                    departure = parts[-1].strip()
                else:
                    departure = ''
            else:
                departure = ''
            
            departure_times.append(departure)
            
        test_predictions_df['Departure_Time'] = departure_times
    
    # Create the JSON structure
    test_json_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model_version": "1.0",
            "prediction_count": len(test_predictions_df)
        },
        "predictions": []
    }
    
    # Process each prediction for JSON format
    for _, row in test_predictions_df.iterrows():
        # Get all track probability columns
        track_prob_cols = [col for col in test_predictions_df.columns if col.startswith('Prob_')]
        
        # Extract track probabilities
        all_track_probs = {}
        for col in track_prob_cols:
            track = col.replace('Prob_', '')
            # Handle NaN values - replace with 0
            prob_value = row[col]
            if pd.isna(prob_value):
                prob_value = 0.0
            all_track_probs[track] = float(prob_value)
        
        # Get top 10 predictions based on probability values
        probs_dict = {track: prob for track, prob in all_track_probs.items()}
        sorted_probs = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
        
        # Create the top predictions list
        top_predictions = []
        for i, (track, prob) in enumerate(sorted_probs[:10]): # Increased to 10 predictions
            if prob > 0:
                try:
                    # Convert track to integer before adding to JSON
                    track_int = int(float(track))
                    top_predictions.append({
                        "track": track_int,
                        "probability": float(prob)
                    })
                except (ValueError, TypeError):
                    # Fallback to string if conversion fails
                    top_predictions.append({
                        "track": track,
                        "probability": float(prob)
                    })
        
        # Extract train information
        train_id = str(row.get('Train_ID', '')) if not pd.isna(row.get('Train_ID', None)) else ''
        
        # Extract line from Train_ID or determine based on destination
        line = str(row.get('Line', '')) if not pd.isna(row.get('Line', None)) else ''
        
        # If line is empty, derive it from other data
        if line == '':
            print("WARNING: INFERRING LINE")
            # Try to extract from Trip_ID pattern: 2025-05-01_6613_08:02 AM
            if not pd.isna(row.get('Trip_ID', None)):
                trip_id = str(row.get('Trip_ID', ''))
                if '_' in trip_id:
                    # Common line prefixes based on Train_ID ranges
                    if train_id.startswith('A') or train_id.startswith('P'):
                        line = 'Amtrak'
                    elif train_id.isdigit():
                        train_num = int(train_id)
                        if 6000 <= train_num <= 7000:
                            line = 'Morristown Line'
                        elif 5000 <= train_num <= 6000:
                            line = 'Raritan Valley'
                        elif 3000 <= train_num <= 4000:
                            line = 'Northeast Corridor'
                        elif 2000 <= train_num <= 3000:
                            line = 'North Jersey Coast'
                        else:
                            # Default to identifying by destination
                            if 'Dover' in str(row.get('Destination', '')):
                                line = 'Morristown Line'
                            elif 'Trenton' in str(row.get('Destination', '')):
                                line = 'Northeast Corridor'
                            elif 'Long Branch' in str(row.get('Destination', '')):
                                line = 'North Jersey Coast'
                            elif 'Raritan' in str(row.get('Destination', '')):
                                line = 'Raritan Valley'
        
        destination = str(row.get('Destination', '')) if not pd.isna(row.get('Destination', None)) else ''
        departure = str(row.get('Departure', '')) if not pd.isna(row.get('Departure', None)) else ''
        status = str(row.get('Status', '')) if not pd.isna(row.get('Status', None)) else ''
        
        # First try to extract date from Trip_ID for both timestamp and date_part
        date_from_trip = None
        date_part = None
        
        if not pd.isna(row.get('Trip_ID', None)):
            trip_id = str(row.get('Trip_ID', ''))
            if '_' in trip_id:
                parts = trip_id.split('_')
                if len(parts) >= 1 and len(parts[0]) >= 10:  # Basic check for date format
                    try:
                        # Validate it's a proper date
                        date_from_trip = pd.to_datetime(parts[0])
                        date_part = parts[0]
                    except:
                        date_from_trip = None
                        date_part = None
        
        # Get timestamp for date information - prioritize original data timestamps
        # First check if we have a Timestamp in the row
        if has_original_metadata and not pd.isna(row.get('Timestamp', None)):
            # Use the original timestamp from the data
            timestamp = pd.to_datetime(row.get('Timestamp'))
            logger.warning("Using original timestamp from test data")
        elif date_from_trip is not None:
            # Use the date extracted from Trip_ID
            timestamp = date_from_trip
        else:
            # Last resort: fall back to today's date, but log a warning
            logger.warning("WARNING: FALLING BACK TO CURRENT TIME WHICH IS WRONG")
            timestamp = pd.to_datetime(row.get('Timestamp', datetime.now()))
        
        # Handle departure time - try different column names that might exist
        if departure == '' and not pd.isna(row.get('Departure_Time', None)):
            departure = str(row.get('Departure_Time', ''))
            
        # Try to extract departure time from Trip_ID if it's still empty
        time_part = None
        if departure == '' and not pd.isna(row.get('Trip_ID', None)):
            trip_id = str(row.get('Trip_ID', ''))
            if '_' in trip_id:
                parts = trip_id.split('_')
                if len(parts) >= 3:
                    # Extract time part from pattern like: 2025-05-01_6613_08:02 AM
                    time_part = parts[-1].strip()
                    departure = time_part
                    
        # Add date component to departure time if it's just a time
        if departure and len(departure) <= 8:  # Simple check for time-only format (HH:MM AM/PM)
            # Use date from trip_id (prioritized) or timestamp as fallback
            date_str = date_part if date_part else timestamp.strftime('%Y-%m-%d')
            departure = f"{date_str} {departure}"
        
        # Create JSON entry matching the latest_predictions.json format
        # Clean destination before adding to JSON
        destination = str(destination)
        destination = destination.replace('&#9992', '').replace('-SEC', '').strip()
        
        prediction = {
            "train_id": train_id,
            "line": line,
            "destination": destination,
            "departure_time": departure,
            "status": status.strip() if status and status.strip() != "" else "On Time",
            "is_predicted": pd.isna(row.get('True_Track', None)) or row.get('True_Track', '') == '',
            "predictions": top_predictions,
            "all_track_probabilities": all_track_probs
        }
        
        # Handle current_track - convert to integer if possible
        if pd.isna(row.get('True_Track', None)) or row.get('True_Track', '') == '':
            print("UNABLE TO GET CURRENT TRACK")
            prediction["current_track"] = None
        else:
            try:
                # Convert track to integer before adding to JSON
                prediction["current_track"] = int(float(row.get('True_Track')))
            except (ValueError, TypeError):
                # Fallback to original value if conversion fails
                prediction["current_track"] = row.get('True_Track')
            print("USING %s FROM %s" % (prediction["current_track"], row.get('True_Track')))
        test_json_data["predictions"].append(prediction)
    
    # Write the JSON file
    with open(test_json_path, 'w') as f:
        json.dump(test_json_data, f, indent=2, cls=NpEncoder)
    
    logger.warning(f"Saved {len(test_predictions_df)} test predictions as JSON to {test_json_path}")
    
    # Create calibration plots for model confidence evaluation
    create_calibration_plots(test_predictions_df, output_dir="final_output")
    
    logger.warning(f"Final model metrics:")
    logger.warning(f"  Accuracy: {final_accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1 Score: {f1:.4f}")
    
    # Store essential history for visualization
    history = {
        'train_losses': train_losses,
        'val_losses': val_losses,
        'train_accuracies': train_accuracies,
        'val_accuracies': val_accuracies,
        'final_accuracy': final_accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'confusion_matrix': cm,
        'class_report': class_report, # Keep for class metrics plot
        'all_targets': all_targets,
        'all_predictions': all_predictions,
    }
    
    # Add line information for per-line visualizations if available
    if df is not None and test_indices is not None:
        logger.warning(f"Preparing line data: DataFrame has columns: {df.columns}")
        
        try:
            # First try to use holdout_indices if available
            if 'holdout_indices' in locals() and len(holdout_indices) == len(all_predictions):
                # Make sure indices are valid
                if max(holdout_indices) < len(df):
                    test_df = df.iloc[holdout_indices].copy() # Use .copy() to avoid SettingWithCopyWarning
                    logger.warning(f"Using holdout indices: {len(holdout_indices)}, All predictions: {len(all_predictions)}")
                else:
                    logger.error(f"Max holdout index ({max(holdout_indices)}) is out of bounds for DataFrame length ({len(df)}). Cannot use holdout indices.")
                    test_df = pd.DataFrame() # Create empty df to avoid further errors
            # Fallback to test_indices
            elif max(test_indices) < len(df):
                 test_df = df.iloc[test_indices].copy() # Use .copy() to avoid SettingWithCopyWarning
                 logger.warning(f"Test indices length: {len(test_indices)}, All predictions: {len(all_predictions)}")
            else:
                 logger.error(f"Max test index ({max(test_indices)}) is out of bounds for DataFrame length ({len(df)}). Cannot create test_df.")
                 test_df = pd.DataFrame() # Create empty df to avoid further errors


            if not test_df.empty and len(test_df) == len(all_predictions):
                # Add line information if available
                if 'Line' in test_df.columns:
                    line_data = test_df['Line'].values
                    history['line_data'] = line_data
                    lines_found = set(line_data)
                    logger.warning(f"Added line information from 'Line' column for {len(line_data)} test samples")
                    logger.warning(f"Lines found in test data: {lines_found}")
                else:
                    # Try to reconstruct line from one-hot encoded columns
                    line_cols = [col for col in test_df.columns if col.startswith('Line_')]
                    if line_cols:
                        logger.warning(f"Found {len(line_cols)} one-hot encoded line columns. Reconstructing line data.")
                        line_data_reconstructed = []
                        # Efficiently find the active line column for each row
                        line_matrix = test_df[line_cols].values
                        # Get the index of the '1' in each row (argmax returns the first max index)
                        # Add check to handle rows with no line set (all zeros)
                        active_line_indices = np.argmax(line_matrix, axis=1)
                        
                        # Create a mask for rows where at least one line is active
                        row_has_line = line_matrix.sum(axis=1) > 0

                        for i in range(len(test_df)):
                            if row_has_line[i]:
                                line_col_index = active_line_indices[i]
                                line_name = line_cols[line_col_index].replace('Line_', '')
                                line_data_reconstructed.append(line_name)
                            else:
                                # Handle rows with no line indicator
                                line_data_reconstructed.append('Unknown') # Or None, or handle as needed

                        history['line_data'] = np.array(line_data_reconstructed)
                        lines_found = set(history['line_data'])
                        logger.warning(f"Reconstructed line information for {len(history['line_data'])} test samples.")
                        logger.warning(f"Lines found in reconstructed test data: {lines_found}")
                    else:
                        logger.warning("No 'Line' column or 'Line_*' columns found in DataFrame")
                        # Create a fallback with a single line category
                        fallback_line_data = np.array(['All'] * len(all_predictions))
                        history['line_data'] = fallback_line_data
                        logger.warning(f"Using fallback line data with {len(fallback_line_data)} samples")

                # Add hour information if available
                if 'Hour' in test_df.columns:
                    hour_data = test_df['Hour'].values
                    history['hour_data'] = hour_data
                    logger.warning(f"Added hour information for {len(hour_data)} test samples")
                elif 'Timestamp' in test_df.columns:
                    # Extract hour from timestamp
                    hour_data = test_df['Timestamp'].dt.hour.values
                    history['hour_data'] = hour_data
                    logger.warning(f"Added hour information from timestamps for {len(hour_data)} test samples")
                else:
                    logger.warning("No hour or timestamp information found, can't add time distribution data")

                # Add day of week information if available
                if 'Day_Of_Week' in test_df.columns:
                    dow_data = test_df['Day_Of_Week'].values
                    history['day_of_week_data'] = dow_data
                    logger.warning(f"Added day of week information for {len(dow_data)} test samples")
                elif 'Timestamp' in test_df.columns:
                    # Extract day of week from timestamp
                    dow_data = test_df['Timestamp'].dt.dayofweek.values
                    history['day_of_week_data'] = dow_data
                    logger.warning(f"Added day of week information from timestamps for {len(dow_data)} test samples")
                else:
                     logger.warning("No day of week or timestamp information found, can't add day distribution data")

            else:
                # Mismatch or empty test_df case
                if test_df.empty:
                     logger.warning("Could not create test_df based on indices.")
                else: # Length mismatch
                    logger.warning(f"Test DataFrame length ({len(test_df)}) doesn't match predictions ({len(all_predictions)})")
                
                logger.warning("Using fallback approach for metadata")
                # Create fallback data if line association failed
                fallback_line_data = np.array(['All'] * len(all_predictions))
                history['line_data'] = fallback_line_data
                logger.warning(f"Using fallback line data with {len(fallback_line_data)} samples due to mismatch or index error.")
                # Optionally add fallback for hour/dow if needed, but they might be less critical
        except Exception as e:
            logger.error(f"Error preparing metadata (line/hour/dow): {e}", exc_info=True)
            # Create fallback data in case of any error during processing
            fallback_line_data = np.array(['All'] * len(all_predictions))
            history['line_data'] = fallback_line_data
            logger.warning(f"Using fallback metadata due to error during preparation")
    
    return model, history

def create_calibration_plots(test_predictions_df, output_dir="output"):
    """Create calibration plots (reliability curves) to evaluate prediction confidence.
    
    This implementation includes comprehensive calibration that accounts for
    both positive predictions (track will be used) and negative predictions
    (track will NOT be used) to provide a more complete view of model calibration.
    
    Args:
        test_predictions_df: DataFrame containing test predictions with confidence scores
        output_dir: Directory to save visualizations
    """
    visualizations_dir = os.path.join(output_dir, "visualizations")
    os.makedirs(visualizations_dir, exist_ok=True)
    
    # Create per-line visualizations directory
    per_line_dir = os.path.join(visualizations_dir, "per_line")
    os.makedirs(per_line_dir, exist_ok=True)
    
    logger.warning("Creating comprehensive calibration plots to evaluate prediction confidence...")
    logger.warning(f"Output directory: {visualizations_dir}")
    
    # Verify we have the necessary data
    logger.warning(f"Available columns in test_predictions_df: {test_predictions_df.columns.tolist()}")
    logger.warning(f"Number of test predictions: {len(test_predictions_df)}")
    
    # Check if we have the required confidence scores and correctness information
    if 'Correct' not in test_predictions_df.columns:
        logger.warning("Cannot create calibration plots: 'Correct' column missing")
        return
    
    # Function to calculate ECE (Expected Calibration Error)
    def calculate_ece(confidences, correctness, n_bins=10):
        """Calculate Expected Calibration Error."""
        bin_indices = np.digitize(confidences, np.linspace(0, 1, n_bins+1))
        ece = 0
        bin_counts = np.zeros(n_bins)
        bin_confidences = np.zeros(n_bins)
        bin_accuracies = np.zeros(n_bins)
        
        for bin_idx in range(1, n_bins+1):
            bin_mask = bin_indices == bin_idx
            if np.sum(bin_mask) > 0:
                bin_counts[bin_idx-1] = np.sum(bin_mask)
                bin_confidences[bin_idx-1] = np.mean(confidences[bin_mask])
                bin_accuracies[bin_idx-1] = np.mean(correctness[bin_mask])
                ece += (np.sum(bin_mask) / len(confidences)) * np.abs(bin_confidences[bin_idx-1] - bin_accuracies[bin_idx-1])
        
        return ece, bin_confidences, bin_accuracies, bin_counts
    
    # Function to create a calibration plot
    def plot_calibration(confidences, correctness, title, output_path, n_bins=10):
        """Create and save a calibration/reliability plot."""
        plt.figure(figsize=(10, 8))
        
        # Calculate ECE and bin statistics
        ece, bin_confidences, bin_accuracies, bin_counts = calculate_ece(confidences, correctness, n_bins)
        
        # Main plot area for the calibration curve
        ax1 = plt.subplot2grid((3, 1), (0, 0), rowspan=2)
        
        # Plot the diagonal reference line (perfect calibration)
        ax1.plot([0, 1], [0, 1], 'r--', label='Perfect Calibration')
        
        # Plot the calibration curve
        valid_bins = bin_counts > 0
        if np.sum(valid_bins) > 0:
            ax1.plot(bin_confidences[valid_bins], bin_accuracies[valid_bins], 'b-o', label='Model Calibration')
            
            # Fill the area between curves to highlight error
            ax1.fill_between(bin_confidences[valid_bins], 
                            bin_confidences[valid_bins], 
                            bin_accuracies[valid_bins], 
                            alpha=0.2, color='blue')
        
        # Configure the plot
        ax1.set_xlabel('Confidence (Predicted Probability)')
        ax1.set_ylabel('Accuracy (Fraction of Positives)')
        ax1.set_title(f'{title}\nExpected Calibration Error (ECE): {ece:.4f}')
        ax1.set_xlim([0, 1])
        ax1.set_ylim([0, 1])
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.legend(loc='lower right')
        
        # Histogram showing distribution of confidence scores
        ax2 = plt.subplot2grid((3, 1), (2, 0))
        ax2.hist(confidences, bins=n_bins, range=(0, 1), edgecolor='black', alpha=0.6)
        ax2.set_xlabel('Confidence')
        ax2.set_ylabel('Count')
        ax2.set_title('Confidence Distribution')
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
        logger.warning(f"Saved calibration plot to {output_path}")
        
        return ece
    
    # Function to create comprehensive calibration data including both positive and negative predictions
    def create_extended_calibration_data(df, track_list=None):
        """Create extended calibration data including both positive and negative predictions."""
        # Get all unique track values if not provided
        if track_list is None:
            unique_tracks = set()
            # Extract all tracks from True_Track and Predicted_Track columns
            unique_tracks.update(df['True_Track'].unique())
            unique_tracks.update(df['Predicted_Track'].unique())
            
            # Also check probability columns to find all possible tracks
            for col in df.columns:
                if col.startswith('Prob_'):
                    track_name = col[5:]  # Remove 'Prob_' prefix
                    unique_tracks.add(track_name)
            
            # Convert to sorted list for consistent processing
            track_list = sorted(list(unique_tracks))
        
        # Data for extended calibration (including predictions against other tracks)
        extended_data = []
        
        # For each sample and each track, create data points for both positive and negative predictions
        for idx, row in df.iterrows():
            true_track = row['True_Track']
            line = row.get('Line', 'Unknown')
            
            for track_name in track_list:
                # Skip tracks that don't have probability data
                prob_col = f'Prob_{track_name}'
                if prob_col not in row:
                    continue
                    
                # Probability that this track will be used
                pos_confidence = row[prob_col]
                # Probability that this track will NOT be used
                neg_confidence = 1.0 - pos_confidence
                
                # Correctness of positive prediction (track will be used)
                pos_correct = 1 if track_name == true_track else 0
                # Correctness of negative prediction (track will NOT be used)
                neg_correct = 1 if track_name != true_track else 0
                
                # Add to extended data
                extended_data.append({
                    'Sample': idx,
                    'Track': track_name,
                    'True_Track': true_track,
                    'Prediction_Type': 'Positive',
                    'Confidence': pos_confidence,
                    'Correct': pos_correct,
                    'Line': line
                })
                
                extended_data.append({
                    'Sample': idx,
                    'Track': track_name,
                    'True_Track': true_track,
                    'Prediction_Type': 'Negative',
                    'Confidence': neg_confidence,
                    'Correct': neg_correct,
                    'Line': line
                })
        
        # Convert to DataFrame
        return pd.DataFrame(extended_data)
    
    # Get all unique track values from test_predictions_df
    unique_tracks = set()
    
    # Extract all tracks from both True_Track and Predicted_Track columns
    unique_tracks.update(test_predictions_df['True_Track'].unique())
    unique_tracks.update(test_predictions_df['Predicted_Track'].unique())
    
    # Also check probability columns to find all possible tracks
    for col in test_predictions_df.columns:
        if col.startswith('Prob_'):
            track_name = col[5:]  # Remove 'Prob_' prefix
            unique_tracks.add(track_name)
    
    # Convert to sorted list for consistent processing
    all_tracks = sorted(list(unique_tracks))
    logger.warning(f"Found {len(all_tracks)} unique tracks for calibration analysis")
    
    # Create extended calibration data
    extended_df = create_extended_calibration_data(test_predictions_df, all_tracks)
    logger.warning(f"Created comprehensive calibration data with {len(extended_df)} entries")
    
    # Filter data for different prediction types
    positive_df = extended_df[extended_df['Prediction_Type'] == 'Positive']
    negative_df = extended_df[extended_df['Prediction_Type'] == 'Negative']
    
    # Save summary data for reference
    summary_data = {
        'Prediction_Type': ['Positive', 'Negative', 'Combined'],
        'Sample_Count': [len(positive_df), len(negative_df), len(extended_df)],
    }
    summary_df = pd.DataFrame(summary_data)
    
    # Create global calibration plots
    logger.warning("Creating global calibration plots...")
    
    # Positive predictions (track will be used)
    pos_ece = plot_calibration(
        positive_df['Confidence'].values,
        positive_df['Correct'].values,
        'Global Calibration for Positive Track Predictions',
        os.path.join(visualizations_dir, 'global_positive_calibration_curve.png')
    )
    
    # Negative predictions (track will NOT be used)
    neg_ece = plot_calibration(
        negative_df['Confidence'].values,
        negative_df['Correct'].values,
        'Global Calibration for Negative Track Predictions',
        os.path.join(visualizations_dir, 'global_negative_calibration_curve.png')
    )
    
    # Combined calibration (both positive and negative)
    combined_ece = plot_calibration(
        extended_df['Confidence'].values,
        extended_df['Correct'].values,
        'Global Calibration for All Prediction Types',
        os.path.join(visualizations_dir, 'global_calibration_curve.png')
    )
    
    summary_df['ECE'] = [pos_ece, neg_ece, combined_ece]
    
    # Per-line calibration plots
    if 'Line' in test_predictions_df.columns:
        logger.warning("Creating per-line calibration plots...")
        all_lines = test_predictions_df['Line'].unique()
        line_eces = {'Positive': {}, 'Negative': {}, 'Combined': {}}
        
        for line in all_lines:
            if pd.isnull(line) or line == '':
                continue
            
            # Filter extended data for this line
            line_extended_df = extended_df[extended_df['Line'] == line]
            if len(line_extended_df) == 0:
                continue
                
            line_pos_df = line_extended_df[line_extended_df['Prediction_Type'] == 'Positive']
            line_neg_df = line_extended_df[line_extended_df['Prediction_Type'] == 'Negative']
            
            line_samples = len(line_pos_df) + len(line_neg_df)
            pos_samples = len(line_pos_df)
            
            # Skip lines with too few samples
            if pos_samples < 10:  # Using positive samples as the metric since they're fewer
                logger.warning(f"Skipping calibration plot for line {line}: only {pos_samples} positive samples")
                
                # Create a directory for this line
                line_safe_name = str(line).replace(" ", "_").replace("/", "_").replace("\\", "_")
                line_dir = os.path.join(per_line_dir, line_safe_name)
                os.makedirs(line_dir, exist_ok=True)
                
                # Write a note to a text file
                with open(os.path.join(line_dir, "no_data_available.txt"), 'w') as f:
                    f.write(f"Insufficient data to create calibration plot for line: {line}\n")
                    f.write(f"Found only {pos_samples} positive samples; minimum 10 required.\n")
                continue
            
            # Create a directory for this line
            line_safe_name = str(line).replace(" ", "_").replace("/", "_").replace("\\", "_")
            line_dir = os.path.join(per_line_dir, line_safe_name)
            os.makedirs(line_dir, exist_ok=True)
            
            # Positive predictions calibration
            pos_line_ece = plot_calibration(
                line_pos_df['Confidence'].values,
                line_pos_df['Correct'].values,
                f'Calibration for Line {line} (Positive Predictions)',
                os.path.join(line_dir, f'{line_safe_name}_positive_calibration_curve.png')
            )
            line_eces['Positive'][line] = pos_line_ece
            
            # Negative predictions calibration
            neg_line_ece = plot_calibration(
                line_neg_df['Confidence'].values,
                line_neg_df['Correct'].values,
                f'Calibration for Line {line} (Negative Predictions)',
                os.path.join(line_dir, f'{line_safe_name}_negative_calibration_curve.png')
            )
            line_eces['Negative'][line] = neg_line_ece
            
            # Combined calibration
            combined_line_ece = plot_calibration(
                line_extended_df['Confidence'].values,
                line_extended_df['Correct'].values,
                f'Calibration for Line {line} (All Predictions)',
                os.path.join(line_dir, f'{line_safe_name}_calibration_curve.png')
            )
            line_eces['Combined'][line] = combined_line_ece
        
        # Create summary plots of ECEs by line
        for pred_type in ['Combined', 'Positive', 'Negative']:
            if not line_eces[pred_type]:
                continue
                
            plt.figure(figsize=(12, 6))
            lines = list(line_eces[pred_type].keys())
            eces = [line_eces[pred_type][line] for line in lines]
            
            # Skip if no data
            if not eces:
                continue
                
            # Sort by ECE value
            sorted_indices = np.argsort(eces)
            sorted_lines = [lines[i] for i in sorted_indices]
            sorted_eces = [eces[i] for i in sorted_indices]
            
            # Get global ECE for this prediction type
            if pred_type == 'Positive':
                global_ece = pos_ece
            elif pred_type == 'Negative':
                global_ece = neg_ece
            else:  # Combined
                global_ece = combined_ece
            
            # Create bar chart
            plt.bar(range(len(sorted_lines)), sorted_eces, color='skyblue')
            plt.axhline(y=global_ece, color='red', linestyle='--', label=f'Global ECE: {global_ece:.4f}')
            plt.xticks(range(len(sorted_lines)), sorted_lines, rotation=45, ha='right')
            plt.xlabel('Train Line')
            plt.ylabel('Expected Calibration Error (ECE)')
            plt.title(f'Calibration Error by Train Line ({pred_type} Predictions)')
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            
            filename = 'line_calibration_comparison.png'
            if pred_type != 'Combined':
                filename = f'line_{pred_type.lower()}_calibration_comparison.png'
                
            plt.savefig(os.path.join(per_line_dir, filename))
            plt.close()
            logger.warning(f"Saved {pred_type} line calibration comparison to {os.path.join(per_line_dir, filename)}")
    
    return summary_df


def visualize_results(history, tracks, output_dir="output", train_lines=None):
    """Create essential visualizations of model performance."""
    visualizations_dir = os.path.join(output_dir, "visualizations")
    os.makedirs(visualizations_dir, exist_ok=True)
    logger.warning(f"Creating visualizations in {visualizations_dir}")

    
    # Create per-line visualizations directory
    per_line_dir = os.path.join(visualizations_dir, "per_line")
    os.makedirs(per_line_dir, exist_ok=True)
    
    # Plot global training curves (Loss and Accuracy)
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.plot(history['train_losses'], label='Train Loss')
    plt.plot(history['val_losses'], label='Validation Loss')
    plt.title('GLOBAL Model Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(1, 2, 2)
    plt.plot(history['train_accuracies'], label='Train Accuracy')
    plt.plot(history['val_accuracies'], label='Validation Accuracy')
    plt.title('GLOBAL Model Accuracy')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(visualizations_dir, "training_history.png"))
    plt.close()
    
    # Plot global confusion matrix
    cm = history['confusion_matrix']
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=tracks, yticklabels=tracks)
    plt.title('GLOBAL Confusion Matrix')
    plt.xlabel('Predicted Track')
    plt.ylabel('True Track')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(os.path.join(visualizations_dir, "confusion_matrix.png"))
    plt.close()
    
    # Create per-line visualizations if line information is available
    logger.warning(f"Checking for required data for per-line visualizations...")
    logger.warning(f"train_lines: {train_lines is not None}")
    logger.warning(f"'all_predictions' in history: {'all_predictions' in history}")
    logger.warning(f"'all_targets' in history: {'all_targets' in history}")
    logger.warning(f"'line_data' in history: {'line_data' in history}")
    
    # Use a fixed list of train lines based on our data analysis
    known_train_lines = [
        'ACELA EXPRESS', 'AMTRAK', 'Amtrak', 'KEYSTONE', 
        'PENNSYLVANIAN', 'REGIONAL',
        'Gladstone Branch', 'Montclair-Boonton', 'Morristown Line', 
        'No Jersey Coast', 'Northeast Corrdr', 'Raritan Valley'
    ]
    
    # Explicitly create line_data if it doesn't exist
    if 'all_predictions' in history and ('line_data' not in history or len(history['line_data']) == 0):
        num_samples = len(history['all_predictions'])
        # Create synthetic line data to ensure we have charts for each line
        synthetic_data = np.array(['All'] * num_samples)
        history['line_data'] = synthetic_data
        logger.warning(f"Created synthetic line_data for {num_samples} predictions")
    
    # Ensure we have valid train_lines
    if train_lines is None or len(train_lines) == 0 or (len(train_lines) == 1 and train_lines[0] == 'All'):
        train_lines = known_train_lines
        logger.warning(f"Using hardcoded list of {len(train_lines)} train lines")
    
    # Make sure 'All' is included for overall metrics
    if 'All' not in train_lines:
        train_lines = ['All'] + train_lines
        logger.warning("Added 'All' to train lines list for global metrics")
    
    # Proceed with per-line visualizations if we have the necessary data
    if 'all_predictions' in history and 'all_targets' in history and 'line_data' in history:
        # For each train line, create separate confusion matrix and training history plots
        line_metrics = {}
        logger.warning(f"Creating per-line visualizations for lines: {train_lines}")
        
        # First collect all available test data and metrics 
        all_line_indices = {}
        all_line_predictions = {}
        all_line_targets = {}
        
        # Process lines that have actual data first
        for line in set(history['line_data']):
            try:
                if pd.isna(line) or line == '' or line is None:
                    continue
                    
                # Get indices for this line from actual data
                line_indices = np.array(history['line_data']) == str(line)
                total_indices = len(line_indices)
                matching_indices = np.sum(line_indices)
                
                if matching_indices > 0:
                    # Get predictions and targets for this line
                    line_predictions = np.array([p for i, p in enumerate(history['all_predictions']) if line_indices[i]])
                    line_targets = np.array([t for i, t in enumerate(history['all_targets']) if line_indices[i]])
                    
                    if len(line_predictions) > 0 and len(line_targets) > 0:
                        all_line_indices[str(line)] = line_indices
                        all_line_predictions[str(line)] = line_predictions
                        all_line_targets[str(line)] = line_targets
                        logger.warning(f"Collected data for line {line}: {len(line_predictions)} predictions")
            except Exception as e:
                logger.error(f"Error collecting data for line {line}: {e}")
        
        # Make sure we have 'All' data
        if 'All' not in all_line_predictions:
            all_line_predictions['All'] = np.array(history['all_predictions'])
            all_line_targets['All'] = np.array(history['all_targets'])
            all_line_indices['All'] = np.array([True] * len(history['all_predictions']))
            logger.warning(f"Added global 'All' data with {len(all_line_predictions['All'])} samples")
        
        # Process each line, including ones with no actual data
        for line in train_lines:
            # Skip generating 'All' plots within the per_line directory
            if str(line).strip() == 'All':
                 continue

            # Skip if the line is empty
            if pd.isna(line) or line == '' or line is None:
                logger.warning(f"Skipping empty line: {line}")
                continue
                
            logger.warning(f"Processing line: {line}")
            line_safe_name = str(line).replace(" ", "_").replace("/", "_").replace("\\", "_")
            line_dir = os.path.join(per_line_dir, line_safe_name)
            os.makedirs(line_dir, exist_ok=True)
            
            # Use collected data if available, otherwise use 'All' data
            if str(line) in all_line_predictions:
                line_predictions = all_line_predictions[str(line)]
                line_targets = all_line_targets[str(line)]
            else:
                # No specific data collected for this line (might not be in test set)
                line_predictions = np.array([]) # Ensure empty arrays
                line_targets = np.array([])
                logger.warning(f"No specific test data found for line '{line}'. Skipping plots or showing 'no data'.")
            
            if len(line_predictions) == 0 or len(line_targets) == 0:
                logger.warning(f"No prediction data available for line: {line}")
                # Create an empty file to show we tried
                with open(os.path.join(line_dir, "no_data_available.txt"), 'w') as f:
                    f.write(f"No prediction data available for line: {line}\n")
                continue
                
            # Calculate metrics for this line
            line_accuracy = accuracy_score(line_targets, line_predictions)
            line_precision, line_recall, line_f1, _ = precision_recall_fscore_support(
                line_targets, line_predictions, average='weighted', zero_division=0
            )
            
            # Plot confusion matrix
            try:
                # Check if there's data before creating the matrix
                if len(line_targets) > 0 and len(line_predictions) > 0:
                    unique_labels = sorted(np.unique(np.concatenate((line_targets, line_predictions))))
                    # Get actual track names corresponding to the integer labels present in this subset
                    present_track_names = [tracks[i] for i in unique_labels if i < len(tracks)]

                    # Create confusion matrix specifically for the unique labels present
                    # Ensure labels argument matches the length of present_track_names for correct mapping
                    if len(present_track_names) == len(unique_labels):
                        line_cm = confusion_matrix(line_targets, line_predictions, labels=unique_labels)
                        plt.figure(figsize=(min(10, len(present_track_names)*0.8 + 2), min(8, len(present_track_names)*0.6 + 2))) # Adjust size based on labels
                        sns.heatmap(line_cm, annot=True, fmt='d', cmap='Blues', xticklabels=present_track_names, yticklabels=present_track_names)
                        plt.title(f'Confusion Matrix - {line}')
                        plt.xlabel('Predicted Track')
                        plt.ylabel('True Track')
                        plt.xticks(rotation=45, ha='right')
                        plt.yticks(rotation=0)
                        plt.tight_layout()

                        output_path = os.path.join(line_dir, f"{line_safe_name}_confusion_matrix.png")
                        plt.savefig(output_path)
                        plt.close()
                    else:
                        logger.warning(f"Label mismatch for confusion matrix on line {line}. Unique labels: {unique_labels}, Track names: {present_track_names}. Skipping heatmap.")
                        with open(os.path.join(line_dir, f"{line_safe_name}_confusion_matrix_label_mismatch.txt"), 'w') as f:
                            f.write(f"Could not generate confusion matrix heatmap due to label mismatch for line: {line}\n")
                            f.write(f"Unique integer labels found: {unique_labels}\n")
                            f.write(f"Corresponding track names found: {present_track_names}\n")
                else:
                     logger.warning(f"Skipping confusion matrix for line {line} due to no data.")
                     # Optionally create a placeholder image/text file
                     with open(os.path.join(line_dir, f"{line_safe_name}_confusion_matrix_no_data.txt"), 'w') as f:
                         f.write(f"No data available to generate confusion matrix for line: {line}\n")

            except Exception as e:
                logger.error(f"Could not create confusion matrix for line {line}: {e}")
            
            # Create a simple bar chart showing accuracy for this line vs global
            try:
                plt.figure(figsize=(8, 5))
                plt.bar(['Global', line], [history['final_accuracy'], line_accuracy], color=['blue', 'green'])
                plt.title(f'Accuracy Comparison - {line} vs Global')
                plt.ylabel('Accuracy')
                plt.ylim(0, 1.0)
                plt.grid(axis='y', linestyle='--')
                plt.tight_layout()
                
                output_path = os.path.join(line_dir, f"{line_safe_name}_accuracy_comparison.png")
                plt.savefig(output_path)
                plt.close()
            except Exception as e:
                logger.error(f"Could not create accuracy comparison for line {line}: {e}")
                
            # Create line-specific performance details chart instead of generic training history
            try:
                # Create a figure with line-specific performance details
                plt.figure(figsize=(14, 10))
                
                # 1. Accuracy by track for this line
                plt.subplot(2, 2, 1)
                
                # Count predictions by track
                track_predictions = {}
                track_correct = {}
                for pred, target in zip(line_predictions, line_targets):
                    track = str(target)
                    if track not in track_predictions:
                        track_predictions[track] = 0
                        track_correct[track] = 0
                    
                    track_predictions[track] += 1
                    if pred == target:
                        track_correct[track] += 1
                
                # Calculate accuracy per track
                track_accuracy = {}
                for track in track_predictions:
                    if track_predictions[track] > 0:
                        track_accuracy[track] = track_correct[track] / track_predictions[track]
                    else:
                        track_accuracy[track] = 0
                
                # Plot track accuracies
                if track_accuracy:
                    tracks_sorted = sorted(track_accuracy.keys(), key=lambda x: track_predictions.get(x, 0), reverse=True)
                    
                    # Limit to top 10 tracks by frequency for readability
                    if len(tracks_sorted) > 10:
                        tracks_limited = tracks_sorted[:10]
                    else:
                        tracks_limited = tracks_sorted
                    
                    track_acc_values = [track_accuracy[t] for t in tracks_limited]
                    track_counts = [track_predictions[t] for t in tracks_limited]
                    
                    # Create bar chart
                    bars = plt.bar(tracks_limited, track_acc_values, color='skyblue')
                    
                    # Add count labels
                    for i, bar in enumerate(bars):
                        plt.text(
                            bar.get_x() + bar.get_width()/2,
                            bar.get_height() + 0.02,
                            f'n={track_counts[i]}',
                            ha='center', va='bottom',
                            fontsize=8
                        )
                    
                    plt.title(f'{line} - Accuracy by Track')
                    plt.xlabel('Track')
                    plt.ylabel('Accuracy')
                    plt.ylim(0, 1.05)
                    plt.grid(axis='y', linestyle='--')
                    plt.xticks(rotation=45, ha='right')
                else:
                    plt.text(0.5, 0.5, "No track data available", ha='center', va='center')
                    plt.title(f'{line} - No Track Data')
                
                # 2. Confusion matrix (simplified version)
                plt.subplot(2, 2, 2)
                
                # Only show most common tracks for readability
                if len(line_targets) > 0 and len(line_predictions) > 0:
                    # Get most common tracks
                    unique_tracks = sorted(set(line_targets))
                    track_counts = {t: np.sum(line_targets == t) for t in unique_tracks}
                    
                    # Filter to top N tracks
                    top_n = min(8, len(unique_tracks))
                    top_tracks = sorted(unique_tracks, key=lambda t: track_counts.get(t, 0), reverse=True)[:top_n]
                    
                    # Build limited confusion matrix
                    mask_target = np.isin(line_targets, top_tracks)
                    mask_pred = np.isin(line_predictions, top_tracks)
                    
                    # Only include rows where both prediction and target are in top tracks
                    mask = mask_target & mask_pred
                    if np.sum(mask) > 0:
                        filtered_targets = line_targets[mask]
                        filtered_preds = line_predictions[mask]
                        
                        # Build confusion matrix
                        cm = confusion_matrix(filtered_targets, filtered_preds)
                        
                        # Plot heatmap
                        track_labels = [str(t) for t in top_tracks]
                        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                                   xticklabels=track_labels, yticklabels=track_labels)
                        plt.title(f'{line} - Top {top_n} Tracks Confusion')
                        plt.xlabel('Predicted Track')
                        plt.ylabel('True Track')
                        plt.xticks(rotation=45, ha='right')
                    else:
                        plt.text(0.5, 0.5, "Insufficient data for confusion matrix", ha='center', va='center')
                        plt.title(f'{line} - Insufficient Data')
                else:
                    plt.text(0.5, 0.5, "No data available for confusion matrix", ha='center', va='center')
                    plt.title(f'{line} - No Data')
                
                # 3. Line performance metrics
                plt.subplot(2, 2, 3)
                
                if 'All' in all_line_predictions:
                    # Compare with all lines
                    metrics = {
                        'This Line': line_accuracy,
                        'Global': history['final_accuracy']
                    }
                    
                    # Add other metrics
                    if len(all_line_predictions) > 2:  # If we have other lines
                        other_lines = []
                        for other_line, other_preds in all_line_predictions.items():
                            if other_line != str(line) and other_line != 'All' and len(other_preds) > 10:
                                other_targets = all_line_targets[other_line]
                                other_acc = accuracy_score(other_targets, other_preds)
                                other_lines.append((other_line, other_acc, len(other_preds)))
                        
                        # Add top 3 other lines by sample count
                        other_lines.sort(key=lambda x: x[2], reverse=True)
                        for i, (other_line, other_acc, _) in enumerate(other_lines[:3]):
                            metrics[f'{other_line}'] = other_acc
                    
                    # Plot metrics
                    plt.bar(metrics.keys(), metrics.values(), color=['green', 'blue'] + ['lightgray'] * (len(metrics) - 2))
                    plt.title(f'{line} vs Other Lines')
                    plt.ylabel('Accuracy')
                    plt.ylim(0, 1.0)
                    plt.grid(axis='y', linestyle='--')
                    
                    # Add labels with percentage difference from global
                    for i, (key, value) in enumerate(metrics.items()):
                        if key == 'This Line':
                            diff = value - metrics['Global']
                            diff_pct = diff * 100
                            color = 'green' if diff >= 0 else 'red'
                            label = f"{value:.3f}\n({diff_pct:+.1f}%)"
                            plt.text(i, value + 0.02, label, ha='center', va='bottom', color=color)
                        else:
                            plt.text(i, value + 0.02, f"{value:.3f}", ha='center', va='bottom')
                else:
                    plt.text(0.5, 0.5, "No comparison data available", ha='center', va='center')
                    plt.title(f'{line} - No Comparison Data')
                
                # 4. Sample distribution by hour 
                plt.subplot(2, 2, 4)
                
                if str(line) in all_line_indices and 'hour_data' in history:
                    # Get hour data for this line
                    line_hour_data = [h for i, h in enumerate(history['hour_data']) if all_line_indices[str(line)][i]]
                    
                    # Create distribution
                    if line_hour_data:
                        hour_counts = pd.Series(line_hour_data).value_counts().sort_index()
                        hour_counts.plot(kind='bar', color='skyblue')
                        plt.title(f'{line} - Sample Distribution by Hour')
                        plt.xlabel('Hour of Day')
                        plt.ylabel('Sample Count')
                        plt.grid(axis='y', linestyle='--')
                    else:
                        plt.text(0.5, 0.5, "No time distribution data available", ha='center', va='center')
                        plt.title(f'{line} - No Time Data')
                else:
                    # Create a basic analysis of the targets
                    counts = pd.Series(line_targets).value_counts().sort_index()
                    if len(counts) > 0:
                        counts.plot(kind='bar', color='skyblue')
                        plt.title(f'{line} - Sample Track Distribution')
                        plt.xlabel('Track')
                        plt.ylabel('Sample Count')
                        plt.grid(axis='y', linestyle='--')
                        plt.xticks(rotation=45, ha='right')
                    else:
                        plt.text(0.5, 0.5, "No track distribution data available", ha='center', va='center')
                        plt.title(f'{line} - No Distribution Data')
                
                plt.tight_layout()
                output_path = os.path.join(line_dir, f"{line_safe_name}_performance_analysis.png")
                plt.savefig(output_path)
                plt.close()
                logger.warning(f"Saved performance analysis for line {line} to {output_path}")
            except Exception as e:
                logger.error(f"Could not create performance analysis for line {line}: {e}", exc_info=True)
                
            # Create a simple line chart showing train distribution
            try:
                sample_counts = pd.Series(line_targets).value_counts().sort_index()
                plt.figure(figsize=(10, 6))
                sample_counts.plot(kind='bar', color='skyblue')
                plt.title(f'Training Sample Distribution - {line}')
                plt.xlabel('Track')
                plt.ylabel('Number of Samples')
                plt.xticks(rotation=45, ha='right')
                plt.grid(axis='y', linestyle='--')
                plt.tight_layout()
                
                output_path = os.path.join(line_dir, f"{line_safe_name}_sample_distribution.png")
                plt.savefig(output_path)
                plt.close()
            except Exception as e:
                logger.error(f"Could not create sample distribution for line {line}: {e}")
            
            # Add to line metrics summary
            line_metrics[line] = {
                'accuracy': line_accuracy,
                'precision': line_precision,
                'recall': line_recall,
                'f1': line_f1,
                'support': len(line_predictions)
            }
        
        # Create a consolidated line metrics report
        if line_metrics:
            line_metrics_df = pd.DataFrame.from_dict(line_metrics, orient='index')
            
            # Add sample counts column
            line_metrics_df['samples'] = line_metrics_df['support']
            
            # Save metrics to CSV
            line_metrics_file = os.path.join(per_line_dir, "line_metrics_summary.csv")
            line_metrics_df.to_csv(line_metrics_file)
            logger.warning(f"Saved line metrics summary to {line_metrics_file} with {len(line_metrics_df)} lines")
            
            # Create a bar chart comparing accuracy across all lines
            plt.figure(figsize=(14, 8))
            # Sort and filter (remove 'All' from the comparison chart)
            plot_df = line_metrics_df.copy()
            if 'All' in plot_df.index:
                plot_df = plot_df.drop('All')
            
            if not plot_df.empty:
                # Plot accuracy by train line
                plot_df = plot_df.sort_values('accuracy', ascending=False)
                ax = plot_df.plot(
                    y='accuracy', kind='bar', color='skyblue', legend=False, figsize=(14, 8)
                )
                plt.axhline(y=history['final_accuracy'], color='red', linestyle='--', label='Global Accuracy')
                
                # Add sample count as text on bars
                for i, (line, row) in enumerate(plot_df.iterrows()):
                    plt.text(
                        i, row['accuracy'] + 0.02, 
                        f"n={int(row['samples'])}", 
                        ha='center', va='bottom',
                        fontsize=8, rotation=0
                    )
                
                plt.title('Accuracy by Train Line')
                plt.xlabel('Train Line')
                plt.ylabel('Accuracy')
                plt.ylim(0, 1.0)
                plt.legend()
                plt.grid(axis='y', linestyle='--')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(per_line_dir, "line_accuracy_comparison.png"))
                logger.warning(f"Saved line accuracy comparison to {os.path.join(per_line_dir, 'line_accuracy_comparison.png')}")
                plt.close()
                
                # Create a comprehensive metrics chart with accuracy, precision, recall, f1
                plt.figure(figsize=(14, 8))
                metrics_plot_df = plot_df[['accuracy', 'precision', 'recall', 'f1']].copy()
                metrics_plot_df = metrics_plot_df.sort_values('accuracy', ascending=False)
                metrics_plot_df.plot(kind='bar', figsize=(14, 8))
                plt.title('Performance Metrics by Train Line')
                plt.xlabel('Train Line')
                plt.ylabel('Score')
                plt.ylim(0, 1.0)
                plt.legend(title='Metric')
                plt.grid(axis='y', linestyle='--')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(per_line_dir, "line_metrics_comparison.png"))
                logger.warning(f"Saved comprehensive line metrics comparison to {os.path.join(per_line_dir, 'line_metrics_comparison.png')}")
                plt.close()
            else:
                logger.warning("No line metrics data available for comparison charts (after filtering)")
                
            # Create a global training history chart with annotations for all lines
            try:
                plt.figure(figsize=(15, 7))
                plt.subplot(1, 2, 1)
                plt.plot(history['train_losses'], label='Train Loss', color='blue', linewidth=2)
                plt.plot(history['val_losses'], label='Validation Loss', color='red', linewidth=2)
                plt.title('Global Model Loss with Line Metrics')
                plt.xlabel('Epoch')
                plt.ylabel('Loss')
                plt.grid(True)
                plt.legend()
                
                plt.subplot(1, 2, 2)
                plt.plot(history['train_accuracies'], label='Train Accuracy', color='blue', linewidth=2)
                plt.plot(history['val_accuracies'], label='Validation Accuracy', color='red', linewidth=2)
                
                # Add horizontal lines for each line's accuracy
                colors = plt.cm.tab20(np.linspace(0, 1, min(20, len(line_metrics_df))))
                for i, (line, row) in enumerate(line_metrics_df.sort_values('accuracy', ascending=False).iterrows()):
                    if line == 'All':
                        continue  # Skip global metrics
                    if i < 8:  # Limit to top 8 lines to avoid clutter
                        plt.axhline(y=row['accuracy'], color=colors[i], linestyle=':', alpha=0.7,
                                   label=f"{line}: {row['accuracy']:.3f}")
                
                plt.title('Global Model Accuracy with Line Performance')
                plt.xlabel('Epoch')
                plt.ylabel('Accuracy')
                plt.ylim(0, 1.05)
                plt.grid(True)
                plt.legend(loc='lower right', fontsize='small')
                
                plt.tight_layout()
                plt.savefig(os.path.join(per_line_dir, "global_history_with_lines.png"))
                plt.close()
                logger.warning(f"Saved global training history with line metrics to {os.path.join(per_line_dir, 'global_history_with_lines.png')}")
            except Exception as e:
                logger.error(f"Could not create global training history with line metrics: {e}")
    else:
        logger.warning("Could not create per-line visualizations: missing line information or prediction data")
    
    # Optional: Per-class metrics bar plot for global data
    try:
        class_metrics = []
        # Ensure we only process dictionary entries (actual classes)
        valid_report_items = {k: v for k, v in history['class_report'].items() if isinstance(v, dict)}
        for label, metrics in valid_report_items.items():
             # Check if label corresponds to a known track index, avoid aggregate stats like 'accuracy'
             try:
                 track_index = tracks.index(label) # Will raise ValueError if label is not a track
                 class_metrics.append({
                     'Track': label,
                     'Precision': metrics['precision'],
                     'Recall': metrics['recall'],
                     'F1-Score': metrics['f1-score'],
                     'Support': metrics['support']
                 })
             except ValueError:
                 logger.debug(f"Skipping non-track label '{label}' in class metrics plot.")
        
        if class_metrics:
            class_df = pd.DataFrame(class_metrics)
            class_df_melted = pd.melt(
                class_df,
                id_vars=['Track', 'Support'],
                value_vars=['Precision', 'Recall', 'F1-Score'],
                var_name='Metric', value_name='Value'
            ).sort_values('Track')
            
            plt.figure(figsize=(14, 7))
            sns.barplot(x='Track', y='Value', hue='Metric', data=class_df_melted)
            plt.title('GLOBAL Per-Class Metrics')
            plt.xlabel('Track')
            plt.ylabel('Score')
            plt.ylim(0, 1.05)
            plt.xticks(rotation=45, ha='right')
            plt.legend(title='Metric', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(axis='y', linestyle='--')
            plt.tight_layout()
            plt.savefig(os.path.join(visualizations_dir, "class_metrics.png"))
            plt.close()
    except Exception as e:
        logger.warning(f"Could not create per-class metrics visualization: {e}")
    

def create_all_trains_json(csv_path=None, output_dir="output"):
    """Create a JSON file from the existing all_trains.csv file."""
    import json
    from datetime import datetime
    import pandas as pd
    import os
    import numpy as np
    
    # Define custom JSON encoder to handle NumPy and NaN values
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (float, np.float64)) and np.isnan(obj):
                return 0.0
            return super(NpEncoder, self).default(obj)
    
    # Set default CSV path if not provided
    if csv_path is None:
        csv_path = os.path.join(output_dir, "model_artifacts", "all_trains.csv")
    
    # Check if the CSV file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return False
    
    try:
        # Load the CSV file
        all_trains_df = pd.read_csv(csv_path)
        print(f"Loaded {len(all_trains_df)} train records from {csv_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Create the JSON output path
        json_path = csv_path.replace('.csv', '.json')
        
        # Create the JSON structure
        json_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model_version": "1.0",
                "train_count": len(all_trains_df)
            },
            "trains": []
        }
        
        # Process each train record for JSON format
        for _, row in all_trains_df.iterrows():
            # Get all track probability columns
            track_prob_cols = [col for col in all_trains_df.columns if col.startswith('Prob_')]
            
            # Extract track probabilities
            all_track_probs = {}
            for col in track_prob_cols:
                track = col.replace('Prob_', '')
                # Handle NaN values - replace with 0
                prob_value = row[col]
                if pd.isna(prob_value):
                    prob_value = 0.0
                all_track_probs[track] = float(prob_value)
            
            # Get top 3 tracks based on probability values
            probs_dict = {track: prob for track, prob in all_track_probs.items()}
            sorted_probs = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
            
            # Create the top tracks list
            top_tracks = []
            for i, (track, prob) in enumerate(sorted_probs[:3]):
                if prob > 0:
                    # Convert track to integer before adding to JSON
                    try:
                        # Remove decimal part if it exists
                        track_int = int(float(track))
                        top_tracks.append({
                            "track": track_int,
                            "probability": float(prob)
                        })
                    except (ValueError, TypeError):
                        # Fallback to string if conversion fails
                        top_tracks.append({
                            "track": track,
                            "probability": float(prob)
                        })
            
            # Extract train information
            train_id = str(row.get('Train_ID', '')) if not pd.isna(row.get('Train_ID', None)) else ''
            
            # Extract line from Train_ID or determine based on destination
            line = str(row.get('Line', '')) if not pd.isna(row.get('Line', None)) else ''
            
            # If line is empty, derive it from other data
            if line == '':
                # Try to extract from Trip_ID pattern: 2025-05-01_6613_08:02 AM
                if not pd.isna(row.get('Trip_ID', None)):
                    trip_id = str(row.get('Trip_ID', ''))
                    if '_' in trip_id:
                        # Common line prefixes based on Train_ID ranges
                        if train_id.startswith('A') or train_id.startswith('P'):
                            line = 'Amtrak'
                        elif train_id.isdigit():
                            train_num = int(train_id)
                            if 6000 <= train_num <= 7000:
                                line = 'Morristown Line'
                            elif 5000 <= train_num <= 6000:
                                line = 'Raritan Valley'
                            elif 3000 <= train_num <= 4000:
                                line = 'Northeast Corridor'
                            elif 2000 <= train_num <= 3000:
                                line = 'North Jersey Coast'
                            else:
                                # Default to identifying by destination
                                if 'Dover' in str(row.get('Destination', '')):
                                    line = 'Morristown Line'
                                elif 'Trenton' in str(row.get('Destination', '')):
                                    line = 'Northeast Corridor'
                                elif 'Long Branch' in str(row.get('Destination', '')):
                                    line = 'North Jersey Coast'
                                elif 'Raritan' in str(row.get('Destination', '')):
                                    line = 'Raritan Valley'
            
            destination = str(row.get('Destination', '')) if not pd.isna(row.get('Destination', None)) else ''
            departure = str(row.get('Departure', '')) if not pd.isna(row.get('Departure', None)) else ''
            status = str(row.get('Status', '')) if not pd.isna(row.get('Status', None)) else ''
            
            # First try to extract date from Trip_ID before using timestamp
            date_part = None
            if not pd.isna(row.get('Trip_ID', None)):
                trip_id = str(row.get('Trip_ID', ''))
                if '_' in trip_id:
                    parts = trip_id.split('_')
                    if len(parts) >= 1 and len(parts[0]) >= 10:
                        # Extract date part from pattern like: 2025-05-01_6613_08:02 AM
                        try:
                            # Validate it's a proper date
                            pd.to_datetime(parts[0])
                            date_part = parts[0]
                        except:
                            date_part = None
            
            # Get timestamp for date information (only used if we can't get date from Trip_ID)
            timestamp = pd.to_datetime(row.get('Timestamp', datetime.now()))
            
            # Handle departure time - try different column names that might exist
            if departure == '' and not pd.isna(row.get('Departure_Time', None)):
                departure = str(row.get('Departure_Time', ''))
                
            # Try to extract departure time from Trip_ID if it's still empty
            time_part = None
            if departure == '' and not pd.isna(row.get('Trip_ID', None)):
                trip_id = str(row.get('Trip_ID', ''))
                if '_' in trip_id:
                    parts = trip_id.split('_')
                    if len(parts) >= 3:
                        # Extract time part from pattern like: 2025-05-01_6613_08:02 AM
                        time_part = parts[-1].strip()
                        departure = time_part
            
            # Add date component to departure time if it's just a time
            if departure and len(departure) <= 8:  # Simple check for time-only format (HH:MM AM/PM)
                # Use date from trip_id (prioritized) or timestamp as fallback
                date_str = date_part if date_part else timestamp.strftime('%Y-%m-%d')
                departure = f"{date_str} {departure}"
            
            # Create JSON entry for train record
            train_record = {
                "train_id": train_id,
                "line": line,
                "destination": destination,
                "departure_time": departure,
                "status": status.strip() if status and status.strip() != "" else "On Time",
                "track": None if pd.isna(row.get('True_Track', None)) or row.get('True_Track', '') == '' else row.get('True_Track'),
                "model_tracks": top_tracks,
                "all_track_probabilities": all_track_probs
            }
            
            json_data["trains"].append(train_record)
        
        # Write the JSON file
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, cls=NpEncoder)
        
        print(f"Successfully saved {len(all_trains_df)} train records as JSON to {json_path}")
        return True
    
    except Exception as e:
        print(f"Error creating JSON file: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to execute the simplified track prediction pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NJ Transit Track Prediction Model Training (Concise)')
    parser.add_argument('--input', default='output/processed_data', help='Directory containing preprocessed CSV data files')
    parser.add_argument('--output', default='output', help='Base directory for model artifacts and visualizations')
    parser.add_argument('--hidden-dim', type=int, default=64, help='Hidden dimension size (default: 64)')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size (default: 32)')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate (default: 0.001)')
    parser.add_argument('--epochs', type=int, default=300, help='Max training epochs (default: 300)')
    parser.add_argument('--predict-all', action='store_true', help='Legacy argument - all train data is now always saved')
    parser.add_argument('--create-json', action='store_true', help='Only create JSON from existing all_trains.csv')
    
    args = parser.parse_args()
    data_dir = args.input
    output_dir = args.output
    
    # Check if we only want to create JSON from existing CSV
    if args.create_json:
        logger.warning("Creating JSON file from existing all_trains.csv")
        print("Creating JSON file from existing all_trains.csv...")
        
        # Define the CSV path
        csv_path = os.path.join(output_dir, "model_artifacts", "all_trains.csv")
        
        # Create the JSON file
        if create_all_trains_json(csv_path, output_dir):
            logger.warning("Successfully created JSON file")
            print("Successfully created JSON file")
            return 0
        else:
            logger.error("Failed to create JSON file")
            print("Failed to create JSON file")
            return 1
    
    logger.warning("Starting NJ Transit Track Prediction Pipeline")
    logger.warning(f"Input: {data_dir}, Output: {output_dir}")
    logger.warning(f"Params: hidden={args.hidden_dim}, batch={args.batch_size}, lr={args.lr}, epochs={args.epochs}")
    print("Starting NJ Transit Track Prediction Pipeline...")
    
    start_time = datetime.now()
    
    try:
        logger.warning("Step 1: Loading data...")
        print("Step 1: Loading data...")
        df, tracks, _, feature_cols = load_track_data(data_dir) # train_lines not used directly later
        
        # Add historical track features
        logger.warning("Step 1b: Adding historical track features...")
        print("Step 1b: Adding historical track features...")
        df = add_historical_features(df)
        
        # Add track percentage features
        logger.warning("Step 1c: Adding track usage percentage features...")
        print("Step 1c: Adding track usage percentage features...")
        df = add_track_percentage_features(df, tracks)
        
        # Update feature_cols to include percentage features and count features
        percentage_features = [col for col in df.columns 
                              if (col.startswith('TrainID_Track_') and col.endswith('_Pct'))
                              or (col.startswith('Line_Track_') and col.endswith('_Pct'))
                              or (col.startswith('Dest_Track_') and col.endswith('_Pct'))]
        count_features = ['TrainID_Count', 'Line_Count', 'Dest_Count']
        feature_cols.extend(percentage_features)
        feature_cols.extend(count_features)
        logger.warning(f"Added {len(percentage_features)} track percentage features and {len(count_features)} count features to feature columns")
        
        logger.warning("Step 2: Preparing data...")
        print("Step 2: Preparing data...")
        X_train, X_test, y_train, y_test, input_dim, output_dim, feature_names, class_weights, scaler = prepare_model_data(
            df, tracks, feature_cols, output_dir
        )
        
        # Reconstruct X_all for the latest data evaluation
        X_all = np.vstack((X_train, X_test))
        
        # We always prepare the feature matrix for all train data for the historical record
        all_features = None
        
        # Since prepare_model_data already created all the necessary transformations,
        # let's recreate the feature matrix for all data
        logger.warning("Preparing feature matrix for all train data...")
        # Load the saved transformations
        scaler = joblib.load(os.path.join(output_dir, "model_artifacts", "scaler.pkl"))
        encoders = joblib.load(os.path.join(output_dir, "model_artifacts", "encoders.pkl"))
        target_encoder = joblib.load(os.path.join(output_dir, "model_artifacts", "target_encoder.pkl"))
        
        # Re-encode the target variable
        y_all_encoded = target_encoder.transform(df['Track'].values.reshape(-1, 1))
        
        # Re-create the feature matrix for all data
        with open(os.path.join(output_dir, "model_artifacts", "feature_names.txt"), 'r') as f:
            feature_cols_used = f.read().splitlines()
        
        logger.warning(f"Recreating feature matrix using {len(feature_cols_used)} features")
        
        # Identify numerical and categorical columns from feature_cols
        categorical_cols = []
        if 'Line' in df.columns and any('Line_' in col for col in feature_cols_used):
            categorical_cols.append('Line')
        if 'Destination' in df.columns and any('Destination_' in col for col in feature_cols_used):
            categorical_cols.append('Destination')
        
        # Get numerical columns (columns that aren't categorical or Line_*)
        numerical_cols = [col for col in feature_cols if col not in categorical_cols 
                         and not col.startswith('Line_') and col in df.columns]
        
        # Process numerical features
        X_numerical = df[numerical_cols].copy()
        for col in X_numerical.columns:
            non_numeric = pd.to_numeric(X_numerical[col], errors='coerce').isna()
            if non_numeric.any():
                col_mean = pd.to_numeric(X_numerical[col], errors='coerce').mean()
                X_numerical.loc[non_numeric, col] = col_mean
        
        # Apply the saved scaler
        X_numerical_scaled = scaler.transform(X_numerical)
        
        # Process categorical features if any
        X_categorical = pd.DataFrame()
        for col in categorical_cols:
            if col in df.columns and col in encoders:
                encoded = encoders[col].transform(df[col].values.reshape(-1, 1))
                current_encoded_cols = [f"{col}_{cat}" for cat in encoders[col].categories_[0]]
                encoded_df = pd.DataFrame(encoded, columns=current_encoded_cols)
                X_categorical = pd.concat([X_categorical, encoded_df], axis=1)
        
        # Get pre-encoded Line features
        line_cols = [col for col in feature_cols if col.startswith('Line_') and col in df.columns]
        pre_encoded_line_features = []
        if line_cols:
            pre_encoded_line_features = df[line_cols].values
        
        # Combine all feature components
        feature_components = [X_numerical_scaled]
        if not X_categorical.empty:
            feature_components.append(X_categorical.values)
        if len(pre_encoded_line_features) > 0:
            feature_components.append(pre_encoded_line_features)
        
        # Combine features into final matrix
        if len(feature_components) > 1:
            all_features = np.hstack(feature_components)
        else:
            all_features = X_numerical_scaled
            
        # Check for NaN values
        if np.isnan(all_features).any():
            logger.warning("NaN values found in feature matrix for all data! Replacing with 0.")
            all_features = np.nan_to_num(all_features)
            
        logger.warning(f"Prepared feature matrix for all {all_features.shape[0]} samples with {all_features.shape[1]} features")
        
        # Get train and test indices for later use with line information
        try:
            # We need to convert it to an array of classes for stratification
            stratify_values = df['Track'].values
            
            # Make sure stratify_values is an array, not a single value
            if len(stratify_values) > 0:
                train_indices, test_indices = train_test_split(
                    np.arange(len(df)), test_size=0.2, random_state=42, stratify=stratify_values
                )
            else:
                # Fallback if no stratification is possible
                train_indices, test_indices = train_test_split(
                    np.arange(len(df)), test_size=0.2, random_state=42
                )
                logger.warning("Could not stratify train/test split - using random split instead")
        except Exception as e:
            # Fallback without stratification
            logger.warning(f"Error during stratified splitting: {e}. Using random split instead.")
            train_indices, test_indices = train_test_split(
                np.arange(len(df)), test_size=0.2, random_state=42
            )
        
        # Get list of unique train lines from the Line column
        if 'Line' in df.columns:
            train_lines = sorted(df['Line'].unique())
            logger.warning(f"Found {len(train_lines)} unique train lines for per-line analysis")
            # If Line_ columns exist, also add those
            line_cols = [col for col in df.columns if col.startswith('Line_')]
            if line_cols:
                extracted_lines = [col.replace('Line_', '') for col in line_cols]
                train_lines = sorted(set(list(train_lines) + extracted_lines))
                logger.warning(f"Added lines from Line_ columns, now have {len(train_lines)} unique train lines")
        else:
            # Try to extract lines from Line_ columns
            line_cols = [col for col in df.columns if col.startswith('Line_')]
            if line_cols:
                train_lines = sorted([col.replace('Line_', '') for col in line_cols])
                logger.warning(f"Extracted {len(train_lines)} train lines from Line_ columns")
            else:
                logger.warning("No line information found in DataFrame. Per-line analysis may be limited.")
                train_lines = None
        
        logger.warning("Step 3: Training model...")
        print("Step 3: Training model...")
        model, history = train_model(
            X_train, y_train, X_test, y_test,
            input_dim, output_dim,
            feature_names=feature_names, # Keep for importance calculation if desired
            class_weights=class_weights,
            hidden_dim=args.hidden_dim,
            batch_size=args.batch_size,
            learning_rate=args.lr,
            num_epochs=args.epochs,
            output_dir=output_dir,
            df=df,  # Pass the full dataframe for line information
            train_indices=train_indices,
            test_indices=test_indices,
            train_lines=train_lines,
            tracks=tracks,
            X_all=X_all,  # Pass the full feature matrix for latest data feature handling
            scaler=scaler  # Pass the scaler for latest data feature handling
        )
        
        # Always generate data for all trains for historical record
        logger.warning("Step 3b: Generating data for all train records...")
        print("Step 3b: Generating data for all train records...")
        
        # Create a dataset with all data and make predictions
        all_dataset = TrackDataset(all_features, y_all_encoded)
        all_loader = DataLoader(all_dataset, batch_size=args.batch_size)
        
        model.eval()
        all_data_predictions = []
        all_data_probs = []
        
        with torch.no_grad():
            for inputs, targets in all_loader:
                # Apply temperature scaling for better calibrated probabilities
                outputs = model(inputs, apply_softmax=True, apply_temperature=True)
                _, predicted = torch.max(outputs, 1)
                all_data_predictions.extend(predicted.numpy())
                all_data_probs.append(outputs.numpy())
        
        # Create DataFrame with all train records
        all_trains_df = pd.DataFrame({
            'True_Track_Index': np.argmax(y_all_encoded, axis=1),
            'Predicted_Track_Index': all_data_predictions
        })
        
        # Add actual track labels
        if tracks is not None:
            all_trains_df['True_Track'] = all_trains_df['True_Track_Index'].apply(lambda idx: tracks[idx] if idx < len(tracks) else 'Unknown')
            all_trains_df['Predicted_Track'] = all_trains_df['Predicted_Track_Index'].apply(lambda idx: tracks[idx] if idx < len(tracks) else 'Unknown')
        else:
            all_trains_df['True_Track'] = all_trains_df['True_Track_Index'].astype(str)
            all_trains_df['Predicted_Track'] = all_trains_df['Predicted_Track_Index'].astype(str)
        
        # Add prediction probabilities
        all_probs_array = np.vstack(all_data_probs)
        if tracks is not None:
            for i, track in enumerate(tracks):
                if i < all_probs_array.shape[1]:
                    all_trains_df[f'Prob_{track}'] = all_probs_array[:, i]
        else:
            for i in range(all_probs_array.shape[1]):
                all_trains_df[f'Prob_Track_{i}'] = all_probs_array[:, i]
            
        # Add metadata from original dataframe
        useful_fields = ['Timestamp', 'Train_ID', 'Trip_ID', 'Line', 'Destination']
        for field in useful_fields:
            if field in df.columns:
                all_trains_df[field] = df[field].values
        
        # Reorder columns to put important metadata first
        ordered_columns = []
        
        # Start with the most important metadata
        for field in ['Timestamp', 'Train_ID', 'Trip_ID', 'Line', 'Destination']:
            if field in all_trains_df.columns:
                ordered_columns.append(field)
        
        # Add track info next
        track_cols = ['True_Track', 'Predicted_Track', 'True_Track_Index', 'Predicted_Track_Index']
        for col in track_cols:
            if col in all_trains_df.columns:
                ordered_columns.append(col)
        
        # Add all remaining columns (probabilities, etc.)
        for col in all_trains_df.columns:
            if col not in ordered_columns:
                ordered_columns.append(col)
        
        # Reorder the dataframe
        all_trains_df = all_trains_df[ordered_columns]
        
        # Save all train records to CSV
        all_trains_path = os.path.join(output_dir, "model_artifacts", "all_trains.csv")
        all_trains_df.to_csv(all_trains_path, index=False)
        logger.warning(f"Saved {len(all_trains_df)} train records to {all_trains_path}")
        print(f"Saved {len(all_trains_df)} train records to CSV")
            
        # Also save all train records as JSON
        all_json_path = os.path.join(output_dir, "model_artifacts", "all_trains.json")
        
        # Create the JSON structure
        all_json_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model_version": "1.0",
                "train_count": len(all_trains_df)
            },
            "trains": []
        }
            
        # Process each train record for JSON format
        for _, row in all_trains_df.iterrows():
            # Get all track probability columns
            track_prob_cols = [col for col in all_trains_df.columns if col.startswith('Prob_')]
            
            # Extract track probabilities
            all_track_probs = {}
            for col in track_prob_cols:
                track = col.replace('Prob_', '')
                # Handle NaN values - replace with 0
                prob_value = row[col]
                if pd.isna(prob_value):
                    prob_value = 0.0
                all_track_probs[track] = float(prob_value)
            
            # Get top 3 predictions based on probability values
            probs_dict = {track: prob for track, prob in all_track_probs.items()}
            sorted_probs = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
            
            # Create the top tracks list
            top_tracks = []
            for i, (track, prob) in enumerate(sorted_probs[:3]):
                if prob > 0:
                    # Convert track to integer before adding to JSON
                    try:
                        # Remove decimal part if it exists
                        track_int = int(float(track))
                        top_tracks.append({
                            "track": track_int,
                            "probability": float(prob)
                        })
                    except (ValueError, TypeError):
                        # Fallback to string if conversion fails
                        top_tracks.append({
                            "track": track,
                            "probability": float(prob)
                        })
            
            # Extract train information
            train_id = str(row.get('Train_ID', '')) if not pd.isna(row.get('Train_ID', None)) else ''
            
            # Extract line from Train_ID or determine based on destination
            line = str(row.get('Line', '')) if not pd.isna(row.get('Line', None)) else ''
            
            # If line is empty, derive it from other data
            if line == '':
                # Try to extract from Trip_ID pattern: 2025-05-01_6613_08:02 AM
                if not pd.isna(row.get('Trip_ID', None)):
                    trip_id = str(row.get('Trip_ID', ''))
                    if '_' in trip_id:
                        # Common line prefixes based on Train_ID ranges
                        if train_id.startswith('A') or train_id.startswith('P'):
                            line = 'Amtrak'
                        elif train_id.isdigit():
                            train_num = int(train_id)
                            if 6000 <= train_num <= 7000:
                                line = 'Morristown Line'
                            elif 5000 <= train_num <= 6000:
                                line = 'Raritan Valley'
                            elif 3000 <= train_num <= 4000:
                                line = 'Northeast Corridor'
                            elif 2000 <= train_num <= 3000:
                                line = 'North Jersey Coast'
                            else:
                                # Default to identifying by destination
                                if 'Dover' in str(row.get('Destination', '')):
                                    line = 'Morristown Line'
                                elif 'Trenton' in str(row.get('Destination', '')):
                                    line = 'Northeast Corridor'
                                elif 'Long Branch' in str(row.get('Destination', '')):
                                    line = 'North Jersey Coast'
                                elif 'Raritan' in str(row.get('Destination', '')):
                                    line = 'Raritan Valley'
            
            destination = str(row.get('Destination', '')) if not pd.isna(row.get('Destination', None)) else ''
            departure = str(row.get('Departure', '')) if not pd.isna(row.get('Departure', None)) else ''
            status = str(row.get('Status', '')) if not pd.isna(row.get('Status', None)) else ''
            
            # First try to extract date from Trip_ID before using timestamp
            date_part = None
            if not pd.isna(row.get('Trip_ID', None)):
                trip_id = str(row.get('Trip_ID', ''))
                if '_' in trip_id:
                    parts = trip_id.split('_')
                    if len(parts) >= 1 and len(parts[0]) >= 10:
                        # Extract date part from pattern like: 2025-05-01_6613_08:02 AM
                        try:
                            # Validate it's a proper date
                            pd.to_datetime(parts[0])
                            date_part = parts[0]
                        except:
                            date_part = None
            
            # Get timestamp for date information (only used if we can't get date from Trip_ID)
            timestamp = pd.to_datetime(row.get('Timestamp', pd.Timestamp.now()))
            
            # Handle departure time - try different column names that might exist
            if departure == '' and not pd.isna(row.get('Departure_Time', None)):
                departure = str(row.get('Departure_Time', ''))
                
            # Try to extract departure time from Trip_ID if it's still empty
            time_part = None
            if departure == '' and not pd.isna(row.get('Trip_ID', None)):
                trip_id = str(row.get('Trip_ID', ''))
                if '_' in trip_id:
                    parts = trip_id.split('_')
                    if len(parts) >= 3:
                        # Extract time part from pattern like: 2025-05-01_6613_08:02 AM
                        time_part = parts[-1].strip()
                        departure = time_part
            
            # Add date component to departure time if it's just a time
            if departure and len(departure) <= 8:  # Simple check for time-only format (HH:MM AM/PM)
                # Use date from trip_id (prioritized) or timestamp as fallback
                date_str = date_part if date_part else timestamp.strftime('%Y-%m-%d')
                departure = f"{date_str} {departure}"
            
            # Create train record for JSON
            train_record = {
                "train_id": train_id,
                "line": line,
                "destination": destination,
                "departure_time": departure,
                "status": status.strip() if status and status.strip() != "" else "On Time",
                "track": None if pd.isna(row.get('True_Track', None)) or row.get('True_Track', '') == '' else row.get('True_Track'),
                "model_tracks": top_tracks,
                "all_track_probabilities": all_track_probs
            }
            
            all_json_data["trains"].append(train_record)
        
        # Using the NpEncoder class defined at the top of the file
                
        # Write the JSON file
        with open(all_json_path, 'w') as f:
            json.dump(all_json_data, f, indent=2, cls=NpEncoder)
        
        logger.warning(f"Saved all {len(all_trains_df)} train records as JSON to {all_json_path}")
        print(f"Saved all {len(all_trains_df)} train records to JSON")
        
        logger.warning("Step 4: Generating visualizations...")
        print("Step 4: Generating visualizations...")
        visualize_results(history, tracks, output_dir, train_lines)
        
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        logger.warning("Track prediction pipeline completed successfully!")
        logger.warning(f"Model saved to '{os.path.join(output_dir, 'model_artifacts/track_predictor_model.pt')}'")
        logger.warning(f"Execution time: {execution_time}")
        print("Pipeline completed successfully!")
        print(f"Model saved to '{os.path.join(output_dir, 'model_artifacts/track_predictor_model.pt')}'")
        print(f"Execution time: {execution_time}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True) # Log traceback on error
        print(f"ERROR: Pipeline failed: {e}")
        # Minimal error logging to file
        error_log_path = os.path.join(output_dir, "pipeline_error.log")
        os.makedirs(output_dir, exist_ok=True) # Ensure output dir exists
        with open(error_log_path, "a") as f:
             f.write(f"{datetime.now()} - Pipeline failed: {e}\n")
             import traceback
             traceback.print_exc(file=f)
        print(f"Error details logged to {error_log_path}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
