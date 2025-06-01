"""
Visualization functions for confusion matrices.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix

from .utils import setup_plot, save_figure, COLORS

logger = logging.getLogger(__name__)

def plot_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    group_key: Optional[str] = None,
    group_name: Optional[str] = None,
    normalize: bool = False,
    figsize: Tuple[int, int] = (15, 12),
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate and save confusion matrix plot.
    
    Args:
        y_true: List of actual track assignments
        y_pred: List of predicted track assignments
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        group_key: Optional field name for grouping (e.g. 'line', 'destination')
        group_name: Optional group value for filtering (e.g. 'NEC', 'Trenton')
        normalize: Whether to normalize the confusion matrix
        figsize: Figure size
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    group_str = f"_{group_key}_{group_name}" if group_key and group_name else ""
    norm_str = "_normalized" if normalize else ""
    
    # Get unique track labels and sort them numerically
    labels = sorted(set(y_true) | set(y_pred), key=lambda x: int(x) if x.isdigit() else float('inf'))
    
    # Calculate confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    # Normalize if requested
    if normalize:
        # Normalize by column (predicted track) instead of by row (actual track)
        # This makes each column sum to 1 instead of each row
        cm = cm.astype('float') / cm.sum(axis=0)[np.newaxis, :]
        cm = np.nan_to_num(cm)  # Replace NaN with 0
    
    # Set up figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot confusion matrix
    sns.heatmap(
        cm,
        annot=True,
        fmt=".2f" if normalize else "d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
        annot_kws={"size": 9 if len(labels) > 15 else 10},
        cbar_kws={"label": "Normalized Probability" if normalize else "Count"}
    )
    
    # Set titles and labels
    group_title = f" - {group_name} {group_key}" if group_key and group_name else ""
    norm_title = " (Normalized by Predicted Track)" if normalize else ""
    ax.set_title(f'Confusion Matrix{group_title}{norm_title} (v{model_version})')
    ax.set_xlabel('Predicted Track')
    ax.set_ylabel('Actual Track')
    
    # Rotate tick labels for better readability
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    plt.setp(ax.get_yticklabels(), rotation=0)
    
    # Tight layout to avoid cutting off labels
    plt.tight_layout()
    
    # Save the figure
    filename = f"confusion_matrix{group_str}{norm_str}{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return saved_files

def plot_all_confusion_matrices(
    y_true: List[str],
    y_pred: List[str],
    lines: List[str],
    destinations: List[str],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    min_samples: int = 20,
    show_plot: bool = False
) -> Dict[str, Dict[str, str]]:
    """
    Generate normalized confusion matrices for overall model, per-line, and per-destination.

    Args:
        y_true: List of actual track assignments
        y_pred: List of predicted track assignments
        lines: List of train lines for each sample
        destinations: List of destinations for each sample
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        min_samples: Minimum number of samples required for a group to create a confusion matrix
        show_plot: Whether to display plots in addition to saving them

    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    saved_files = {}

    # 1. Overall normalized confusion matrix
    logger.info("Generating overall normalized confusion matrix")
    overall_files = plot_confusion_matrix(
        y_true, y_pred, output_dir, model_version, timestamp,
        normalize=True, show_plot=show_plot
    )
    saved_files['overall'] = overall_files

    # 2. Create subdirectories for line and destination confusion matrices
    lines_dir = Path(output_dir) / "lines"
    destinations_dir = Path(output_dir) / "destinations"
    lines_dir.mkdir(exist_ok=True, parents=True)
    destinations_dir.mkdir(exist_ok=True, parents=True)

    # 3. Per-line normalized confusion matrices
    logger.info("Generating per-line normalized confusion matrices")
    unique_lines = sorted(set(lines))
    saved_files['lines'] = {}

    for line in unique_lines:
        # Filter data by line
        line_indices = [i for i, l in enumerate(lines) if l == line]

        if len(line_indices) < min_samples:
            logger.info(f"Skipping confusion matrix for line '{line}': insufficient samples ({len(line_indices)})")
            continue

        line_y_true = [y_true[i] for i in line_indices]
        line_y_pred = [y_pred[i] for i in line_indices]

        # Create subdirectory for this line
        line_subdir = lines_dir / str(line)
        line_subdir.mkdir(exist_ok=True, parents=True)

        # Generate normalized confusion matrix
        logger.info(f"Generating normalized confusion matrix for line '{line}' with {len(line_indices)} samples")
        line_files = plot_confusion_matrix(
            line_y_true, line_y_pred, line_subdir, model_version, timestamp,
            group_key="line", group_name=line, normalize=True, show_plot=show_plot
        )

        saved_files['lines'][line] = line_files

    # 4. Per-destination normalized confusion matrices
    logger.info("Generating per-destination normalized confusion matrices")
    unique_destinations = sorted(set(destinations))
    saved_files['destinations'] = {}

    for dest in unique_destinations:
        # Filter data by destination
        dest_indices = [i for i, d in enumerate(destinations) if d == dest]

        if len(dest_indices) < min_samples:
            logger.info(f"Skipping confusion matrix for destination '{dest}': insufficient samples ({len(dest_indices)})")
            continue

        dest_y_true = [y_true[i] for i in dest_indices]
        dest_y_pred = [y_pred[i] for i in dest_indices]

        # Create subdirectory for this destination
        dest_subdir = destinations_dir / str(dest)
        dest_subdir.mkdir(exist_ok=True, parents=True)

        # Generate normalized confusion matrix
        logger.info(f"Generating normalized confusion matrix for destination '{dest}' with {len(dest_indices)} samples")
        dest_files = plot_confusion_matrix(
            dest_y_true, dest_y_pred, dest_subdir, model_version, timestamp,
            group_key="destination", group_name=dest, normalize=True, show_plot=show_plot
        )

        saved_files['destinations'][dest] = dest_files

    # 5. Create summary confusion matrix comparison if there are multiple lines/destinations
    if len(saved_files['lines']) > 1 or len(saved_files['destinations']) > 1:
        logger.info("Generating summary confusion matrix comparisons")

        # Create accuracy by line comparison
        if len(saved_files['lines']) > 1:
            plot_confusion_matrix_comparison(
                y_true, y_pred, lines, 'line',
                output_dir, model_version, timestamp,
                show_plot=show_plot
            )

        # Create accuracy by destination comparison
        if len(saved_files['destinations']) > 1:
            plot_confusion_matrix_comparison(
                y_true, y_pred, destinations, 'destination',
                output_dir, model_version, timestamp,
                show_plot=show_plot
            )

    return saved_files


def plot_confusion_matrix_comparison(
    y_true: List[str],
    y_pred: List[str],
    group_values: List[str],
    group_key: str,
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    min_samples: int = 20,
    figsize: Tuple[int, int] = (12, 8),
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Create a summary comparison of prediction accuracy across different groups.

    Args:
        y_true: List of actual track assignments
        y_pred: List of predicted track assignments
        group_values: List of group values (line or destination) for each sample
        group_key: Grouping field ('line' or 'destination')
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        min_samples: Minimum number of samples required for a group
        figsize: Figure size
        show_plot: Whether to display plots in addition to saving them

    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""

    # Calculate accuracy by group
    group_acc = {}
    group_counts = {}

    # Get unique group values
    unique_groups = sorted(set(group_values))

    for group in unique_groups:
        # Filter data by group
        group_indices = [i for i, g in enumerate(group_values) if g == group]

        if len(group_indices) < min_samples:
            logger.info(f"Skipping {group_key} '{group}' in comparison: insufficient samples ({len(group_indices)})")
            continue

        group_y_true = [y_true[i] for i in group_indices]
        group_y_pred = [y_pred[i] for i in group_indices]

        # Calculate accuracy
        accuracy = sum(1 for t, p in zip(group_y_true, group_y_pred) if t == p) / len(group_y_true)
        group_acc[group] = accuracy
        group_counts[group] = len(group_indices)

    # Create comparison plot
    fig, ax = plt.subplots(figsize=figsize)

    # Sort groups by accuracy for better visualization
    sorted_groups = sorted(group_acc.keys(), key=lambda g: group_acc[g], reverse=True)
    accuracies = [group_acc[g] for g in sorted_groups]
    counts = [group_counts[g] for g in sorted_groups]

    # Create bars with sequential coloring
    bars = ax.bar(
        sorted_groups,
        accuracies,
        color=[plt.cm.viridis(i/len(sorted_groups)) for i in range(len(sorted_groups))]
    )

    # Add value labels and sample counts
    for i, (acc, count) in enumerate(zip(accuracies, counts)):
        ax.annotate(
            f'{acc:.3f}',
            xy=(i, acc),
            xytext=(0, 3),
            textcoords="offset points",
            ha='center',
            va='bottom',
            fontsize=9
        )
        ax.annotate(
            f'n={count}',
            xy=(i, acc),
            xytext=(0, -14),
            textcoords="offset points",
            ha='center',
            va='top',
            fontsize=8,
            color='gray'
        )

    # Style the chart
    ax.set_ylim(0, max(accuracies) * 1.15)  # Add some headroom for annotations
    ax.set_xlabel(f'Train {group_key.capitalize()}')
    ax.set_ylabel('Prediction Accuracy')
    ax.set_title(f'Track Prediction Accuracy by {group_key.capitalize()} (v{model_version})')

    # Add grid
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    # Rotate x-axis labels for better readability if needed
    if max(len(str(g)) for g in sorted_groups) > 5:
        plt.xticks(rotation=45, ha='right')

    plt.tight_layout()

    # Save the figure
    filename = f"confusion_matrix_{group_key}_comparison{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)

    if show_plot:
        plt.show()
    else:
        plt.close(fig)

    return saved_files