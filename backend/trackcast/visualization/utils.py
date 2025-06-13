"""
Utility functions for visualization in TrackCast.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.gridspec import GridSpec
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)

# Define color palette for consistency across visualizations
COLORS = {
    "primary": "#1f77b4",  # Main color for primary plots
    "secondary": "#ff7f0e",  # Secondary color for comparison plots
    "accent": "#2ca02c",  # Accent color for highlights
    "error": "#d62728",  # Error/warning color
    "success": "#2ca02c",  # Success color
    "grid": "#cccccc",  # Grid line color
    "text": "#333333",  # Text color
    "background": "#f5f5f5",  # Background color
    "lines": [  # Color cycle for multi-line plots
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ],
    "heatmap": "Blues",  # Default heatmap color palette
    "bars": [  # Color cycle for bar plots
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ],
}

# Font settings for consistency
FONT_SETTINGS = {
    "family": "sans-serif",
    "weight": "normal",
    "size": 10,
    "title_size": 14,
    "subtitle_size": 12,
    "axis_label_size": 11,
    "annotation_size": 9,
    "legend_title_size": 11,
    "legend_size": 10,
    "tick_size": 9,
}


def setup_plot(
    figsize: Tuple[int, int] = (10, 6), style: str = "whitegrid"
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Set up a standardized matplotlib figure with consistent styling.

    Args:
        figsize: Figure size as (width, height) in inches
        style: Seaborn style to use

    Returns:
        Tuple of (figure, axes)
    """
    # Set global style
    sns.set_style(style)

    # Create figure and axes
    fig, ax = plt.subplots(figsize=figsize)

    # Apply consistent styling
    ax.grid(True, linestyle="--", alpha=0.7, color=COLORS["grid"])
    ax.set_facecolor(COLORS["background"])

    # Set font properties
    plt.rcParams.update(
        {
            "font.family": FONT_SETTINGS["family"],
            "font.weight": FONT_SETTINGS["weight"],
            "font.size": FONT_SETTINGS["size"],
            "axes.titlesize": FONT_SETTINGS["title_size"],
            "axes.labelsize": FONT_SETTINGS["axis_label_size"],
            "xtick.labelsize": FONT_SETTINGS["tick_size"],
            "ytick.labelsize": FONT_SETTINGS["tick_size"],
            "legend.title_fontsize": FONT_SETTINGS["legend_title_size"],
            "legend.fontsize": FONT_SETTINGS["legend_size"],
        }
    )

    return fig, ax


def setup_grid(
    grid_layout: Tuple[int, int] = (2, 2),
    figsize: Tuple[int, int] = (15, 12),
    height_ratios: Optional[List[int]] = None,
    width_ratios: Optional[List[int]] = None,
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """
    Create a figure with a grid of subplots with consistent styling.

    Args:
        grid_layout: Tuple of (rows, cols)
        figsize: Figure size as (width, height) in inches
        height_ratios: Optional list of height ratios for rows
        width_ratios: Optional list of width ratios for columns

    Returns:
        Tuple of (figure, list of axes)
    """
    rows, cols = grid_layout

    # Set seaborn style
    sns.set_style("whitegrid")

    # Create figure
    fig = plt.figure(figsize=figsize)

    # Create GridSpec with optional ratios
    if height_ratios and width_ratios:
        gs = GridSpec(rows, cols, height_ratios=height_ratios, width_ratios=width_ratios)
    elif height_ratios:
        gs = GridSpec(rows, cols, height_ratios=height_ratios)
    elif width_ratios:
        gs = GridSpec(rows, cols, width_ratios=width_ratios)
    else:
        gs = GridSpec(rows, cols)

    # Create and style all axes
    axes = []
    for i in range(rows * cols):
        row, col = divmod(i, cols)
        ax = fig.add_subplot(gs[row, col])

        # Apply consistent styling
        ax.grid(True, linestyle="--", alpha=0.7, color=COLORS["grid"])
        ax.set_facecolor(COLORS["background"])
        axes.append(ax)

    # Set font properties
    plt.rcParams.update(
        {
            "font.family": FONT_SETTINGS["family"],
            "font.weight": FONT_SETTINGS["weight"],
            "font.size": FONT_SETTINGS["size"],
            "axes.titlesize": FONT_SETTINGS["title_size"],
            "axes.labelsize": FONT_SETTINGS["axis_label_size"],
            "xtick.labelsize": FONT_SETTINGS["tick_size"],
            "ytick.labelsize": FONT_SETTINGS["tick_size"],
            "legend.title_fontsize": FONT_SETTINGS["legend_title_size"],
            "legend.fontsize": FONT_SETTINGS["legend_size"],
        }
    )

    # Add more space between subplots
    plt.tight_layout()

    return fig, axes


def save_figure(
    fig: plt.Figure,
    filename: str,
    output_dir: Union[str, Path],
    formats: List[str] = ["png"],  # Only use PNG format
    dpi: int = 300,
    close_fig: bool = True,
) -> Dict[str, str]:
    """
    Save a figure in PNG format with standardized naming.

    Args:
        fig: Matplotlib figure to save
        filename: Base filename (without extension)
        output_dir: Directory to save figure in
        formats: List of file formats to save (default: PNG only)
        dpi: Resolution in dots per inch
        close_fig: Whether to close the figure after saving

    Returns:
        Dictionary of saved file paths by format
    """
    # Convert to Path object if needed
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    # Create directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save in each format
    saved_files = {}
    for fmt in formats:
        output_path = output_dir / f"{filename}.{fmt}"
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        saved_files[fmt] = str(output_path)
        logger.info(f"Saved figure to {output_path}")

    if close_fig:
        plt.close(fig)

    return saved_files


def create_subdirectory(parent_dir: Union[str, Path], subdir_name: str) -> Path:
    """
    Create a subdirectory within a parent directory.

    Args:
        parent_dir: Parent directory path
        subdir_name: Name of the subdirectory to create

    Returns:
        Path to the created subdirectory
    """
    # Convert to Path object if needed
    if isinstance(parent_dir, str):
        parent_dir = Path(parent_dir)

    # Create subdirectory
    subdir_path = parent_dir / subdir_name
    subdir_path.mkdir(parents=True, exist_ok=True)

    return subdir_path


def sanitize_string(text: str) -> str:
    """
    Convert a string to a safe filename by replacing invalid characters.

    Args:
        text: String to sanitize

    Returns:
        Sanitized string suitable for use in filenames
    """
    # Replace spaces and special characters
    safe_name = str(text).replace(" ", "_").replace("/", "_").replace("\\", "_")
    safe_name = safe_name.replace(":", "_").replace("*", "_").replace("?", "_")
    safe_name = safe_name.replace('"', "_").replace("<", "_").replace(">", "_")
    safe_name = safe_name.replace("|", "_").replace("'", "_")

    return safe_name


def calculate_ece(
    confidences: np.ndarray, correctness: np.ndarray, n_bins: int = 10
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Expected Calibration Error and bin statistics.

    Args:
        confidences: Array of confidence scores (predicted probabilities)
        correctness: Array of correctness values (0 or 1)
        n_bins: Number of bins to use for ECE calculation

    Returns:
        Tuple containing (ece, bin_confidences, bin_accuracies, bin_counts)
    """
    bin_indices = np.digitize(confidences, np.linspace(0, 1, n_bins + 1))
    ece = 0
    bin_counts = np.zeros(n_bins)
    bin_confidences = np.zeros(n_bins)
    bin_accuracies = np.zeros(n_bins)

    for bin_idx in range(1, n_bins + 1):
        bin_mask = bin_indices == bin_idx
        if np.sum(bin_mask) > 0:
            bin_counts[bin_idx - 1] = np.sum(bin_mask)
            bin_confidences[bin_idx - 1] = np.mean(confidences[bin_mask])
            bin_accuracies[bin_idx - 1] = np.mean(correctness[bin_mask])
            ece += (np.sum(bin_mask) / len(confidences)) * np.abs(
                bin_confidences[bin_idx - 1] - bin_accuracies[bin_idx - 1]
            )

    return ece, bin_confidences, bin_accuracies, bin_counts


def add_value_labels(
    ax: plt.Axes, values: List, fmt: str = "{:.3f}", offset: Tuple[float, float] = (0, 5)
):
    """
    Add value labels above bars in a bar chart.

    Args:
        ax: Matplotlib axes containing the bars
        values: List of values to display
        fmt: String format for the values
        offset: (x,y) offset in points for the labels
    """
    for i, rect in enumerate(ax.patches):
        if i < len(values):
            height = rect.get_height()
            # Only add annotation if the bar has positive height
            if height > 0:
                ax.annotate(
                    fmt.format(values[i]),
                    (rect.get_x() + rect.get_width() / 2.0, height),
                    ha="center",
                    va="bottom",
                    fontsize=FONT_SETTINGS["annotation_size"],
                    xytext=offset,
                    textcoords="offset points",
                )


def add_counts_to_bars(ax: plt.Axes, counts: List[int], offset: Tuple[float, float] = (0, 5)):
    """
    Add count annotations above bars in a bar chart.

    Args:
        ax: Matplotlib axes containing the bars
        counts: List of count values to display
        offset: (x,y) offset in points for the labels
    """
    for i, rect in enumerate(ax.patches):
        if i < len(counts):
            height = rect.get_height()
            # Only add annotation if the bar has positive height
            if height > 0:
                ax.annotate(
                    f"n={counts[i]}",
                    (rect.get_x() + rect.get_width() / 2.0, height),
                    ha="center",
                    va="bottom",
                    fontsize=FONT_SETTINGS["annotation_size"],
                    xytext=offset,
                    textcoords="offset points",
                )
