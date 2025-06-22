"""Tests for the CLI module."""
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from trackcast.cli import main as cli


class TestCLI:
    """Tests for the CLI command-line interface."""
    
    def setup_method(self):
        """Set up test fixture."""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test the CLI help command."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
    
    @patch("trackcast.cli.create_engine")
    @patch("trackcast.cli.Base")
    def test_init_db_command(self, mock_base, mock_create_engine):
        """Test the init-db command."""
        # Capture the output including log messages
        result = self.runner.invoke(cli, ["init-db"], catch_exceptions=False)
        assert result.exit_code == 0
        # Check that the function was successful
        mock_create_engine.assert_called_once()
        mock_base.metadata.create_all.assert_called_once()
        # Since we're not actually capturing logs in tests, just check that the command completed successfully
        assert result.exception is None
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.DataCollectorService")
    def test_collect_data_command(self, mock_service_class, mock_get_db_session):
        """Test the collect-data command."""
        # Set up mock session and service
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_collection.return_value = (True, {
            "trains_total": 1,
            "trains_new": 1
        })

        # Run the command
        result = self.runner.invoke(cli, ["collect-data"], catch_exceptions=False)

        # Verify it was successful
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(mock_session)
        mock_service.run_collection.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    def test_process_features_command(self, mock_service_class, mock_get_db_session):
        """Test the process-features command."""
        # Set up mock session and service
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_pending_trains.return_value = (True, {
            "trains_processed": 1,
            "trains_succeeded": 1
        })

        # Run the command
        result = self.runner.invoke(cli, ["process-features"], catch_exceptions=False)

        # Verify it was successful
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(mock_session)
        mock_service.process_pending_trains.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.PredictionService")
    def test_generate_predictions_command(self, mock_service_class, mock_get_db_session):
        """Test the generate-predictions command."""
        # Set up mock session and service
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {
            "trains_processed": 1,
            "trains_predicted": 1
        })

        # Run the command
        result = self.runner.invoke(cli, ["generate-predictions"], catch_exceptions=False)

        # Verify it was successful
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(mock_session)
        mock_service.run_prediction.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.uvicorn")
    def test_start_api_command(self, mock_uvicorn):
        """Test the start-api command."""
        result = self.runner.invoke(cli, ["start-api"])
        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once()
    
    def test_train_model_command(self):
        """Test the train-model command."""
        # Skip test if training module dependencies aren't available (e.g., in CI)
        try:
            import matplotlib
            import seaborn
        except ImportError:
            pytest.skip("Training dependencies not available - skipping training test")
        
        with patch("trackcast.models.training.train_new_model") as mock_train:
            mock_train.return_value = (True, {"accuracy": 0.85, "model_version": "1.0"})

            result = self.runner.invoke(cli, ["train-model"])
            assert result.exit_code == 0
            mock_train.assert_called_once()


class TestRunPipelineCommand:
    """Tests for the run-pipeline command."""
    
    def setup_method(self):
        """Set up test fixture."""
        self.runner = CliRunner()
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_all_steps_default(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with all steps enabled (default behavior)."""
        # Mock all steps to succeed
        mock_collect.return_value = True
        mock_features.return_value = True
        mock_predictions.return_value = True
        
        result = self.runner.invoke(cli, ["run-pipeline"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # All steps should be called with default parameters
        mock_collect.assert_called_once()
        mock_features.assert_called_once_with(False, False)  # debug=False, regenerate=False
        mock_predictions.assert_called_once_with(False)  # regenerate=False
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_with_regenerate_flag(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with --regenerate flag."""
        # Mock all steps to succeed
        mock_collect.return_value = True
        mock_features.return_value = True
        mock_predictions.return_value = True
        
        result = self.runner.invoke(cli, ["run-pipeline", "--regenerate"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # All steps should be called with regenerate=True
        mock_collect.assert_called_once()
        mock_features.assert_called_once_with(False, True)  # debug=False, regenerate=True
        mock_predictions.assert_called_once_with(True)  # regenerate=True
        
        # Note: Logger output is not captured by CliRunner, only print statements
        # The regeneration logging happens via logger.info(), which isn't captured in result.output
        # We can verify the flag was passed correctly by checking the mock calls above
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_with_debug_and_regenerate(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with both --debug and --regenerate flags."""
        # Mock all steps to succeed
        mock_collect.return_value = True
        mock_features.return_value = True
        mock_predictions.return_value = True
        
        result = self.runner.invoke(cli, ["run-pipeline", "--debug", "--regenerate"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # All steps should be called with correct parameters
        mock_collect.assert_called_once()
        mock_features.assert_called_once_with(True, True)  # debug=True, regenerate=True
        mock_predictions.assert_called_once_with(True)  # regenerate=True
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_with_skip_flags(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with skip flags (should not call skipped steps)."""
        result = self.runner.invoke(cli, ["run-pipeline", "--skip-collection", "--skip-features"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # Only predictions step should be called
        mock_collect.assert_not_called()
        mock_features.assert_not_called()
        mock_predictions.assert_called_once_with(False)  # regenerate=False (default)
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_skip_with_regenerate(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with skip flags and regenerate."""
        # Mock remaining step to succeed
        mock_predictions.return_value = True
        
        result = self.runner.invoke(cli, ["run-pipeline", "--skip-collection", "--regenerate"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # Only features and predictions should be called with regenerate=True
        mock_collect.assert_not_called()
        mock_features.assert_called_once_with(False, True)  # debug=False, regenerate=True
        mock_predictions.assert_called_once_with(True)  # regenerate=True
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_dry_run_mode(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with --dry-run flag."""
        result = self.runner.invoke(cli, ["run-pipeline", "--dry-run"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # No actual steps should be executed in dry-run mode
        mock_collect.assert_not_called()
        mock_features.assert_not_called()
        mock_predictions.assert_not_called()
        
        # Note: Logger output is not captured by CliRunner, only print statements
        # The dry-run logging happens via logger.info(), which isn't captured in result.output
        # We can verify dry-run worked correctly by checking no mocks were called
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_dry_run_with_regenerate(self, mock_collect, mock_features, mock_predictions):
        """Test run-pipeline with --dry-run and --regenerate flags."""
        result = self.runner.invoke(cli, ["run-pipeline", "--dry-run", "--regenerate"])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # No actual steps should be executed in dry-run mode
        mock_collect.assert_not_called()
        mock_features.assert_not_called()
        mock_predictions.assert_not_called()
        
        # Note: Logger output is not captured by CliRunner, only print statements
        # We can verify both flags worked correctly by checking no mocks were called (dry-run)
        # and that the regenerate flag would have been passed if steps had executed
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_step_failure_stops_execution(self, mock_collect, mock_features, mock_predictions):
        """Test that pipeline stops execution when a step fails."""
        # Mock first step to fail
        mock_collect.return_value = False
        
        result = self.runner.invoke(cli, ["run-pipeline"])
        
        # Should exit with error code
        assert result.exit_code == 1
        
        # Only first step should be called
        mock_collect.assert_called_once()
        mock_features.assert_not_called()
        mock_predictions.assert_not_called()
        
        # Note: Logger output is not captured by CliRunner, only print statements
        # We can verify the failure by checking the exit code and mock calls
    
    @patch("trackcast.cli._execute_generate_predictions")
    @patch("trackcast.cli._execute_process_features")
    @patch("trackcast.cli._execute_collect_data")
    def test_run_pipeline_features_failure_with_regenerate(self, mock_collect, mock_features, mock_predictions):
        """Test pipeline failure at features step with regenerate flag."""
        # Mock collection to succeed, features to fail
        mock_collect.return_value = True
        mock_features.return_value = False
        
        result = self.runner.invoke(cli, ["run-pipeline", "--regenerate"])
        
        # Should exit with error code
        assert result.exit_code == 1
        
        # Collection and features should be called, predictions should not
        mock_collect.assert_called_once()
        mock_features.assert_called_once_with(False, True)  # debug=False, regenerate=True
        mock_predictions.assert_not_called()
        
        # Note: Logger output is not captured by CliRunner, only print statements
        # We can verify the regenerate flag was passed and the failure occurred by checking mock calls
    
    def test_run_pipeline_help_includes_regenerate_flag(self):
        """Test that run-pipeline help includes the --regenerate flag."""
        result = self.runner.invoke(cli, ["run-pipeline", "--help"])
        
        assert result.exit_code == 0
        assert "--regenerate" in result.output
        # Help text may be wrapped across lines, so check for key phrases
        assert "Clear and regenerate features/predictions for future" in result.output
        assert "trains (next 24h)" in result.output


class TestPipelineExecuteFunctions:
    """Tests for the internal _execute_* functions with regenerate parameter."""
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    def test_execute_process_features_default_mode(self, mock_service_class, mock_get_db_session):
        """Test _execute_process_features in default (incremental) mode."""
        from trackcast.cli import _execute_process_features
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_pending_trains.return_value = (True, {"trains_processed": 5})
        
        # Call function in default mode
        result = _execute_process_features(debug=False, regenerate=False)
        
        # Should succeed
        assert result is True
        
        # Should call incremental processing method
        mock_service.process_pending_trains.assert_called_once()
        mock_service.process_future_trains_with_regeneration.assert_not_called()
        
        # Session should be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    def test_execute_process_features_regenerate_mode(self, mock_service_class, mock_get_db_session):
        """Test _execute_process_features in regeneration mode."""
        from trackcast.cli import _execute_process_features
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_future_trains_with_regeneration.return_value = (True, {
            "trains_processed": 8,
            "features_cleared": 3,
            "regeneration": True
        })
        
        # Call function in regeneration mode
        result = _execute_process_features(debug=False, regenerate=True)
        
        # Should succeed
        assert result is True
        
        # Should call regeneration method
        mock_service.process_future_trains_with_regeneration.assert_called_once()
        mock_service.process_pending_trains.assert_not_called()
        
        # Session should be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    @patch("trackcast.cli.logging")
    def test_execute_process_features_debug_mode(self, mock_logging, mock_service_class, mock_get_db_session):
        """Test _execute_process_features with debug logging enabled."""
        from trackcast.cli import _execute_process_features
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_pending_trains.return_value = (True, {"trains_processed": 2})
        
        # Mock logging getLogger
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        # Call function with debug enabled
        result = _execute_process_features(debug=True, regenerate=False)
        
        # Should succeed
        assert result is True
        
        # Should set debug logging levels
        mock_logging.getLogger.assert_any_call("trackcast.features")
        mock_logging.getLogger.assert_any_call("trackcast.features.extractors")
        
        # Debug loggers should have their level set
        assert mock_logger.setLevel.call_count >= 2
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    def test_execute_process_features_failure(self, mock_service_class, mock_get_db_session):
        """Test _execute_process_features when service fails."""
        from trackcast.cli import _execute_process_features
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_pending_trains.return_value = (False, {"error": "Processing failed"})
        
        # Call function
        result = _execute_process_features(debug=False, regenerate=False)
        
        # Should fail
        assert result is False
        
        # Session should still be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.FeatureEngineeringService")
    def test_execute_process_features_exception(self, mock_service_class, mock_get_db_session):
        """Test _execute_process_features when an exception occurs."""
        from trackcast.cli import _execute_process_features
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_pending_trains.side_effect = Exception("Database error")
        
        # Call function
        result = _execute_process_features(debug=False, regenerate=False)
        
        # Should fail
        assert result is False
        
        # Session should still be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.PredictionService")
    def test_execute_generate_predictions_default_mode(self, mock_service_class, mock_get_db_session):
        """Test _execute_generate_predictions in default (incremental) mode."""
        from trackcast.cli import _execute_generate_predictions
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (True, {"trains_predicted": 12})
        
        # Call function in default mode
        result = _execute_generate_predictions(regenerate=False)
        
        # Should succeed
        assert result is True
        
        # Should call incremental processing method
        mock_service.run_prediction.assert_called_once()
        mock_service.run_prediction_with_regeneration.assert_not_called()
        
        # Session should be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.PredictionService")
    def test_execute_generate_predictions_regenerate_mode(self, mock_service_class, mock_get_db_session):
        """Test _execute_generate_predictions in regeneration mode."""
        from trackcast.cli import _execute_generate_predictions
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_prediction_with_regeneration.return_value = (True, {
            "trains_predicted": 15,
            "predictions_cleared": 8,
            "regeneration": True
        })
        
        # Call function in regeneration mode
        result = _execute_generate_predictions(regenerate=True)
        
        # Should succeed
        assert result is True
        
        # Should call regeneration method
        mock_service.run_prediction_with_regeneration.assert_called_once()
        mock_service.run_prediction.assert_not_called()
        
        # Session should be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.PredictionService")
    def test_execute_generate_predictions_failure(self, mock_service_class, mock_get_db_session):
        """Test _execute_generate_predictions when service fails."""
        from trackcast.cli import _execute_generate_predictions
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_prediction.return_value = (False, {"error": "Model loading failed"})
        
        # Call function
        result = _execute_generate_predictions(regenerate=False)
        
        # Should fail
        assert result is False
        
        # Session should still be closed
        mock_session.close.assert_called_once()
    
    @patch("trackcast.cli.get_db_session")
    @patch("trackcast.cli.PredictionService")
    def test_execute_generate_predictions_exception(self, mock_service_class, mock_get_db_session):
        """Test _execute_generate_predictions when an exception occurs."""
        from trackcast.cli import _execute_generate_predictions
        
        # Set up mocks
        mock_session = MagicMock()
        mock_get_db_session.return_value = mock_session
        
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.run_prediction_with_regeneration.side_effect = Exception("Model file not found")
        
        # Call function
        result = _execute_generate_predictions(regenerate=True)
        
        # Should fail
        assert result is False
        
        # Session should still be closed
        mock_session.close.assert_called_once()
