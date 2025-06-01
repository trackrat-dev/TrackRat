"""
Visualization functions for model calibration analysis.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss

from .utils import (
    setup_plot, setup_grid, save_figure, COLORS, create_subdirectory, 
    sanitize_string, calculate_ece, add_value_labels, add_counts_to_bars
)

logger = logging.getLogger(__name__)

def create_extended_calibration_data(
    y_true: List[str],
    y_prob: List[Dict[str, float]],
    lines: Optional[List[str]] = None,
    destinations: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Create extended calibration data including both positive and negative predictions
    for comprehensive calibration analysis.
    
    Args:
        y_true: List of actual track assignments
        y_prob: List of dictionaries mapping tracks to probabilities
        lines: Optional list of train lines for each sample
        destinations: Optional list of destinations for each sample
        
    Returns:
        DataFrame with extended calibration data
    """
    # Get all unique track values
    unique_tracks = set()
    
    # Extract tracks from actual values
    unique_tracks.update(y_true)
    
    # Extract tracks from probability dictionaries
    for probs in y_prob:
        unique_tracks.update(probs.keys())
    
    # Convert to sorted list for consistent processing
    track_list = sorted(list(unique_tracks))
    logger.info(f"Found {len(track_list)} unique tracks for calibration analysis")
    
    # Data for extended calibration (including both positive and negative predictions)
    extended_data = []
    
    # For each sample and each track, create data points
    for i, (true_track, probs) in enumerate(zip(y_true, y_prob)):
        # Add line and destination info if available
        line = lines[i] if lines is not None else "Unknown"
        destination = destinations[i] if destinations is not None else "Unknown"
        
        for track in track_list:
            # Skip if no probability for this track
            if track not in probs:
                continue
            
            # Probability that this track will be used
            pos_confidence = probs[track]
            # Probability that this track will NOT be used
            neg_confidence = 1.0 - pos_confidence
            
            # Correctness of positive prediction (track will be used)
            pos_correct = 1 if track == true_track else 0
            # Correctness of negative prediction (track will NOT be used)
            neg_correct = 1 if track != true_track else 0
            
            # Add positive prediction (track will be used)
            extended_data.append({
                'Sample': i,
                'Track': track,
                'True_Track': true_track,
                'Prediction_Type': 'Positive',
                'Confidence': pos_confidence,
                'Correct': pos_correct,
                'Line': line,
                'Destination': destination
            })
            
            # Add negative prediction (track will NOT be used)
            extended_data.append({
                'Sample': i,
                'Track': track,
                'True_Track': true_track,
                'Prediction_Type': 'Negative',
                'Confidence': neg_confidence,
                'Correct': neg_correct,
                'Line': line,
                'Destination': destination
            })
    
    # Convert to DataFrame
    return pd.DataFrame(extended_data)

def plot_calibration_curve(
    y_true: List[str],
    y_prob: List[Dict[str, float]],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    group_key: Optional[str] = None,
    group_name: Optional[str] = None,
    n_bins: int = 10,
    figsize: Tuple[int, int] = (10, 8),
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate and save calibration curve plot.

    Args:
        y_true: List of actual track assignments
        y_prob: List of dictionaries mapping tracks to probabilities
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        group_key: Optional field name for grouping (e.g. 'line', 'destination')
        group_name: Optional group value for filtering (e.g. 'NEC', 'Trenton')
        n_bins: Number of bins for the calibration curve
        figsize: Figure size
        show_plot: Whether to display plots in addition to saving them

    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    group_str = f"_{group_key}_{group_name}" if group_key and group_name else ""

    # Extract probabilities for actual tracks
    confidences = []
    for true_label, prob_dict in zip(y_true, y_prob):
        # Get probability for the actual track, default to 0 if not present
        if true_label in prob_dict:
            confidences.append(prob_dict[true_label])
        else:
            confidences.append(0.0)

    # Create correctness array (always 1 since we're focusing on the true label)
    correctness = np.ones_like(confidences)

    # Create title based on grouping
    group_title = f" - {group_name} {group_key}" if group_key and group_name else ""
    title = f'Calibration Curve{group_title} (v{model_version})'

    # Generate calibration plot
    fig, ax, ece = plot_comprehensive_calibration(
        np.array(confidences),
        correctness,
        title=title,
        n_bins=n_bins,
        figsize=figsize
    )

    # Save the figure
    filename = f"calibration_curve{group_str}{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)

    if show_plot:
        plt.show()
    else:
        plt.close(fig)

    # Create reliability diagram (alternative visualization)
    fig, ax = setup_plot(figsize=figsize)

    # Calculate calibration curve
    prob_true, prob_pred = calibration_curve(
        correctness, confidences, n_bins=n_bins, strategy='uniform'
    )

    # Calculate Brier score
    brier_score = brier_score_loss(correctness, confidences)

    # Plot calibration curve
    ax.plot([0, 1], [0, 1], "k:", label="Perfectly calibrated")
    ax.plot(
        prob_pred, prob_true, "s-", color=COLORS['primary'],
        label=f"Model calibration (ECE: {ece:.3f})"
    )

    # Set title and labels
    ax.set_title(f'Reliability Diagram{group_title} (v{model_version})')
    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Fraction of positives')
    ax.legend(loc="lower right")

    # Add Brier score and ECE to plot
    ax.text(
        0.05, 0.95,
        f"Brier Score: {brier_score:.4f}\nECE: {ece:.4f}",
        verticalalignment='top',
        horizontalalignment='left',
        transform=ax.transAxes,
        fontsize=10,
        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round')
    )

    # Set axis limits
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.0])
    ax.grid(True, linestyle='--', alpha=0.7)

    # Save the reliability diagram
    filename = f"reliability_diagram{group_str}{timestamp_str}"
    reliability_files = save_figure(fig, filename, output_dir)

    if show_plot:
        plt.show()
    else:
        plt.close(fig)

    # Combine both visualizations in the result
    saved_files.update(reliability_files)

    return saved_files


def plot_comprehensive_calibration(
    confidences: np.ndarray,
    correctness: np.ndarray,
    title: str,
    n_bins: int = 10,
    figsize: Tuple[int, int] = (12, 8)
) -> Tuple[plt.Figure, plt.Axes, float]:
    """
    Create a comprehensive calibration plot with ECE calculation.
    
    Args:
        confidences: Array of confidence scores
        correctness: Array of correctness values (0 or 1)
        title: Plot title
        n_bins: Number of bins for the calibration curve
        figsize: Figure size as (width, height) in inches
        
    Returns:
        Tuple of (figure, axes, ece_value)
    """
    # Set up figure and axes
    fig, ax = setup_plot(figsize=figsize)
    
    # Calculate ECE and bin statistics
    ece, bin_confidences, bin_accuracies, bin_counts = calculate_ece(
        confidences, correctness, n_bins
    )
    
    # Plot the diagonal reference line (perfect calibration)
    ax.plot([0, 1], [0, 1], 'r--', label='Perfect Calibration')
    
    # Plot the calibration curve
    valid_bins = bin_counts > 0
    if np.sum(valid_bins) > 0:
        ax.plot(
            bin_confidences[valid_bins], 
            bin_accuracies[valid_bins], 
            's-', color=COLORS['primary'],
            linewidth=2, markersize=6, label='Model Calibration'
        )
        
        # Fill the area between curves to highlight error
        ax.fill_between(
            bin_confidences[valid_bins], 
            bin_confidences[valid_bins], 
            bin_accuracies[valid_bins], 
            alpha=0.2, color=COLORS['primary']
        )
    
    # Add bin count annotations 
    for i, (x, y) in enumerate(zip(bin_confidences[valid_bins], bin_accuracies[valid_bins])):
        bin_idx = np.where(valid_bins)[0][i]
        count = bin_counts[bin_idx]
        if count > 0:
            ax.annotate(
                f"n={int(count)}",
                (x, y),
                textcoords="offset points",
                xytext=(0, -15),
                ha='center',
                fontsize=8
            )
    
    # Configure the plot
    ax.set_xlabel('Predicted Probability')
    ax.set_ylabel('Observed Frequency')
    ax.set_title(f'{title}\nExpected Calibration Error (ECE): {ece:.4f}')
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(loc='lower right')
    
    # Add ECE and sample count to the plot
    ax.text(
        0.05, 0.95, 
        f'ECE: {ece:.4f}\nSamples: {len(confidences):,}',
        transform=ax.transAxes, 
        fontsize=10,
        verticalalignment='top', 
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
    )
    
    return fig, ax, ece

def plot_calibration_analysis(
    y_true: List[str],
    y_prob: List[Dict[str, float]],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    n_bins: int = 10,
    group_key: Optional[str] = None,
    group_name: Optional[str] = None,
    lines: Optional[List[str]] = None,
    destinations: Optional[List[str]] = None,
    show_plot: bool = False
) -> Dict[str, str]:
    """
    Generate and save unified calibration analysis focused on track prediction accuracy.
    
    Args:
        y_true: List of actual track assignments
        y_prob: List of dictionaries mapping tracks to probabilities
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        n_bins: Number of bins for the calibration curves
        group_key: Optional field name for grouping (e.g. 'line', 'destination')
        group_name: Optional group value for filtering (e.g. 'NEC', 'Trenton')
        lines: Optional list of train lines for each sample
        destinations: Optional list of destinations for each sample
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    group_str = f"_{group_key}_{group_name}" if group_key and group_name else ""
    
    # Create figure with single calibration chart and confidence histogram
    fig = plt.figure(figsize=(14, 10))
    
    # Create grid layout: main calibration chart on top, histogram on bottom
    gs = plt.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.3)
    
    # Setup subplots
    ax_main = fig.add_subplot(gs[0])    # Main calibration chart
    ax_hist = fig.add_subplot(gs[1])    # Confidence distribution histogram
    
    # Extract all track predictions for proper calibration analysis
    confidences = []
    correct_predictions = []
    
    for true_track, prob_dict in zip(y_true, y_prob):
        # For each sample, look at all track predictions
        for predicted_track, confidence in prob_dict.items():
            confidences.append(confidence)
            # 1 if this prediction was correct, 0 if incorrect
            correct_predictions.append(1 if predicted_track == true_track else 0)
    
    confidences = np.array(confidences)
    correct_predictions = np.array(correct_predictions)
    
    logger.info(f"Created track prediction calibration data with {len(confidences)} predictions")
    
    # Calculate calibration metrics
    ece, bin_confidences, bin_accuracies, bin_counts = calculate_ece(
        confidences, correct_predictions, n_bins=n_bins
    )
    
    # Calculate Brier score for additional context
    brier_score = brier_score_loss(correct_predictions, confidences)
    
    # Main calibration plot
    # Plot perfect calibration reference line
    ax_main.plot([0, 1], [0, 1], 'r--', linewidth=2, label='Perfect Calibration', alpha=0.8)
    
    # Plot model calibration curve
    valid_bins = bin_counts > 0
    if np.sum(valid_bins) > 0:
        ax_main.plot(
            bin_confidences[valid_bins], 
            bin_accuracies[valid_bins], 
            's-', color=COLORS['primary'], linewidth=3, markersize=8, 
            label='Model Calibration', markerfacecolor='white', markeredgewidth=2
        )
        
        # Fill area to show calibration error
        ax_main.fill_between(
            bin_confidences[valid_bins], 
            bin_confidences[valid_bins], 
            bin_accuracies[valid_bins], 
            alpha=0.15, color=COLORS['primary'], label='Calibration Error'
        )
        
        # Add sample count annotations for each bin
        for i, (x, y) in enumerate(zip(bin_confidences[valid_bins], bin_accuracies[valid_bins])):
            bin_idx = np.where(valid_bins)[0][i]
            count = bin_counts[bin_idx]
            if count > 5:  # Show annotation if reasonable sample size
                ax_main.annotate(
                    f"{int(count)}",
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 12),
                    ha='center',
                    fontsize=9,
                    fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray')
                )
    
    # Configure main calibration plot
    group_title = f" - {group_name} {group_key}" if group_key and group_name else ""
    ax_main.set_title(
        f'Track Prediction Calibration{group_title}', 
        fontsize=14, fontweight='bold', pad=20
    )
    ax_main.set_xlabel('Model Confidence (Predicted Probability)', fontsize=12)
    ax_main.set_ylabel('Actual Accuracy (Observed Frequency)', fontsize=12)
    
    # Add comprehensive metrics text box
    metrics_text = (
        f'Expected Calibration Error (ECE): {ece:.4f}\n'
        f'Brier Score: {brier_score:.4f}\n'
        f'Total Predictions: {len(confidences):,}\n'
        f'Mean Confidence: {np.mean(confidences):.3f}'
    )
    ax_main.text(
        0.02, 0.98, metrics_text,
        transform=ax_main.transAxes, 
        fontsize=11,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.9, edgecolor='darkblue')
    )
    
    # Add interpretation guide
    interpretation_text = (
        'How to read this chart:\n'
        '• X-axis: Model confidence (0-100%)\n'
        '• Y-axis: Actual accuracy at that confidence\n'
        '• Perfect line: Confidence = Accuracy\n'
        '• Below line: Model overconfident\n'
        '• Above line: Model underconfident'
    )
    ax_main.text(
        0.98, 0.02, interpretation_text,
        transform=ax_main.transAxes, 
        fontsize=10,
        verticalalignment='bottom',
        horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9, edgecolor='orange')
    )
    
    ax_main.set_xlim([0, 1])
    ax_main.set_ylim([0, 1])
    ax_main.grid(True, linestyle='--', alpha=0.4)
    ax_main.legend(loc='center right', fontsize=11)
    
    # Confidence distribution histogram - separate correct vs incorrect predictions
    correct_confidences = confidences[correct_predictions == 1]
    incorrect_confidences = confidences[correct_predictions == 0]
    
    # Plot histograms
    ax_hist.hist(
        incorrect_confidences, 
        bins=30, range=(0, 1), 
        alpha=0.6, color='red', label=f'Incorrect (n={len(incorrect_confidences):,})',
        edgecolor='darkred', linewidth=0.5
    )
    ax_hist.hist(
        correct_confidences, 
        bins=30, range=(0, 1), 
        alpha=0.6, color='green', label=f'Correct (n={len(correct_confidences):,})',
        edgecolor='darkgreen', linewidth=0.5
    )
    
    # Add vertical line for mean confidence
    mean_conf = np.mean(confidences)
    ax_hist.axvline(mean_conf, color='black', linestyle='--', linewidth=2, 
                   label=f'Overall Mean: {mean_conf:.3f}')
    
    # Configure histogram
    ax_hist.set_title('Distribution of Model Confidence Scores', fontsize=12, fontweight='bold')
    ax_hist.set_xlabel('Model Confidence', fontsize=11)
    ax_hist.set_ylabel('Count', fontsize=11)
    ax_hist.legend(fontsize=10)
    ax_hist.grid(True, linestyle='--', alpha=0.3)
    
    # Set main title for the entire figure
    fig.suptitle(
        f'Model Calibration Analysis{group_title} (v{model_version})',
        fontsize=16, fontweight='bold', y=0.95
    )
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    
    # Save the figure
    filename = f"calibration_analysis{group_str}{timestamp_str}"
    saved_files = save_figure(fig, filename, output_dir)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    # Save calibration summary to text file
    summary_file = Path(output_dir) / f"calibration_summary{group_str}{timestamp_str}.txt"
    with open(summary_file, 'w') as f:
        f.write(f"Track Prediction Calibration Summary{group_title} (v{model_version})\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Generated: {timestamp if timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("CALIBRATION METRICS:\n")
        f.write(f"  Expected Calibration Error (ECE): {ece:.6f}\n")
        f.write(f"  Brier Score: {brier_score:.6f}\n")
        f.write(f"  Total Predictions: {len(confidences):,}\n")
        f.write(f"  Mean Confidence: {np.mean(confidences):.4f}\n")
        f.write(f"  Median Confidence: {np.median(confidences):.4f}\n")
        f.write(f"  Confidence Std Dev: {np.std(confidences):.4f}\n\n")
        
        f.write("INTERPRETATION:\n")
        f.write("  • ECE measures calibration quality (lower is better, 0 = perfect)\n")
        f.write("  • Brier Score measures overall prediction quality (lower is better)\n")
        f.write("  • Well-calibrated models have ECE < 0.1\n\n")
        
        f.write("BIN DETAILS:\n")
        for i in range(len(bin_confidences)):
            if bin_counts[i] > 0:
                f.write(f"  Bin {i+1}: Confidence {bin_confidences[i]:.3f}, "
                       f"Accuracy {bin_accuracies[i]:.3f}, Count {int(bin_counts[i])}\n")
    
    saved_files['summary'] = str(summary_file)
    
    return saved_files

def plot_all_calibration_curves(
    y_true: List[str],
    y_prob: List[Dict[str, float]],
    lines: List[str],
    destinations: List[str],
    output_dir: Union[str, Path] = Path("training_artifacts"),
    model_version: str = "1.0.0",
    timestamp: Optional[str] = None,
    min_samples: int = 30,
    show_plot: bool = False
) -> Dict[str, Dict[str, str]]:
    """
    Generate calibration curves for overall model, per-line, and per-destination.
    
    Args:
        y_true: List of actual track assignments
        y_prob: List of dictionaries mapping tracks to probabilities
        lines: List of train lines for each sample
        destinations: List of destinations for each sample
        output_dir: Directory to save plots
        model_version: Model version identifier
        timestamp: Timestamp for file naming
        min_samples: Minimum number of samples required for a group
        show_plot: Whether to display plots in addition to saving them
        
    Returns:
        Dictionary of saved file paths
    """
    timestamp_str = f"_{timestamp}" if timestamp else ""
    saved_files = {}
    
    # Create output directory and subdirectories
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Overall calibration curve
    logger.info("Generating overall calibration analysis")
    overall_files = plot_calibration_analysis(
        y_true, y_prob, output_dir, model_version, timestamp,
        lines=lines, destinations=destinations, show_plot=show_plot
    )
    saved_files['overall'] = overall_files
    
    # 2. Create subdirectories for line and destination calibration curves
    lines_dir = create_subdirectory(output_dir, "lines")
    destinations_dir = create_subdirectory(output_dir, "destinations")
    
    # 3. Per-line calibration curves
    logger.info("Generating per-line calibration analyses")
    unique_lines = sorted(set(lines))
    saved_files['lines'] = {}
    
    for line in unique_lines:
        # Filter data by line
        line_indices = [i for i, l in enumerate(lines) if l == line]
        
        if len(line_indices) < min_samples:
            logger.info(f"Skipping calibration analysis for line '{line}': insufficient samples ({len(line_indices)})")
            
            # Create a placeholder file explaining why we skipped this line
            line_safe_name = sanitize_string(line)
            line_subdir = create_subdirectory(lines_dir, line_safe_name)
            placeholder_file = line_subdir / f"insufficient_samples_{timestamp_str}.txt"
            
            with open(placeholder_file, 'w') as f:
                f.write(f"Insufficient samples to generate calibration analysis for line: {line}\n")
                f.write(f"Found {len(line_indices)} samples, minimum required: {min_samples}\n")
            
            continue
        
        # Filter data for this line
        line_y_true = [y_true[i] for i in line_indices]
        line_y_prob = [y_prob[i] for i in line_indices]
        line_destinations = [destinations[i] for i in line_indices]
        
        # Create a subdirectory for this line
        line_safe_name = sanitize_string(line)
        line_subdir = create_subdirectory(lines_dir, line_safe_name)
        
        logger.info(f"Generating calibration analysis for line '{line}' with {len(line_indices)} samples")
        line_files = plot_calibration_analysis(
            line_y_true, line_y_prob, line_subdir, model_version, timestamp,
            group_key="line", group_name=line,
            destinations=line_destinations, show_plot=show_plot
        )
        saved_files['lines'][line] = line_files
    
    # Create an index file for lines
    if saved_files['lines']:
        lines_index_file = lines_dir / f"lines_calibration_index{timestamp_str}.txt"
        with open(lines_index_file, 'w') as f:
            f.write(f"Per-Line Calibration Analysis Index (v{model_version})\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Generated: {timestamp if timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Available Line Analyses:\n")
            
            for line in sorted(saved_files['lines'].keys()):
                line_sample_count = len([i for i, l in enumerate(lines) if l == line])
                f.write(f"  - {line}: {line_sample_count} samples\n")
    
    # 4. Per-destination calibration curves
    logger.info("Generating per-destination calibration analyses")
    unique_destinations = sorted(set(destinations))
    saved_files['destinations'] = {}
    
    for dest in unique_destinations:
        # Filter data by destination
        dest_indices = [i for i, d in enumerate(destinations) if d == dest]
        
        if len(dest_indices) < min_samples:
            logger.info(f"Skipping calibration analysis for destination '{dest}': insufficient samples ({len(dest_indices)})")
            continue
        
        # Filter data for this destination
        dest_y_true = [y_true[i] for i in dest_indices]
        dest_y_prob = [y_prob[i] for i in dest_indices]
        dest_lines = [lines[i] for i in dest_indices]
        
        # Create a subdirectory for this destination
        dest_safe_name = sanitize_string(dest)
        dest_subdir = create_subdirectory(destinations_dir, dest_safe_name)
        
        logger.info(f"Generating calibration analysis for destination '{dest}' with {len(dest_indices)} samples")
        dest_files = plot_calibration_analysis(
            dest_y_true, dest_y_prob, dest_subdir, model_version, timestamp,
            group_key="destination", group_name=dest,
            lines=dest_lines, show_plot=show_plot
        )
        saved_files['destinations'][dest] = dest_files
    
    # Create a summary file comparing ECE values across lines and destinations
    summary_file = output_dir / f"calibration_ece_summary{timestamp_str}.txt"
    with open(summary_file, 'w') as f:
        f.write(f"ECE Comparison Summary (v{model_version})\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Generated: {timestamp if timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Extract ECE values from summaries
        # global_ece = ... # Need to parse from summary file
        
        f.write("Line ECE values (sorted by ECE):\n")
        line_eces = []
        for line, files in saved_files.get('lines', {}).items():
            if 'summary' in files:
                with open(files['summary'], 'r') as sf:
                    summary_content = sf.read()
                    # Extract ECE value from the new format
                    import re
                    match = re.search(r"Expected Calibration Error \(ECE\): ([\d.]+)", summary_content)
                    if match:
                        ece = float(match.group(1))
                        line_sample_count = len([i for i, l in enumerate(lines) if l == line])
                        line_eces.append((line, ece, line_sample_count))
        
        # Sort by ECE value (ascending)
        for line, ece, count in sorted(line_eces, key=lambda x: x[1]):
            f.write(f"  - {line}: {ece:.6f} (n={count})\n")
    
    saved_files['summary'] = str(summary_file)
    
    # Create a bar chart comparing ECE values across lines
    if line_eces:
        fig, ax = setup_plot(figsize=(14, 8))
        
        sorted_lines = [x[0] for x in sorted(line_eces, key=lambda x: x[1])]
        sorted_eces = [x[1] for x in sorted(line_eces, key=lambda x: x[1])]
        sample_counts = [x[2] for x in sorted(line_eces, key=lambda x: x[1])]
        
        # Plot bars
        bars = ax.bar(sorted_lines, sorted_eces, color=COLORS['primary'], alpha=0.7)
        
        # Add count annotations
        for i, (count, bar) in enumerate(zip(sample_counts, bars)):
            height = bar.get_height()
            ax.annotate(
                f'n={count}',
                (bar.get_x() + bar.get_width() / 2, height + 0.005),
                ha='center',
                va='bottom',
                fontsize=9,
                rotation=0
            )
        
        # Add titles and labels
        ax.set_title(f'Calibration Quality by Line (v{model_version})\nLower ECE is Better')
        ax.set_xlabel('Train Line')
        ax.set_ylabel('Expected Calibration Error (ECE)')
        ax.set_ylim(0, max(sorted_eces) * 1.2)  # Add 20% headroom
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        ax.set_xticklabels(sorted_lines, rotation=45, ha='right')
        
        # Save the figure
        ece_chart_file = output_dir / f"calibration_ece_comparison{timestamp_str}.png"
        plt.tight_layout()
        plt.savefig(ece_chart_file, dpi=300, bbox_inches='tight')
        if not show_plot:
            plt.close(fig)
        
        saved_files['ece_chart'] = str(ece_chart_file)
    
    return saved_files