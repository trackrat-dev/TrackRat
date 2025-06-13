"""
Visualization functions for model training metrics.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .utils import COLORS, save_figure, setup_plot

logger = logging.getLogger(__name__)


def plot_learning_curves(
    train_losses: List[float],
    val_losses: Optional[List[float]] = None,
    val_accuracies: Optional[List[float]] = None,
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    show_plot: bool = False,
) -> Dict[str, Dict[str, str]]:
    """
    Generate and save combined learning curve plot showing both loss and accuracy.

    Args:
        train_losses: List of training loss values per epoch
        val_losses: List of validation loss values per epoch (optional)
        val_accuracies: List of validation accuracy values per epoch (optional)
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        show_plot: Whether to display plots in addition to saving them

    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    saved_files = {}

    # Create epoch indices
    epochs = np.arange(1, len(train_losses) + 1)

    # Create combined plot with both loss and accuracy
    fig, ax1 = setup_plot(figsize=(12, 6))

    # First y-axis: loss
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss", color=COLORS["primary"])
    ax1.plot(
        epochs,
        train_losses,
        "o-",
        color=COLORS["primary"],
        linewidth=2,
        markersize=4,
        label="Training Loss",
    )

    # Plot validation loss if available
    if val_losses and len(val_losses) > 0:
        # Handle case where validation might have different length
        val_epochs = np.arange(1, len(val_losses) + 1)
        ax1.plot(
            val_epochs,
            val_losses,
            "o-",
            color=COLORS["secondary"],
            linewidth=2,
            markersize=4,
            label="Validation Loss",
        )

    ax1.tick_params(axis="y", labelcolor=COLORS["primary"])
    ax1.legend(loc="upper left")

    # Second y-axis: accuracy (if available)
    if val_accuracies and len(val_accuracies) > 0:
        ax2 = ax1.twinx()
        ax2.set_ylabel("Accuracy", color=COLORS["accent"])

        # Handle case where validation might have different length
        val_epochs = np.arange(1, len(val_accuracies) + 1)
        ax2.plot(
            val_epochs,
            val_accuracies,
            "o-",
            color=COLORS["accent"],
            linewidth=2,
            markersize=4,
            label="Validation Accuracy",
        )

        ax2.tick_params(axis="y", labelcolor=COLORS["accent"])
        ax2.legend(loc="upper right")
        ax2.set_ylim(0, 1.05)  # Leave a little room above 1.0

    # Set title
    ax1.set_title(f"Training Metrics (v{model_version})")

    # Improve readability
    ax1.set_xlim(0, len(train_losses) + 1)

    # Save the figure
    combined_filename = f"learning_curve_combined{timestamp_str}"
    saved_files["combined"] = save_figure(fig, combined_filename, output_dir)

    if show_plot:
        plt.show()
    else:
        plt.close(fig)

    return saved_files
