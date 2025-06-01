"""Integration tests for the scheduler service."""
import pytest
import time
from unittest.mock import patch, MagicMock

from trackcast.services.scheduler import SchedulerService


class TestSchedulerIntegration:
    """Integration tests for the scheduler service."""
    
    def test_scheduler_execution(self):
        """Test that scheduler properly executes tasks."""
        # Create mock services
        mock_data_service = MagicMock()
        mock_feature_service = MagicMock()
        mock_prediction_service = MagicMock()
        
        # Configure scheduler with short intervals for testing
        scheduler_config = {
            "data_collection_interval": 1,  # 1 second
            "feature_engineering_interval": 2,  # 2 seconds
            "prediction_interval": 3,  # 3 seconds
        }
        
        # Create scheduler service with mocked components
        scheduler = SchedulerService(
            config=scheduler_config,
            data_collection_service=mock_data_service,
            feature_engineering_service=mock_feature_service,
            prediction_service=mock_prediction_service
        )
        
        # Start scheduler in non-blocking mode
        scheduler.start(blocking=False)
        
        try:
            # Wait for all services to be called at least once
            max_wait = 5  # 5 seconds max wait time
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                data_called = mock_data_service.collect_and_store_data.call_count > 0
                feature_called = mock_feature_service.process_features.call_count > 0
                prediction_called = mock_prediction_service.generate_predictions.call_count > 0
                
                if data_called and feature_called and prediction_called:
                    break
                    
                time.sleep(0.1)
            
            # Verify all services were called
            assert mock_data_service.collect_and_store_data.call_count > 0
            assert mock_feature_service.process_features.call_count > 0
            assert mock_prediction_service.generate_predictions.call_count > 0
            
        finally:
            # Stop scheduler
            scheduler.stop()
    
    def test_scheduler_error_handling(self):
        """Test that scheduler handles service errors gracefully."""
        # Create mock services with the data service raising an exception
        mock_data_service = MagicMock()
        mock_data_service.collect_and_store_data.side_effect = Exception("API Error")
        
        mock_feature_service = MagicMock()
        mock_prediction_service = MagicMock()
        
        # Configure scheduler with short intervals for testing
        scheduler_config = {
            "data_collection_interval": 1,  # 1 second
            "feature_engineering_interval": 2,  # 2 seconds
            "prediction_interval": 3,  # 3 seconds
        }
        
        # Create scheduler service with mocked components
        scheduler = SchedulerService(
            config=scheduler_config,
            data_collection_service=mock_data_service,
            feature_engineering_service=mock_feature_service,
            prediction_service=mock_prediction_service
        )
        
        # Mock the logger
        with patch("trackcast.services.scheduler.logger") as mock_logger:
            # Start scheduler in non-blocking mode
            scheduler.start(blocking=False)
            
            try:
                # Wait for error to be logged
                max_wait = 2  # 2 seconds max wait time
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    if mock_logger.error.call_count > 0:
                        break
                    time.sleep(0.1)
                
                # Verify error was logged but scheduler didn't crash
                assert mock_logger.error.call_count > 0
                assert "Error in data collection task" in mock_logger.error.call_args[0][0]
                
                # Other services should still be called
                time.sleep(3)  # Wait for other services to be called
                assert mock_feature_service.process_features.call_count > 0
                
            finally:
                # Stop scheduler
                scheduler.stop()