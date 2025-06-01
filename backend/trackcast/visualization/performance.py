"""
Visualization functions for time-based performance analysis.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import accuracy_score

from .utils import setup_plot, save_figure, COLORS

logger = logging.getLogger(__name__)

def plot_performance_by_time(
    y_true: List[str],
    y_pred: List[str],
    timestamps: List[datetime],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    show_plot: bool = False
) -> Dict[str, Dict[str, str]]:
    """
    Generate plots showing model performance by time of day and day of week.
    
    Args:
        y_true: List of actual track assignments
        y_pred: List of predicted track assignments
        timestamps: List of datetime objects for each prediction
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming (model timestamp)
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    saved_files = {}
    
    # Create dataframe for analysis
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred': y_pred,
        'timestamp': timestamps
    })
    
    # Add time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_correct'] = df['y_true'] == df['y_pred']
    
    # 1. Performance by hour of day
    logger.info("Generating performance by hour of day")
    fig, ax = setup_plot(figsize=(12, 6))
    
    # Group by hour and calculate accuracy
    hour_perf = df.groupby('hour')['is_correct'].agg(['count', 'mean']).reset_index()
    hour_perf.columns = ['hour', 'count', 'accuracy']
    
    # Ensure all 24 hours are represented
    all_hours = pd.DataFrame({'hour': range(24)})
    hour_perf = all_hours.merge(hour_perf, on='hour', how='left')
    # Fill missing values with 0 count and NaN accuracy (will be skipped in plotting)
    hour_perf['count'] = hour_perf['count'].fillna(0)
    # Keep accuracy as NaN for hours with no data
    
    # Filter out hours with no data for plotting
    hours_with_data = hour_perf.dropna(subset=['accuracy'])
    
    # Plot the accuracy with error bars (based on binomial distribution)
    if not hours_with_data.empty:
        error = 1.96 * np.sqrt(hours_with_data['accuracy'] * (1 - hours_with_data['accuracy']) / hours_with_data['count'])
        
        ax.errorbar(hours_with_data['hour'], hours_with_data['accuracy'], yerr=error, 
                    fmt='o-', markersize=8, linewidth=2, color=COLORS['primary'],
                    ecolor=COLORS['secondary'], capsize=5)
        
        # Annotate each point with the count
        for i, row in hours_with_data.iterrows():
            ax.annotate(f"{int(row['count'])}", 
                       (row['hour'], row['accuracy']), 
                       textcoords="offset points", 
                       xytext=(0, 10), 
                       ha='center')
    
    # Plot a horizontal line at the overall accuracy
    overall_accuracy = df['is_correct'].mean()
    ax.axhline(y=overall_accuracy, color='black', linestyle='--', 
               label=f'Overall Accuracy: {overall_accuracy:.3f}')
    
    # Add text annotation for hours with no data
    hours_no_data = hour_perf[hour_perf['accuracy'].isna()]
    if not hours_no_data.empty:
        for i, row in hours_no_data.iterrows():
            ax.annotate('No Data', 
                       (row['hour'], 0.02), 
                       ha='center', va='bottom',
                       fontsize=8, alpha=0.6)
    
    # Set titles and labels
    ax.set_title(f'Model Accuracy by Hour of Day (v{model_version})')
    ax.set_xlabel('Hour of Day (0-23)')
    ax.set_ylabel('Accuracy')
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(0, 1.05)
    ax.legend()
    
    # Add grid for readability
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Save the figure
    hour_filename = f"performance_by_hour{timestamp_str}"
    saved_files['hour'] = save_figure(fig, hour_filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    # 2. Performance by day of week
    logger.info("Generating performance by day of week")
    fig, ax = setup_plot(figsize=(12, 6))
    
    # Group by day and calculate accuracy
    day_perf = df.groupby('day_of_week')['is_correct'].agg(['count', 'mean']).reset_index()
    day_perf.columns = ['day_of_week', 'count', 'accuracy']
    
    # Ensure all 7 days are represented
    all_days = pd.DataFrame({'day_of_week': range(7)})
    day_perf = all_days.merge(day_perf, on='day_of_week', how='left')
    # Fill missing values with 0 count and NaN accuracy
    day_perf['count'] = day_perf['count'].fillna(0)
    
    # Get day names
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_perf['day_name'] = day_perf['day_of_week'].apply(lambda x: day_names[x])
    
    # Separate days with and without data
    days_with_data = day_perf.dropna(subset=['accuracy'])
    days_no_data = day_perf[day_perf['accuracy'].isna()]
    
    # Calculate error bars only for days with data
    error_with_data = 1.96 * np.sqrt(days_with_data['accuracy'] * (1 - days_with_data['accuracy']) / days_with_data['count'])
    
    # Use day_name for x-axis - all 7 days
    x_pos = np.arange(len(day_perf))
    
    # Create bars for all days, but only fill those with data
    bars = ax.bar(x_pos, day_perf['accuracy'].fillna(0), 
                  color=COLORS['primary'], alpha=0.7)
    
    # Add error bars only for days with data
    if not days_with_data.empty:
        days_with_data_indices = days_with_data.index
        ax.errorbar(days_with_data_indices, days_with_data['accuracy'], 
                   yerr=error_with_data, fmt='none', capsize=5,
                   ecolor=COLORS['secondary'])
    
    # Make bars for days without data look different (lighter/hollow)
    if not days_no_data.empty:
        for idx in days_no_data.index:
            bars[idx].set_alpha(0.2)
            bars[idx].set_edgecolor('gray')
            bars[idx].set_linewidth(1)
    
    # Set x-tick labels to day names
    ax.set_xticks(x_pos)
    ax.set_xticklabels(day_perf['day_name'])
    
    # Plot a horizontal line at the overall accuracy
    ax.axhline(y=overall_accuracy, color='black', linestyle='--', 
               label=f'Overall Accuracy: {overall_accuracy:.3f}')
    
    # Annotate bars
    for i, row in day_perf.iterrows():
        if pd.notna(row['accuracy']):
            # Days with data: show count and accuracy
            ax.annotate(f"{int(row['count'])}\n({row['accuracy']:.3f})", 
                       (i, row['accuracy']), 
                       textcoords="offset points", 
                       xytext=(0, 10), 
                       ha='center')
        else:
            # Days without data: show "No Data"
            ax.annotate('No Data', 
                       (i, 0.02), 
                       ha='center', va='bottom',
                       fontsize=9, alpha=0.6)
    
    # Set titles and labels
    ax.set_title(f'Model Accuracy by Day of Week (v{model_version})')
    ax.set_xlabel('Day of Week')
    ax.set_ylabel('Accuracy')
    ax.set_ylim(0, 1.05)
    ax.legend()
    
    # Add grid for readability
    ax.grid(True, linestyle='--', alpha=0.7, axis='y')
    
    # Save the figure
    day_filename = f"performance_by_day{timestamp_str}"
    saved_files['day'] = save_figure(fig, day_filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    # 3. Combined heatmap: hour x day
    logger.info("Generating hour x day performance heatmap")
    
    # Group by day and hour
    combined_perf = df.groupby(['day_of_week', 'hour'])['is_correct'].agg(['count', 'mean']).reset_index()
    combined_perf.columns = ['day_of_week', 'hour', 'count', 'accuracy']
    
    # Create a pivot table for the heatmap
    pivot_accuracy = combined_perf.pivot_table(
        values='accuracy', 
        index='day_of_week', 
        columns='hour',
        fill_value=np.nan
    )
    
    # Create a pivot table for the counts
    pivot_count = combined_perf.pivot_table(
        values='count', 
        index='day_of_week', 
        columns='hour',
        fill_value=0
    )
    
    # Ensure all 7 days of the week are represented (0-6)
    all_days = pd.Index(range(7), name='day_of_week')
    all_hours = pd.Index(range(24), name='hour')
    
    # Reindex to include all days and hours
    pivot_accuracy = pivot_accuracy.reindex(index=all_days, columns=all_hours, fill_value=np.nan)
    pivot_count = pivot_count.reindex(index=all_days, columns=all_hours, fill_value=0)
    
    # Set row labels to day names
    pivot_accuracy.index = [day_names[i] for i in pivot_accuracy.index]
    pivot_count.index = [day_names[i] for i in pivot_count.index]
    
    # Set up figure
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Create mask for cells with count < 5 (unreliable)
    mask = pivot_count < 5
    
    # Plot heatmap
    sns.heatmap(
        pivot_accuracy,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        vmin=0.0,
        vmax=1.0,
        mask=mask,
        ax=ax,
        linewidths=0.5,
        cbar_kws={'label': 'Accuracy'}
    )
    
    # Set titles and labels
    ax.set_title(f'Model Accuracy by Day and Hour (v{model_version})\nBlank cells have fewer than 5 samples')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Day of Week')
    
    # Save the figure
    heatmap_filename = f"performance_heatmap{timestamp_str}"
    saved_files['heatmap'] = save_figure(fig, heatmap_filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return saved_files

def plot_track_usage_heatmap(
    tracks: List[str],
    timestamps: List[datetime],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate a heatmap showing track usage patterns by time.
    
    Args:
        tracks: List of track assignments
        timestamps: List of datetime objects for each track assignment
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming (model timestamp)
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    
    # Create dataframe for analysis
    df = pd.DataFrame({
        'track': tracks,
        'timestamp': timestamps
    })
    
    # Add time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    
    # Calculate track counts by hour and day
    track_usage = df.groupby(['day_of_week', 'hour', 'track']).size().reset_index(name='count')
    
    # Day names
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Create a pivot table for the heatmap (sum of all tracks used in each time slot)
    pivot_usage = track_usage.pivot_table(
        values='count', 
        index='day_of_week', 
        columns='hour',
        aggfunc='sum',
        fill_value=0
    )
    
    # Ensure all 7 days of the week are represented (0-6)
    all_days = pd.Index(range(7), name='day_of_week')
    all_hours = pd.Index(range(24), name='hour')
    
    # Reindex to include all days and hours
    pivot_usage = pivot_usage.reindex(index=all_days, columns=all_hours, fill_value=0)
    
    # Set row labels to day names
    pivot_usage.index = [day_names[i] for i in pivot_usage.index]
    
    # Set up figure
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Plot heatmap
    sns.heatmap(
        pivot_usage,
        annot=True,
        fmt="d",
        cmap="YlGnBu",
        ax=ax,
        linewidths=0.5,
        cbar_kws={'label': 'Number of Track Assignments'}
    )
    
    # Set titles and labels
    ax.set_title(f'Track Usage by Day and Hour (v{model_version})')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Day of Week')
    
    # Save the figure
    filename = f"track_usage_heatmap{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    # Also create a track distribution plot
    track_counts = df['track'].value_counts().sort_index()
    
    fig, ax = setup_plot(figsize=(12, 6))
    
    # Plot bar chart
    bars = ax.bar(track_counts.index, track_counts.values, color=COLORS['primary'])
    
    # Add value annotations
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}',
                   xy=(bar.get_x() + bar.get_width()/2, height),
                   xytext=(0, 3),  # 3 points vertical offset
                   textcoords="offset points",
                   ha='center', va='bottom')
    
    # Set titles and labels
    ax.set_title(f'Track Usage Distribution (v{model_version})')
    ax.set_xlabel('Track')
    ax.set_ylabel('Count')
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7, axis='y')
    
    # Save the figure
    dist_filename = f"track_distribution{timestamp_str}"
    saved_files.update(save_figure(fig, dist_filename, output_dir))
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return saved_files