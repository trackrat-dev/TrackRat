"""
Visualization functions for feature importance analysis.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.inspection import permutation_importance

from .utils import setup_plot, save_figure, COLORS

logger = logging.getLogger(__name__)

def plot_feature_importance(
    feature_names: List[str],
    importance_values: List[float],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    group_key: Optional[str] = None,
    group_name: Optional[str] = None,
    n_top_features: int = 20,
    figsize: Tuple[int, int] = (12, 10),
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate and save feature importance plot.
    
    Args:
        feature_names: List of feature names
        importance_values: List of importance values corresponding to features
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        group_key: Optional field name for grouping (e.g. 'line', 'destination', 'track')
        group_name: Optional group value for filtering (e.g. 'NEC', 'Trenton', '1')
        n_top_features: Number of top features to show
        figsize: Figure size
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    group_str = f"_{group_key}_{group_name}" if group_key and group_name else ""
    
    # Create a dataframe for easier manipulation
    df = pd.DataFrame({
        'feature': feature_names,
        'importance': importance_values
    })
    
    # Sort by importance and take top N features
    df = df.sort_values('importance', ascending=False).head(n_top_features)
    
    # Reverse order for horizontal bar chart (bottom to top)
    df = df.iloc[::-1]
    
    # Set up figure
    fig, ax = setup_plot(figsize=figsize)
    
    # Plot horizontal bar chart
    bars = ax.barh(df['feature'], df['importance'], color=COLORS['primary'])
    
    # Add value labels to the right of each bar
    for bar in bars:
        width = bar.get_width()
        ax.text(width * 1.01, bar.get_y() + bar.get_height()/2, 
                f'{width:.3f}', ha='left', va='center')
    
    # Set titles and labels
    group_title = f" - {group_name} {group_key}" if group_key and group_name else ""
    ax.set_title(f'Top {n_top_features} Feature Importance{group_title} (v{model_version})')
    ax.set_xlabel('Importance Score')
    ax.set_ylabel('Feature')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the figure
    filename = f"feature_importance{group_str}{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return saved_files

def plot_track_specific_feature_importance(
    all_tracks: List[str],
    feature_names: List[str],
    track_importances: Dict[str, List[float]],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    min_samples: int = 20,
    n_top_features: int = 15,
    show_plot: bool = False
) -> Dict[str, Dict[str, str]]:
    """
    Generate feature importance plots for specific tracks.
    
    Args:
        all_tracks: List of all tracks
        feature_names: List of feature names
        track_importances: Dictionary mapping track to list of importance values
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        min_samples: Minimum number of samples required for a track
        n_top_features: Number of top features to show
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    saved_files = {}
    
    # Create subdirectory for track-specific feature importances
    tracks_dir = Path(output_dir) / "tracks"
    tracks_dir.mkdir(exist_ok=True, parents=True)
    
    # Generate per-track feature importance plots
    logger.info("Generating per-track feature importance plots")
    
    for track in all_tracks:
        if track not in track_importances:
            logger.info(f"Skipping feature importance for track '{track}': no importance data")
            continue
        
        importance_values = track_importances[track]
        
        logger.info(f"Generating feature importance for track '{track}'")
        track_files = plot_feature_importance(
            feature_names, importance_values, tracks_dir, 
            model_version, timestamp, "track", track,
            n_top_features=n_top_features, show_plot=show_plot
        )
        
        saved_files[track] = track_files
    
    return saved_files

def plot_shap_summary(
    shap_values: np.ndarray,
    feature_names: List[str],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    max_display: int = 20,
    figsize: Tuple[int, int] = (12, 10),
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate and save SHAP summary plot.
    
    Args:
        shap_values: SHAP values array
        feature_names: List of feature names
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        max_display: Maximum number of features to display
        figsize: Figure size
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    
    # This requires shap package
    import shap
    
    # Set up figure
    plt.figure(figsize=figsize)
    
    # Create SHAP summary plot
    # Note: We're manually capturing the figure instead of using shap's built-in save
    shap.summary_plot(
        shap_values, 
        feature_names=feature_names,
        max_display=max_display,
        show=False
    )
    
    # Get the current figure
    fig = plt.gcf()
    
    # Save the figure
    filename = f"shap_summary{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return saved_files