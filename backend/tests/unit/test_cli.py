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
    
    @patch("trackcast.models.training.train_new_model")
    def test_train_model_command(self, mock_train):
        """Test the train-model command."""
        mock_train.return_value = (True, {"accuracy": 0.85, "model_version": "1.0"})

        result = self.runner.invoke(cli, ["train-model"])
        assert result.exit_code == 0
        mock_train.assert_called_once()
