"""
Push notification service for sending APNS notifications to iOS devices.
"""

import asyncio
import json
import logging
import os
import ssl
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.db.connection import get_db
from trackcast.db.models import DeviceToken, LiveActivityToken, Train
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Alert types for Dynamic Island notifications."""

    TRACK_ASSIGNED = "track_assigned"
    BOARDING = "boarding"
    DEPARTED = "departed"
    APPROACHING = "approaching"
    DELAY_UPDATE = "delay_update"
    STATUS_CHANGE = "status_change"


class APNSPushService:
    """
    Apple Push Notification Service for sending push notifications and Live Activity updates.
    """

    def __init__(self):
        """Initialize the APNS push service."""
        # Determine APNS environment - separate from overall app environment
        apns_env = os.getenv("APNS_ENVIRONMENT", os.getenv("TRACKCAST_ENV", "dev"))
        if apns_env == "prod":
            self.apns_url = "https://api.push.apple.com"  # Production
        else:
            self.apns_url = "https://api.sandbox.push.apple.com"  # Development/Sandbox

        # APNS configuration from environment variables
        self.team_id = os.getenv("APNS_TEAM_ID")
        self.key_id = os.getenv("APNS_KEY_ID")
        self.auth_key_path = os.getenv("APNS_AUTH_KEY_PATH")
        self.bundle_id = os.getenv("APNS_BUNDLE_ID", "net.trackrat.TrackRat")

        # Certificate-based auth (alternative to auth key)
        self.cert_path = os.getenv("APNS_CERT_PATH")
        self.key_path = os.getenv("APNS_KEY_PATH")

        # JWT token cache
        self._jwt_token = None
        self._jwt_expires_at = 0

        # SSL context for APNS
        self.ssl_context = ssl.create_default_context()

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests

        # Validate configuration
        if not self._validate_config():
            logger.warning("APNS configuration incomplete - notifications will use mock mode")
            self._use_mock = True
        else:
            self._use_mock = False
            logger.info(
                f"APNS service initialized for {'production' if apns_env == 'prod' else 'sandbox'} environment"
            )

    async def send_train_notifications(
        self,
        live_activity_token: "LiveActivityToken",
        train_data: Dict[str, Any],
        alert_type: Optional[AlertType] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, bool]:
        """
        Send both Live Activity update and regular push notification for train changes.

        Args:
            live_activity_token: LiveActivityToken object with device relationship
            train_data: Current train data for the update
            alert_type: Optional alert type for notifications
            db: Database session for logging

        Returns:
            Dict with success status for each notification type
        """
        results = {"live_activity": False, "regular_notification": False}

        try:
            # Send Live Activity update
            await self._rate_limit()
            live_activity_payload = self._create_live_activity_payload(train_data, alert_type)
            results["live_activity"] = await self._send_apns_request(
                live_activity_token.push_token, live_activity_payload, is_live_activity=True
            )

            # Send regular push notification if there's an alert and device token
            if alert_type and live_activity_token.device:
                await self._rate_limit()
                regular_payload = self._create_regular_notification_payload(train_data, alert_type)
                results["regular_notification"] = await self._send_apns_request(
                    live_activity_token.device.device_token, regular_payload, is_live_activity=False
                )

            # Update database timestamps
            if db and (results["live_activity"] or results["regular_notification"]):
                live_activity_token.last_update_sent = get_eastern_now()
                if alert_type:
                    live_activity_token.last_notification_sent = get_eastern_now()
                    if live_activity_token.device:
                        live_activity_token.device.last_used = get_eastern_now()
                db.commit()

            logger.info(
                f"Notifications sent - Live Activity: {results['live_activity']}, Regular: {results['regular_notification']}"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to send train notifications: {str(e)}")
            return results

    async def send_live_activity_update(
        self,
        push_token: str,
        train_data: Dict[str, Any],
        alert_type: Optional[AlertType] = None,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Send a Live Activity update (backward compatibility method).

        Args:
            push_token: Live Activity push token
            train_data: Current train data for the update
            alert_type: Optional alert type for Dynamic Island expansion
            db: Database session for logging

        Returns:
            True if successful, False otherwise
        """
        # Find the Live Activity token by push token
        if db:
            from sqlalchemy.orm import joinedload

            token = (
                db.query(LiveActivityToken)
                .options(joinedload(LiveActivityToken.device))
                .filter(
                    LiveActivityToken.push_token == push_token, LiveActivityToken.is_active == True
                )
                .first()
            )

            if token:
                results = await self.send_train_notifications(token, train_data, alert_type, db)
                return results["live_activity"]

        # Fallback to basic Live Activity update
        try:
            await self._rate_limit()
            payload = self._create_live_activity_payload(train_data, alert_type)
            return await self._send_apns_request(push_token, payload, is_live_activity=True)
        except Exception as e:
            logger.error(f"Failed to send Live Activity update: {str(e)}")
            return False

    async def send_device_notification(
        self, device_token: str, title: str, body: str, custom_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a regular push notification to a device.

        Args:
            device_token: Device push token
            title: Notification title
            body: Notification body
            custom_data: Additional custom data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Rate limiting
            await self._rate_limit()

            # Prepare the APNS payload
            payload = {
                "aps": {"alert": {"title": title, "body": body}, "sound": "default", "badge": 1}
            }

            if custom_data:
                payload.update(custom_data)

            # Send the notification
            success = await self._send_apns_request(device_token, payload, is_live_activity=False)
            logger.info(f"Device notification sent successfully to {device_token[:8]}...")
            return success

        except Exception as e:
            logger.error(f"Failed to send device notification: {str(e)}")
            return False

    def _create_live_activity_payload(
        self, train_data: Dict[str, Any], alert_type: Optional[AlertType] = None
    ) -> Dict[str, Any]:
        """
        Create APNS payload for Live Activity update.

        Args:
            train_data: Current train data
            alert_type: Optional alert type for Dynamic Island

        Returns:
            APNS payload dictionary
        """
        # Base Live Activity payload
        payload = {
            "aps": {
                "timestamp": int(time.time()),
                "event": "update",
                "content-state": {
                    "trainNumber": train_data.get("train_id"),
                    "status": train_data.get("status_v2") or train_data.get("status"),
                    "track": train_data.get("track"),
                    "delayMinutes": train_data.get("delay_minutes", 0),
                    "currentLocation": train_data.get("current_location"),
                    "nextStop": train_data.get("next_stop_info"),
                    "journeyProgress": train_data.get("journey_percent", 0),
                    "lastUpdated": int(time.time()),
                },
            }
        }

        # Add alert for Dynamic Island expansion
        if alert_type:
            alert_config = self._get_alert_config(train_data, alert_type)
            if alert_config:
                payload["aps"]["alert"] = alert_config["alert"]
                payload["aps"]["sound"] = alert_config.get("sound", "default")
                payload["aps"]["relevance-score"] = alert_config.get("relevance_score", 1.0)

        return payload

    def _create_regular_notification_payload(
        self, train_data: Dict[str, Any], alert_type: AlertType
    ) -> Dict[str, Any]:
        """
        Create APNS payload for regular push notification.

        Args:
            train_data: Current train data
            alert_type: Alert type for notification

        Returns:
            APNS payload dictionary for regular notification
        """
        train_id = train_data.get("train_id", "")
        track = train_data.get("track", "")

        # Get alert text based on type
        alert_configs = {
            AlertType.TRACK_ASSIGNED: {
                "title": "Track Assigned! 🚋",
                "body": (
                    f"Train {train_id} → Track {track}"
                    if track
                    else f"Train {train_id} track assigned"
                ),
            },
            AlertType.BOARDING: {
                "title": "Time to Board! 🚆",
                "body": f"Train {train_id} is boarding" + (f" on Track {track}" if track else ""),
            },
            AlertType.DEPARTED: {
                "title": "Train Departed 🛤️",
                "body": f"Train {train_id} has left the station",
            },
            AlertType.APPROACHING: {
                "title": "Approaching Stop 🎯",
                "body": f"Train {train_id} is approaching your destination",
            },
            AlertType.DELAY_UPDATE: {
                "title": "Delay Update ⏰",
                "body": f"Train {train_id} is running behind schedule",
            },
            AlertType.STATUS_CHANGE: {
                "title": "Status Update 📢",
                "body": f"Train {train_id} status has changed",
            },
        }

        alert_config = alert_configs.get(
            alert_type, {"title": "Train Update", "body": f"Train {train_id} has been updated"}
        )

        return {
            "aps": {
                "alert": alert_config,
                "sound": "default",
                "badge": 1,
                "category": "TRAIN_UPDATE",
            },
            "train_data": {"train_id": train_id, "alert_type": alert_type.value, "track": track},
        }

    def _get_alert_config(
        self, train_data: Dict[str, Any], alert_type: AlertType
    ) -> Optional[Dict[str, Any]]:
        """
        Get alert configuration for Dynamic Island notifications.

        Args:
            train_data: Current train data
            alert_type: Type of alert

        Returns:
            Alert configuration dictionary
        """
        train_id = train_data.get("train_id", "")
        track = train_data.get("track", "")

        configs = {
            AlertType.TRACK_ASSIGNED: {
                "alert": {
                    "title": "Track Assigned! 🚋",
                    "body": f"Track {track} - Get Ready to Board",
                },
                "sound": "default",
                "relevance_score": 1.0,
            },
            AlertType.BOARDING: {
                "alert": {
                    "title": "Time to Board! 🚆",
                    "body": f"Track {track} - All Aboard!" if track else "Boarding Now!",
                },
                "sound": "default",
                "relevance_score": 1.0,
            },
            AlertType.DEPARTED: {
                "alert": {
                    "title": "Train Departed 🛤️",
                    "body": "Journey Started - Live Updates Active",
                },
                "sound": "default",
                "relevance_score": 0.8,
            },
            AlertType.APPROACHING: {
                "alert": {
                    "title": f"Approaching Destination 🎯",
                    "body": "Your stop is coming up!",
                },
                "sound": "default",
                "relevance_score": 0.9,
            },
            AlertType.DELAY_UPDATE: {
                "alert": {
                    "title": "Delay Update ⏰",
                    "body": f"Train {train_id} is running behind schedule",
                },
                "sound": "default",
                "relevance_score": 0.6,
            },
            AlertType.STATUS_CHANGE: {
                "alert": {"title": "Status Update 📢", "body": f"Train {train_id} status changed"},
                "sound": "default",
                "relevance_score": 0.5,
            },
        }

        return configs.get(alert_type)

    def _validate_config(self) -> bool:
        """Validate APNS configuration."""
        # Check for Auth Key configuration (preferred)
        if self.team_id and self.key_id and self.auth_key_path:
            if os.path.exists(self.auth_key_path):
                return True
            else:
                logger.error(f"APNS Auth Key file not found: {self.auth_key_path}")

        # Check for certificate-based configuration
        elif self.cert_path and self.key_path:
            if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
                return True
            else:
                logger.error(f"APNS certificate files not found: {self.cert_path}, {self.key_path}")

        # No valid configuration found
        logger.warning("APNS configuration incomplete. Need either:")
        logger.warning("1. APNS_TEAM_ID, APNS_KEY_ID, and APNS_AUTH_KEY_PATH (recommended)")
        logger.warning("2. APNS_CERT_PATH and APNS_KEY_PATH")
        return False

    def _generate_jwt_token(self) -> str:
        """Generate JWT token for APNS authentication."""
        now = int(time.time())

        # Check if we have a valid cached token
        if self._jwt_token and now < self._jwt_expires_at - 300:  # Refresh 5 minutes early
            return self._jwt_token

        if not (self.team_id and self.key_id and self.auth_key_path):
            raise ValueError("JWT authentication requires team_id, key_id, and auth_key_path")

        try:
            # Load the private key
            with open(self.auth_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(key_file.read(), password=None)

            # Create JWT payload
            payload = {"iss": self.team_id, "iat": now, "exp": now + 3600}  # Expire in 1 hour

            # Generate the token
            token = jwt.encode(
                payload, private_key, algorithm="ES256", headers={"kid": self.key_id}
            )

            # Cache the token
            self._jwt_token = token
            self._jwt_expires_at = now + 3600

            return token

        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            raise

    async def _send_apns_request(
        self, device_token: str, payload: Dict[str, Any], is_live_activity: bool = False
    ) -> bool:
        """
        Send APNS HTTP/2 request.

        Args:
            device_token: Device or Live Activity token
            payload: APNS payload
            is_live_activity: Whether this is a Live Activity update

        Returns:
            True if successful, False otherwise
        """
        # Use mock mode if configuration is incomplete
        if self._use_mock:
            logger.info(f"[MOCK] APNS Request (Live Activity: {is_live_activity}):")
            logger.info(f"[MOCK] Token: {device_token[:8]}...")
            logger.info(f"[MOCK] Payload: {json.dumps(payload, indent=2)}")
            await asyncio.sleep(0.1)  # Simulate network delay
            return True

        try:
            # Prepare headers
            # Live Activities require special topic format
            topic = (
                f"{self.bundle_id}.push-type.liveactivity" if is_live_activity else self.bundle_id
            )

            headers = {
                "apns-topic": topic,
                "apns-push-type": "liveactivity" if is_live_activity else "alert",
                "apns-priority": "10",  # High priority
                "content-type": "application/json",
            }

            # Debug logging
            logger.info(
                f"APNS Request Debug - Topic: {topic}, Push Type: {'liveactivity' if is_live_activity else 'alert'}, Token: {device_token[:12]}..."
            )

            # Add authentication header
            if self.team_id and self.key_id and self.auth_key_path:
                # JWT authentication (preferred)
                jwt_token = self._generate_jwt_token()
                headers["authorization"] = f"bearer {jwt_token}"

            # Construct URL
            url = f"{self.apns_url}/3/device/{device_token}"

            # Configure HTTP/2 client
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(10.0),
                cert=(self.cert_path, self.key_path) if self.cert_path and self.key_path else None,
            ) as client:
                # Send the request
                response = await client.post(url, json=payload, headers=headers)

                # Handle response
                if response.status_code == 200:
                    logger.info(
                        f"APNS notification sent successfully (Live Activity: {is_live_activity}) "
                        f"to {device_token[:8]}..."
                    )
                    return True
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        reason = error_data.get("reason", "unknown")
                        logger.error(
                            f"APNS request failed with 400 Bad Request: {reason} "
                            f"for token {device_token[:8]}..."
                        )
                    except Exception:
                        logger.error(
                            f"APNS request failed with 400 Bad Request for token {device_token[:8]}..."
                        )
                    return False
                elif response.status_code == 403:
                    logger.error(
                        f"APNS request forbidden (403) - check authentication for token {device_token[:8]}..."
                    )
                    return False
                elif response.status_code == 410:
                    logger.warning(
                        f"APNS token is no longer valid (410) - token should be removed: {device_token[:8]}..."
                    )
                    return False
                else:
                    logger.error(
                        f"APNS request failed with status {response.status_code} "
                        f"for token {device_token[:8]}...: {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error(f"APNS request timed out for token {device_token[:8]}...")
            return False
        except Exception as e:
            logger.error(f"APNS request failed for token {device_token[:8]}...: {str(e)}")
            return False

    async def _rate_limit(self):
        """Apply rate limiting to APNS requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()


class TrainUpdateNotificationService:
    """
    Service for detecting train changes and sending appropriate notifications.
    """

    def __init__(self):
        """Initialize the notification service."""
        self.push_service = APNSPushService()
        self.last_train_states: Dict[str, Dict[str, Any]] = {}

    async def process_train_updates(self, trains: List[Train], db: Session):
        """
        Process train updates and send notifications for significant changes.

        Args:
            trains: List of current train data
            db: Database session
        """
        try:
            for train in trains:
                await self._check_and_notify_train_changes(train, db)

        except Exception as e:
            logger.error(f"Error processing train updates: {str(e)}")

    async def _check_and_notify_train_changes(self, train: Train, db: Session):
        """
        Check for significant changes in a train and send notifications.

        Args:
            train: Train data
            db: Database session
        """
        try:
            train_key = f"{train.train_id}_{train.origin_station_code}"
            current_state = self._extract_train_state(train)
            last_state = self.last_train_states.get(train_key)

            # Detect significant changes
            alert_type = self._detect_alert_worthy_changes(last_state, current_state)

            if alert_type:
                # Get active Live Activity tokens for this train with device relationships
                from sqlalchemy.orm import joinedload

                active_tokens = (
                    db.query(LiveActivityToken)
                    .options(joinedload(LiveActivityToken.device))
                    .filter(
                        LiveActivityToken.train_id == train.train_id,
                        LiveActivityToken.is_active == True,
                    )
                    .all()
                )

                # Send both Live Activity updates and regular notifications
                for token in active_tokens:
                    results = await self.push_service.send_train_notifications(
                        live_activity_token=token,
                        train_data=current_state,
                        alert_type=alert_type,
                        db=db,
                    )

                    if results["live_activity"] or results["regular_notification"]:
                        logger.info(
                            f"Notifications sent for train {train.train_id}: {alert_type.value} "
                            f"(Live Activity: {results['live_activity']}, Regular: {results['regular_notification']})"
                        )
            else:
                # No alert, but send silent Live Activity updates to keep data fresh
                from sqlalchemy.orm import joinedload

                active_tokens = (
                    db.query(LiveActivityToken)
                    .options(joinedload(LiveActivityToken.device))
                    .filter(
                        LiveActivityToken.train_id == train.train_id,
                        LiveActivityToken.is_active == True,
                    )
                    .all()
                )

                for token in active_tokens:
                    # Send silent Live Activity update (no regular notification)
                    results = await self.push_service.send_train_notifications(
                        live_activity_token=token,
                        train_data=current_state,
                        alert_type=None,  # No alert = silent update
                        db=db,
                    )

                    if results["live_activity"]:
                        logger.debug(f"Silent Live Activity update sent for train {train.train_id}")

            # Update last known state
            self.last_train_states[train_key] = current_state

        except Exception as e:
            logger.error(f"Error checking train changes for {train.train_id}: {str(e)}")

    def _extract_train_state(self, train: Train) -> Dict[str, Any]:
        """
        Extract relevant state from train for comparison.

        Args:
            train: Train object

        Returns:
            State dictionary
        """
        return {
            "train_id": train.train_id,
            "track": train.track,
            "status": train.status,
            "delay_minutes": train.delay_minutes or 0,
            "departure_time": train.departure_time.isoformat() if train.departure_time else None,
            "current_location": getattr(train, "current_location", None),
            "journey_percent": getattr(train, "journey_percent", 0),
        }

    def _detect_alert_worthy_changes(
        self, old_state: Optional[Dict[str, Any]], new_state: Dict[str, Any]
    ) -> Optional[AlertType]:
        """
        Detect if changes warrant a Dynamic Island alert.

        Args:
            old_state: Previous train state
            new_state: Current train state

        Returns:
            AlertType if alert warranted, None otherwise
        """
        if not old_state:
            return None

        # Track assignment (highest priority)
        if not old_state.get("track") and new_state.get("track"):
            return AlertType.TRACK_ASSIGNED

        # Boarding status change
        old_status = old_state.get("status", "")
        new_status = new_state.get("status", "")

        if "BOARDING" not in old_status and "BOARDING" in new_status:
            return AlertType.BOARDING

        # Departure detection
        if old_status != "DEPARTED" and new_status == "DEPARTED":
            return AlertType.DEPARTED

        # Significant delay change (5+ minutes)
        old_delay = old_state.get("delay_minutes", 0)
        new_delay = new_state.get("delay_minutes", 0)

        if abs(new_delay - old_delay) >= 5:
            return AlertType.DELAY_UPDATE

        # Other significant status changes
        if old_status != new_status and new_status in ["DELAYED", "CANCELLED"]:
            return AlertType.STATUS_CHANGE

        return None


# Global instance for use in schedulers and services
notification_service = TrainUpdateNotificationService()
