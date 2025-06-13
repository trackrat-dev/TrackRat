"""
Visualization module for TrackCast model insights and evaluation metrics.
"""

from .calibration import plot_all_calibration_curves, plot_calibration_curve
from .confusion import (
    plot_all_confusion_matrices,
    plot_confusion_matrix,
    plot_confusion_matrix_comparison,
)
from .feature_importance import (
    plot_feature_importance,
    plot_shap_summary,
    plot_track_specific_feature_importance,
)
from .training import plot_learning_curves
from .utils import save_figure, setup_plot
