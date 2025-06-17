"""
Tests for CLI filtering functionality.

This module tests the enhanced CLI commands that support filtering
by train ID, time range, and future trains for prediction generation and clearing.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from trackcast.cli import generate_predictions


class TestCLIGeneratePredictions:
    """Test the enhanced generate_predictions CLI command."""

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_generate_predictions_basic(self, mock_get_db_session, mock_prediction_service_class):
        """Test basic prediction generation without filters."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 5})
        
        # Test CLI command
        runner = CliRunner()
        result = runner.invoke(generate_predictions, [])
        
        assert result.exit_code == 0
        mock_service.run_prediction.assert_called_once_with(
            train_id=None,
            time_range=None,
            future_only=False
        )

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_generate_predictions_with_train_id(self, mock_get_db_session, mock_prediction_service_class):
        """Test prediction generation with train ID filter."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 1})
        
        # Test CLI command with train ID
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--train-id', '7001'])
        
        assert result.exit_code == 0
        mock_service.run_prediction.assert_called_once_with(
            train_id='7001',
            time_range=None,
            future_only=False
        )

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_generate_predictions_with_time_range(self, mock_get_db_session, mock_prediction_service_class):
        """Test prediction generation with time range filter."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 3})
        
        # Test CLI command with time range
        runner = CliRunner()
        result = runner.invoke(generate_predictions, [
            '--time-range', '2024-01-01T10:00:00', '2024-01-01T18:00:00'
        ])
        
        assert result.exit_code == 0
        # Verify the time range was passed (as datetime objects)
        call_args = mock_service.run_prediction.call_args
        assert call_args[1]['train_id'] is None
        assert call_args[1]['time_range'] is not None
        assert len(call_args[1]['time_range']) == 2
        assert call_args[1]['future_only'] is False

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_generate_predictions_with_future_flag(self, mock_get_db_session, mock_prediction_service_class):
        """Test prediction generation with future flag."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 10})
        
        # Test CLI command with future flag
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--future'])
        
        assert result.exit_code == 0
        mock_service.run_prediction.assert_called_once_with(
            train_id=None,
            time_range=None,
            future_only=True
        )

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_clear_predictions_basic(self, mock_get_db_session, mock_prediction_service_class):
        """Test basic prediction clearing without filters."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.clear_predictions.return_value = (True, {"predictions_deleted": 15})
        
        # Test CLI command
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--clear'])
        
        assert result.exit_code == 0
        mock_service.clear_predictions.assert_called_once_with(
            train_id=None,
            time_range=None,
            future_only=False
        )

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_clear_predictions_with_train_id(self, mock_get_db_session, mock_prediction_service_class):
        """Test prediction clearing with train ID filter."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.clear_predictions.return_value = (True, {"predictions_deleted": 1})
        
        # Test CLI command with clear and train ID
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--clear', '--train-id', '7001'])
        
        assert result.exit_code == 0
        mock_service.clear_predictions.assert_called_once_with(
            train_id='7001',
            time_range=None,
            future_only=False
        )

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_clear_predictions_with_future_flag(self, mock_get_db_session, mock_prediction_service_class):
        """Test prediction clearing with future flag."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.clear_predictions.return_value = (True, {"predictions_deleted": 8})
        
        # Test CLI command with clear and future flag
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--clear', '--future'])
        
        assert result.exit_code == 0
        mock_service.clear_predictions.assert_called_once_with(
            train_id=None,
            time_range=None,
            future_only=True
        )

    def test_multiple_filters_error(self):
        """Test that using multiple filters results in an error."""
        runner = CliRunner()
        
        # Test train-id + future
        result = runner.invoke(generate_predictions, ['--train-id', '7001', '--future'])
        assert result.exit_code == 1
        assert "Cannot use multiple filtering options" in result.output
        
        # Test train-id + time-range
        result = runner.invoke(generate_predictions, [
            '--train-id', '7001',
            '--time-range', '2024-01-01T10:00:00', '2024-01-01T18:00:00'
        ])
        assert result.exit_code == 1
        assert "Cannot use multiple filtering options" in result.output
        
        # Test time-range + future
        result = runner.invoke(generate_predictions, [
            '--time-range', '2024-01-01T10:00:00', '2024-01-01T18:00:00',
            '--future'
        ])
        assert result.exit_code == 1
        assert "Cannot use multiple filtering options" in result.output

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_service_failure_handling(self, mock_get_db_session, mock_prediction_service_class):
        """Test handling of service failures."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (False, {"error": "Model not found"})
        
        # Test CLI command when service fails
        runner = CliRunner()
        result = runner.invoke(generate_predictions, [])
        
        assert result.exit_code == 1

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_exception_handling(self, mock_get_db_session, mock_prediction_service_class):
        """Test handling of exceptions."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.side_effect = Exception("Database connection failed")
        
        # Test CLI command when exception occurs
        runner = CliRunner()
        result = runner.invoke(generate_predictions, [])
        
        assert result.exit_code == 1

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_session_cleanup(self, mock_get_db_session, mock_prediction_service_class):
        """Test that database session is properly cleaned up."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 5})
        
        # Test CLI command
        runner = CliRunner()
        runner.invoke(generate_predictions, [])
        
        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch('trackcast.cli.PredictionService')
    @patch('trackcast.cli.get_db_session')
    def test_session_cleanup_on_exception(self, mock_get_db_session, mock_prediction_service_class):
        """Test that database session is cleaned up even when exception occurs."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_prediction_service_class.return_value = mock_service
        mock_service.run_prediction.side_effect = Exception("Test exception")
        
        # Test CLI command with exception
        runner = CliRunner()
        runner.invoke(generate_predictions, [])
        
        # Verify session was still closed
        mock_session.close.assert_called_once()


class TestCLIHelpText:
    """Test help text and option descriptions."""

    def test_help_text_includes_new_options(self):
        """Test that help text includes all new options."""
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--help'])
        
        assert result.exit_code == 0
        help_text = result.output
        
        # Check that all new options are documented
        assert '--clear' in help_text
        assert '--train-id' in help_text
        assert '--time-range' in help_text
        assert '--future' in help_text
        
        # Check descriptions
        assert 'Clear predictions instead of generating them' in help_text
        assert 'Filter to a specific train ID' in help_text
        assert 'Filter to trains within a time range' in help_text
        assert 'Filter to trains with future departure times' in help_text

    def test_time_range_format_documented(self):
        """Test that time range format is documented."""
        runner = CliRunner()
        result = runner.invoke(generate_predictions, ['--help'])
        
        help_text = result.output
        assert 'start_time end_time' in help_text