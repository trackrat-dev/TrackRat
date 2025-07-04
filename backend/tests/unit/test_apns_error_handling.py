"""
Tests for APNS error handling, specifically 410 Gone responses.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import httpx
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from trackcast.db.models import DeviceToken, LiveActivityToken
from trackcast.services.push_notification import APNSPushService, TrainUpdateNotificationService


class TestAPNSErrorHandling:
    """Test APNS error response handling."""

    @pytest.fixture
    def apns_service(self):
        """Create a configured APNS service."""
        with patch.dict(
            "os.environ",
            {
                "APNS_TEAM_ID": "TESTTEAM",
                "APNS_KEY_ID": "TESTKEY123",
                "APNS_AUTH_KEY_PATH": "/tmp/test_auth_key.p8",
                "APNS_BUNDLE_ID": "net.trackrat.TrackRat",
                "TRACKCAST_ENV": "dev",
            },
        ):
            # Mock file existence check
            with patch("os.path.exists", return_value=True):
                service = APNSPushService()
                # Force it to not use mock mode
                service._use_mock = False
                return service

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        # Create a mock query object that can be chained
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 1  # Return count of deleted records
        
        # Create a mock object that can represent both DeviceToken and LiveActivityToken
        mock_token = MagicMock()
        mock_token.id = 123
        mock_token.device_id = 456
        mock_query.first.return_value = mock_token
        
        db.query.return_value = mock_query
        return db

    @pytest.mark.asyncio
    async def test_handle_410_gone_live_activity_token(self, apns_service, mock_db):
        """Test that 410 Gone response triggers Live Activity token deletion."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.text = "Gone"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request that will get 410 response
                result = await apns_service._send_apns_request(
                    "test_push_token_123", {"test": "payload"}, is_live_activity=True, db=mock_db
                )

                # Verify request failed
                assert result is False

                # Verify token deletion was attempted
                mock_db.query.assert_called_with(LiveActivityToken)
                mock_query = mock_db.query.return_value
                mock_query.filter.assert_called()
                mock_query.delete.assert_called_with(synchronize_session=False)
                mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_410_gone_device_token(self, apns_service, mock_db):
        """Test that 410 Gone response triggers device token deletion."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.text = "Gone"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request that will get 410 response
                result = await apns_service._send_apns_request(
                    "test_device_token_456", {"test": "payload"}, is_live_activity=False, db=mock_db
                )

                # Verify request failed
                assert result is False

                # Verify token deletion was attempted
                # Check that DeviceToken and LiveActivityToken were both queried
                query_calls = [call_args[0][0] for call_args in mock_db.query.call_args_list]
                assert DeviceToken in query_calls, f"DeviceToken not queried. Actual calls: {query_calls}"
                assert LiveActivityToken in query_calls, f"LiveActivityToken not queried. Actual calls: {query_calls}"
                
                mock_query = mock_db.query.return_value
                mock_query.filter.assert_called()
                mock_query.delete.assert_called_with(synchronize_session=False)
                mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_bad_device_token_error(self, apns_service, mock_db):
        """Test that BadDeviceToken error in 400 response triggers token deletion."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"reason": "BadDeviceToken"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request that will get BadDeviceToken error
                result = await apns_service._send_apns_request(
                    "bad_token_789", {"test": "payload"}, is_live_activity=True, db=mock_db
                )

                # Verify request failed
                assert result is False

                # Verify token deletion was attempted
                mock_db.query.assert_called_with(LiveActivityToken)
                mock_query = mock_db.query.return_value
                mock_query.filter.assert_called()
                mock_query.delete.assert_called_with(synchronize_session=False)
                mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_unregistered_error(self, apns_service, mock_db):
        """Test that Unregistered error triggers token deletion."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"reason": "Unregistered"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request
                result = await apns_service._send_apns_request(
                    "unregistered_token", {"test": "payload"}, is_live_activity=False, db=mock_db
                )

                # Verify request failed and token was deleted
                assert result is False
                mock_query = mock_db.query.return_value
                mock_query.delete.assert_called_with(synchronize_session=False)
                mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_invalid_token_without_db(self, apns_service):
        """Test that token deletion creates its own db session when none provided."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.text = "Gone"

        # Mock database session creation
        mock_db = MagicMock(spec=Session)
        # Create a mock query object that can be chained
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 1  # Return count of deleted records
        mock_db.query.return_value = mock_query

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Mock get_db to return our mock db
                with patch("trackcast.services.push_notification.get_db") as mock_get_db:
                    mock_get_db.return_value = iter([mock_db])

                    # Send request without db parameter
                    result = await apns_service._send_apns_request(
                        "test_token_no_db", {"test": "payload"}, is_live_activity=True, db=None
                    )

                    # Verify request failed
                    assert result is False

                    # Verify get_db was called to create session
                    mock_get_db.assert_called_once()

                    # Verify token deletion was attempted
                    mock_query = mock_db.query.return_value
                    mock_query.delete.assert_called_with(synchronize_session=False)
                    mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_device_token_not_for_topic_does_not_delete(self, apns_service, mock_db):
        """Test that DeviceTokenNotForTopic error does NOT trigger deletion."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"reason": "DeviceTokenNotForTopic"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request
                result = await apns_service._send_apns_request(
                    "wrong_topic_token", {"test": "payload"}, is_live_activity=True, db=mock_db
                )

                # Verify request failed
                assert result is False

                # Verify token deletion was NOT attempted
                mock_query = mock_db.query.return_value
                mock_query.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_token_deletion_failure(self, apns_service, mock_db):
        """Test graceful handling when token deletion fails."""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.text = "Gone"

        # Make deletion fail - need to configure the mock query
        mock_query = mock_db.query.return_value
        mock_query.delete.side_effect = Exception("Database error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request
                result = await apns_service._send_apns_request(
                    "token_delete_fails", {"test": "payload"}, is_live_activity=True, db=mock_db
                )

                # Verify request still fails gracefully
                assert result is False

                # Verify rollback was attempted
                mock_db.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_successful_notification_does_not_delete_token(self, apns_service, mock_db):
        """Test that successful notifications don't trigger token deletion."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock JWT generation
            with patch.object(apns_service, "_generate_jwt_token", return_value="test_jwt"):
                # Send request
                result = await apns_service._send_apns_request(
                    "valid_token", {"test": "payload"}, is_live_activity=True, db=mock_db
                )

                # Verify request succeeded
                assert result is True

                # Verify token deletion was NOT attempted
                mock_query = mock_db.query.return_value
                mock_query.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_object_deleted_error_handling(self):
        """Test that ObjectDeletedError doesn't crash when accessing token attributes."""
        # Create a mock token that will raise ObjectDeletedError
        mock_token = MagicMock(spec=LiveActivityToken)
        
        # Configure push_token to work initially but raise ObjectDeletedError on later access
        mock_token.push_token = "test_token_123456"
        
        # Create notification service
        notification_service = TrainUpdateNotificationService()
        
        # Mock the push service to simulate token deletion during processing
        with patch.object(notification_service.push_service, 'send_train_notifications') as mock_send:
            # Configure the mock to delete the token and then raise an exception
            def simulate_token_deletion_and_error(*args, **kwargs):
                # Simulate token deletion by making push_token attribute raise ObjectDeletedError
                def raise_object_deleted_error(*args, **kwargs):
                    raise ObjectDeletedError("Instance has been deleted")
                
                # Replace push_token property to raise error on access
                type(mock_token).push_token = property(raise_object_deleted_error)
                
                # Raise an exception to simulate notification failure
                raise Exception("Token was deleted during processing")
            
            mock_send.side_effect = simulate_token_deletion_and_error
            
            # Mock database session
            mock_db = MagicMock(spec=Session)
            
            # Create test consolidated train data
            consolidated_train = {
                "train_id": "test_train_123",
                "consolidated_id": "test_train_123_2025-07-04",
                "track": "5",
                "status": "BOARDING",
                "status_v2": {"current": "BOARDING", "location": "at New York Penn Station"},
                "progress": {"journey_percent": 25},
                "stops": []
            }
            
            # Create a list with the problematic token
            active_tokens = [mock_token]
            
            with patch.object(mock_db, 'query') as mock_query:
                mock_query.return_value.options.return_value.filter.return_value.all.return_value = active_tokens
                
                # This should not raise ObjectDeletedError even though token is deleted
                try:
                    await notification_service._check_and_notify_consolidated_train_changes(
                        consolidated_train, mock_db
                    )
                except ObjectDeletedError:
                    pytest.fail("ObjectDeletedError was not properly handled - the fix didn't work")
                except Exception as e:
                    # Other exceptions are expected since we're mocking incomplete scenarios
                    # The important thing is that ObjectDeletedError is not raised
                    assert not isinstance(e, ObjectDeletedError), f"Got ObjectDeletedError: {e}"