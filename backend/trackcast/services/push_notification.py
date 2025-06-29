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
from trackcast.metrics import (
    LIVE_ACTIVITY_UPDATES_TOTAL,
    NOTIFICATION_ATTEMPTS_TOTAL,
    NOTIFICATION_LATENCY_SECONDS,
    NOTIFICATION_SUCCESSES_TOTAL,
)
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
    STOP_DEPARTURE = "stop_departure"
    APPROACHING_STOP = "approaching_stop"


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

        # Live Activity extension bundle ID (for reference only - not used in APNS topic)
        # Note: Live Activities use the main app bundle ID with .push-type.liveactivity suffix
        # The extension bundle ID is stored here for logging/debugging purposes only
        self.live_activity_bundle_id = os.getenv(
            "APNS_LIVE_ACTIVITY_BUNDLE_ID", f"{self.bundle_id}.TrainLiveActivityExtension"
        )

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
        event_data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, bool]:
        """
        Send Live Activity update with enhanced alert metadata for Dynamic Island prominence.

        Args:
            live_activity_token: LiveActivityToken object with device relationship
            train_data: Current train data for the update
            alert_type: Optional alert type for Dynamic Island prominence
            event_data: Optional event-specific data
            db: Database session for logging

        Returns:
            Dict with success status (only live_activity now)
        """
        results = {"live_activity": False}
        station = (
            train_data.get("train_id", "unknown")[:2] if train_data.get("train_id") else "unknown"
        )  # Extract station from train ID
        start_time = time.time()

        try:
            # Send Live Activity update with enhanced alert metadata
            await self._rate_limit()
            live_activity_payload = self._create_live_activity_payload(
                train_data, alert_type, event_data
            )

            # Track Live Activity attempt
            NOTIFICATION_ATTEMPTS_TOTAL.labels(
                notification_type="live_activity", station=station, result="attempted"
            ).inc()

            results["live_activity"] = await self._send_apns_request(
                live_activity_token.push_token, live_activity_payload, is_live_activity=True
            )

            # Track Live Activity result
            if results["live_activity"]:
                LIVE_ACTIVITY_UPDATES_TOTAL.labels(station=station, result="success").inc()
                NOTIFICATION_SUCCESSES_TOTAL.labels(
                    notification_type="live_activity", station=station
                ).inc()
            else:
                LIVE_ACTIVITY_UPDATES_TOTAL.labels(station=station, result="failure").inc()

            # Update database timestamps
            if db and results["live_activity"]:
                live_activity_token.last_update_sent = get_eastern_now()
                if alert_type:
                    live_activity_token.last_notification_sent = get_eastern_now()
                    if live_activity_token.device:
                        live_activity_token.device.last_used = get_eastern_now()
                db.commit()

            # Track overall notification latency
            total_latency = time.time() - start_time
            if results["live_activity"]:
                NOTIFICATION_LATENCY_SECONDS.labels(notification_type="live_activity").observe(
                    total_latency
                )

            alert_info = f" with {alert_type.value} alert" if alert_type else ""
            logger.info(
                f"📬 Live Activity update sent for train {train_data.get('train_id')}{alert_info} - Success: {results['live_activity']}"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to send Live Activity update: {str(e)}")
            # Track failed attempts due to exceptions
            NOTIFICATION_ATTEMPTS_TOTAL.labels(
                notification_type="live_activity", station=station, result="error"
            ).inc()
            return results

    async def send_live_activity_update(
        self,
        push_token: str,
        train_data: Dict[str, Any],
        alert_type: Optional[AlertType] = None,
        event_data: Optional[Dict[str, Any]] = None,
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
                results = await self.send_train_notifications(
                    token, train_data, alert_type, event_data, db
                )
                return results["live_activity"]

        # Fallback to basic Live Activity update
        try:
            await self._rate_limit()
            payload = self._create_live_activity_payload(train_data, alert_type, event_data)
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
        station = "unknown"  # Default since we don't have train context here
        start_time = time.time()

        try:
            # Track notification attempt
            NOTIFICATION_ATTEMPTS_TOTAL.labels(
                notification_type="device_push", station=station, result="attempted"
            ).inc()

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

            # Track result and latency
            latency = time.time() - start_time
            NOTIFICATION_LATENCY_SECONDS.labels(notification_type="device_push").observe(latency)

            if success:
                NOTIFICATION_SUCCESSES_TOTAL.labels(
                    notification_type="device_push", station=station
                ).inc()
                NOTIFICATION_ATTEMPTS_TOTAL.labels(
                    notification_type="device_push", station=station, result="success"
                ).inc()
                logger.info(f"Device notification sent successfully to {device_token[:8]}...")
            else:
                NOTIFICATION_ATTEMPTS_TOTAL.labels(
                    notification_type="device_push", station=station, result="failure"
                ).inc()

            return success

        except Exception as e:
            # Track error
            NOTIFICATION_ATTEMPTS_TOTAL.labels(
                notification_type="device_push", station=station, result="error"
            ).inc()
            logger.error(f"Failed to send device notification: {str(e)}")
            return False

    def _create_live_activity_payload(
        self,
        train_data: Dict[str, Any],
        alert_type: Optional[AlertType] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create APNS payload for Live Activity update.

        Args:
            train_data: Current train data
            alert_type: Optional alert type for Dynamic Island
            event_data: Optional event-specific data

        Returns:
            APNS payload dictionary
        """
        # Base Live Activity payload
        current_timestamp = int(time.time())

        # Convert journey percent (0-100) to progress (0.0-1.0)
        journey_percent = train_data.get("journey_percent", 0)
        journey_progress = journey_percent / 100.0 if journey_percent else 0.0

        # Extract status location from status_v2 if available
        status_location = None
        if isinstance(train_data.get("status_v2"), dict):
            status_location = train_data["status_v2"].get("location")

        payload = {
            "aps": {
                "timestamp": current_timestamp,
                "event": "update",
                "stale-date": current_timestamp + 900,  # 15 minutes from now
                "content-state": {
                    "trainNumber": train_data.get("train_id"),
                    "statusV2": str(
                        train_data.get("status_v2") or train_data.get("status", "")
                    ),  # Changed to camelCase, ensure string
                    "statusLocation": status_location,  # Added
                    "track": train_data.get("track"),
                    "delayMinutes": train_data.get("delay_minutes", 0),
                    "currentLocation": train_data.get("current_location"),
                    "nextStop": train_data.get("next_stop_info"),  # Changed to camelCase
                    "journeyProgress": journey_progress,  # Changed to camelCase and converted to 0-1
                    "destinationETA": train_data.get("destination_eta"),  # Added
                    "trackRatPrediction": train_data.get("trackrat_prediction"),  # Added
                    "lastUpdated": current_timestamp,
                    "hasStatusChanged": train_data.get("has_status_changed", False),  # Added
                },
            }
        }

        # Add enhanced alert configuration for Dynamic Island prominence
        if alert_type:
            alert_config = self._get_alert_config(train_data, alert_type)
            if alert_config:
                # Core APNS alert fields
                payload["aps"]["alert"] = alert_config["alert"]
                payload["aps"]["sound"] = alert_config.get("sound", "default")
                payload["aps"]["relevance-score"] = alert_config.get("relevance_score", 1.0)

                # Enhanced metadata for Live Activity processing
                payload["aps"]["content-state"]["alertMetadata"] = alert_config.get(
                    "alert_metadata", {}
                )
                payload["aps"]["content-state"]["dynamicIslandPriority"] = alert_config.get(
                    "priority", "medium"
                )
                payload["aps"]["content-state"]["requiresHapticFeedback"] = alert_config.get(
                    "requires_attention", False
                )

        # Add event-specific data if provided
        if alert_type and event_data:
            payload["event_type"] = alert_type.value
            payload["event_data"] = event_data

        # Always include a timestamp for Live Activity freshness
        payload["aps"]["content-state"]["pushTimestamp"] = current_timestamp

        # Debug logging for enhanced Live Activity payload
        logger.info(f"🔍 Enhanced Live Activity Payload Debug:")
        logger.info(f"  🎯 Event: {payload['aps']['event']}")
        logger.info(f"  🚨 Alert Type: {alert_type.value if alert_type else 'None'}")
        logger.info(f"  ⭐ Relevance Score: {payload['aps'].get('relevance-score', 'None')}")
        logger.info(f"  🗝️  Content State Keys: {list(payload['aps']['content-state'].keys())}")
        logger.info(f"  📊 Journey Progress: {payload['aps']['content-state']['journeyProgress']}")
        logger.info(f"  🚂 Status V2: {payload['aps']['content-state']['statusV2']}")
        logger.info(f"  🎯 Train ID: {payload['aps']['content-state']['trainNumber']}")
        logger.info(f"  🛤️  Track: {payload['aps']['content-state'].get('track', 'None')}")
        logger.info(
            f"  📍 Status Location: {payload['aps']['content-state'].get('statusLocation', 'None')}"
        )

        # Log enhanced metadata if present
        if alert_type:
            logger.info(
                f"  🔥 Dynamic Island Priority: {payload['aps']['content-state'].get('dynamicIslandPriority', 'None')}"
            )
            logger.info(
                f"  📳 Requires Haptic: {payload['aps']['content-state'].get('requiresHapticFeedback', 'None')}"
            )
            logger.info(
                f"  📋 Alert Metadata: {payload['aps']['content-state'].get('alertMetadata', {})}"
            )

        logger.info(
            f"  ⏰ Push Timestamp: {payload['aps']['content-state'].get('pushTimestamp', 'None')}"
        )

        return payload

    def _get_alert_config(
        self, train_data: Dict[str, Any], alert_type: AlertType
    ) -> Optional[Dict[str, Any]]:
        """
        Get enhanced alert configuration for Live Activity Dynamic Island prominence.

        These configurations replace traditional push notifications with Live Activity
        alerts that trigger Dynamic Island expansion with maximum visibility.

        Args:
            train_data: Current train data
            alert_type: Type of alert

        Returns:
            Enhanced alert configuration dictionary with high relevance scores
        """
        train_id = train_data.get("train_id", "")
        track = train_data.get("track", "")
        delay_minutes = train_data.get("delay_minutes", 0)

        # Get station and destination for contextual messages
        status_v2 = train_data.get("status_v2", {})
        location = status_v2.get("location") if isinstance(status_v2, dict) else None

        configs = {
            AlertType.TRACK_ASSIGNED: {
                "alert": {
                    "title": "Track Assigned! 🚋",
                    "body": f"Track {track} - Get Ready to Board",
                },
                "sound": "default",
                "relevance_score": 95.0,  # Maximum prominence for track assignments
                "priority": "high",
                "requires_attention": True,
            },
            AlertType.BOARDING: {
                "alert": {
                    "title": "Time to Board! 🚆",
                    "body": f"Track {track} - All Aboard!" if track else "Boarding Now!",
                },
                "sound": "default",
                "relevance_score": 100.0,  # Maximum possible prominence for boarding
                "priority": "urgent",
                "requires_attention": True,
            },
            AlertType.DEPARTED: {
                "alert": {
                    "title": "Journey Started 🛤️",
                    "body": f"Train {train_id} has departed{f' from {location}' if location else ''}",
                },
                "sound": "default",
                "relevance_score": 88.0,  # High prominence for departures
                "priority": "high",
                "requires_attention": True,
            },
            AlertType.APPROACHING: {
                "alert": {
                    "title": "Approaching Destination! 🎯",
                    "body": "Your stop is coming up - Get ready!",
                },
                "sound": "default",
                "relevance_score": 92.0,  # Very high prominence for approaching destination
                "priority": "high",
                "requires_attention": True,
            },
            AlertType.DELAY_UPDATE: {
                "alert": {
                    "title": "Delay Update ⏰",
                    "body": f"Train {train_id} now {delay_minutes} minutes delayed",
                },
                "sound": "default",
                "relevance_score": (
                    75.0 if delay_minutes >= 10 else 60.0
                ),  # Higher for significant delays
                "priority": "medium" if delay_minutes >= 10 else "low",
                "requires_attention": delay_minutes
                >= 15,  # Only require attention for major delays
            },
            AlertType.STATUS_CHANGE: {
                "alert": {
                    "title": "Status Update 📢",
                    "body": f"Train {train_id} status has changed",
                },
                "sound": "default",
                "relevance_score": 70.0,  # Moderate prominence for status changes
                "priority": "medium",
                "requires_attention": False,
            },
            AlertType.STOP_DEPARTURE: {
                "alert": {
                    "title": "Stop Departure 🚂",
                    "body": f"Train {train_id} departed{f' {location}' if location else ''}",
                },
                "sound": "default",
                "relevance_score": 85.0,  # High prominence for stop departures
                "priority": "high",
                "requires_attention": True,
            },
            AlertType.APPROACHING_STOP: {
                "alert": {
                    "title": "Approaching Stop 📍",
                    "body": f"Next stop coming up{f': {location}' if location else ''}",
                },
                "sound": "default",
                "relevance_score": 90.0,  # Very high prominence for approaching stops
                "priority": "high",
                "requires_attention": True,
            },
        }

        config = configs.get(alert_type)
        if config:
            # Add metadata for Live Activity processing
            config["alert_metadata"] = {
                "alert_type": alert_type.value,
                "train_id": train_id,
                "track": track,
                "dynamic_island_priority": config["priority"],
                "requires_haptic_feedback": config["requires_attention"],
                "timestamp": int(time.time()),
            }

        return config

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
            # IMPORTANT: Per Apple docs, Live Activities use the format:
            # <your bundleID>.push-type.liveactivity
            # This uses the MAIN APP bundle ID, not the extension bundle ID
            if is_live_activity:
                # Live Activities must use main app bundle ID + .push-type.liveactivity
                topic = f"{self.bundle_id}.push-type.liveactivity"
            else:
                # Use the main app bundle ID for regular notifications
                topic = self.bundle_id

            headers = {
                "apns-topic": topic,
                "apns-push-type": "liveactivity" if is_live_activity else "alert",
                "apns-priority": "10",  # High priority
                "content-type": "application/json",
            }

            # Construct URL first
            url = f"{self.apns_url}/3/device/{device_token}"

            # Add authentication header
            if self.team_id and self.key_id and self.auth_key_path:
                # JWT authentication (preferred)
                jwt_token = self._generate_jwt_token()
                headers["authorization"] = f"bearer {jwt_token}"

            # Validate topic format for Live Activities
            if is_live_activity and not topic.endswith(".push-type.liveactivity"):
                logger.error(f"❌ Invalid Live Activity topic format: {topic}")
                logger.error("Live Activity topics must end with '.push-type.liveactivity'")
                return False

            # Debug logging
            logger.info(
                f"🚀 APNS Request Debug - Topic: {topic}, Push Type: {'liveactivity' if is_live_activity else 'alert'}, Token: {device_token[:12]}..."
            )
            logger.info(f"📡 APNS URL: {url}")
            logger.info(f"📋 APNS Headers: {headers}")
            if is_live_activity:
                logger.info(
                    f"🎯 Using Live Activity Topic: {topic} (Main app bundle + .push-type.liveactivity)"
                )
                logger.info(
                    f"📌 Extension Bundle ID (for reference): {self.live_activity_bundle_id}"
                )
            else:
                logger.info(f"📱 Using Main App Bundle ID: {self.bundle_id}")
            if is_live_activity:
                logger.info(f"📦 APNS Live Activity Payload: {json.dumps(payload, indent=2)}")
            else:
                logger.info(f"📦 APNS Regular Payload: {json.dumps(payload, indent=2)}")

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

                        # Special handling for DeviceTokenNotForTopic
                        if reason == "DeviceTokenNotForTopic":
                            logger.error(
                                f"❌ DeviceTokenNotForTopic: The token was not issued for topic '{topic}'. "
                                f"This usually means:\n"
                                f"  1. The iOS app is using a different bundle ID than expected\n"
                                f"  2. The token is from a development build but being sent to production APNS (or vice versa)\n"
                                f"  3. For Live Activities, ensure the iOS app is sending the Live Activity push token, "
                                f"not the regular device token"
                            )
                            if is_live_activity:
                                logger.error(
                                    f"🔍 Live Activity Debug Info:\n"
                                    f"  - Expected topic: {topic}\n"
                                    f"  - Main app bundle ID: {self.bundle_id}\n"
                                    f"  - Extension bundle ID (reference): {self.live_activity_bundle_id}\n"
                                    f"  - APNS environment: {'Production' if 'sandbox' not in self.apns_url else 'Sandbox'}"
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
        logger.info(f"🔄 Processing train updates for {len(trains)} trains")
        try:
            for train in trains:
                await self._check_and_notify_train_changes(train, db)
            logger.info(f"✅ Successfully processed {len(trains)} train updates")
        except Exception as e:
            logger.error(f"❌ Error processing train updates: {str(e)}")

    async def process_consolidated_train_updates(
        self, train_ids: List[str], db: Session, since: Optional[datetime] = None
    ):
        """
        Process train updates using consolidation to eliminate duplicates and enhance data.

        This method replaces process_train_updates with a consolidation-aware approach:
        1. For each unique train_id, fetch all Train records from different origin stations
        2. Apply consolidation to get unified journey data with enhanced fields
        3. Send notifications using the consolidated data (with status_v2, progress, etc.)

        Args:
            train_ids: List of unique train IDs to process
            db: Database session
            since: Optional datetime to filter train records updated since this time
        """
        logger.info(f"🔄 Processing consolidated train updates for {len(train_ids)} unique trains")

        try:
            from trackcast.db.repository import TrainRepository
            from trackcast.services.train_consolidation import TrainConsolidationService

            train_repo = TrainRepository(db)
            consolidation_service = TrainConsolidationService()

            for train_id in train_ids:
                try:
                    # Get all Train records for this train_id (from all origin stations)
                    train_records = train_repo.get_all_trains_for_train_id(train_id, since=since)

                    if not train_records:
                        logger.warning(f"⚠️ No train records found for train_id {train_id}")
                        continue

                    logger.debug(f"📊 Found {len(train_records)} records for train {train_id}")

                    # Apply consolidation (without station context for now)
                    consolidated_trains = consolidation_service.consolidate_trains(
                        train_records, from_station_code=None
                    )

                    if not consolidated_trains:
                        logger.warning(f"⚠️ Consolidation produced no results for train {train_id}")
                        continue

                    # Should get exactly one consolidated train per unique train_id
                    consolidated_train = consolidated_trains[0]

                    logger.debug(
                        f"✅ Consolidated train {train_id}: status_v2='{consolidated_train.get('status_v2', {}).get('current', 'None')}', progress={consolidated_train.get('progress', {}).get('journey_percent', 0)}%"
                    )

                    # Process notifications using consolidated data
                    await self._check_and_notify_consolidated_train_changes(consolidated_train, db)

                except Exception as e:
                    logger.error(f"❌ Error processing train {train_id}: {str(e)}")
                    continue

            logger.info(f"✅ Successfully processed {len(train_ids)} consolidated train updates")

        except Exception as e:
            logger.error(f"❌ Error in consolidated train processing: {str(e)}")

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

            logger.debug(
                f"🔍 Checking train {train.train_id} - Last state: {bool(last_state)}, Current: {current_state.get('status')}"
            )

            # Detect significant changes
            alert_type = self._detect_alert_worthy_changes(last_state, current_state)

            if alert_type:
                logger.info(f"🚨 Alert detected for train {train.train_id}: {alert_type.value}")
            else:
                logger.debug(f"📊 No alert for train {train.train_id}, sending silent update")

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

                logger.info(
                    f"📱 Found {len(active_tokens)} active Live Activity tokens for train {train.train_id}"
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
                            f"✅ Notifications sent for train {train.train_id}: {alert_type.value} "
                            f"(Live Activity: {results['live_activity']}, Regular: {results['regular_notification']}) to token {token.push_token[:12]}..."
                        )
                    else:
                        logger.warning(
                            f"⚠️ Failed to send notifications for train {train.train_id}: {alert_type.value} to token {token.push_token[:12]}..."
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

                logger.debug(
                    f"📤 Sending silent Live Activity updates to {len(active_tokens)} tokens"
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
                        logger.debug(
                            f"🔕 Silent Live Activity update sent for train {train.train_id} to token {token.push_token[:12]}..."
                        )
                    else:
                        logger.warning(
                            f"⚠️ Silent Live Activity update failed for train {train.train_id} to token {token.push_token[:12]}..."
                        )

            # Update last known state
            self.last_train_states[train_key] = current_state
            logger.debug(f"💾 Updated last known state for train {train.train_id}")

        except Exception as e:
            logger.error(f"❌ Error checking train changes for {train.train_id}: {str(e)}")
            import traceback

            logger.error(f"📋 Traceback: {traceback.format_exc()}")

    async def _check_and_notify_consolidated_train_changes(
        self, consolidated_train: Dict, db: Session
    ):
        """
        Check for significant changes in a consolidated train and send notifications.

        This method handles consolidated train data (dict) instead of Train objects,
        allowing for enhanced fields like status_v2 and progress from consolidation.

        Args:
            consolidated_train: Consolidated train dictionary from TrainConsolidationService
            db: Database session
        """
        try:
            train_id = consolidated_train.get("train_id")
            if not train_id:
                logger.error("❌ No train_id found in consolidated train data")
                return

            # Use consolidated_id for state tracking (includes journey info)
            train_key = consolidated_train.get("consolidated_id", train_id)
            current_state = self._extract_consolidated_train_state(consolidated_train)
            last_state = self.last_train_states.get(train_key)

            logger.debug(
                f"🔍 Checking consolidated train {train_id} - Last state: {bool(last_state)}, Current status_v2: {current_state.get('status_v2')}"
            )

            # Detect significant changes
            alert_type = self._detect_alert_worthy_changes(last_state, current_state)

            if alert_type:
                logger.info(
                    f"🚨 Alert detected for consolidated train {train_id}: {alert_type.value}"
                )
            else:
                logger.debug(
                    f"📊 No alert for consolidated train {train_id}, sending silent update"
                )

            # Get active Live Activity tokens for this train
            from sqlalchemy.orm import joinedload

            active_tokens = (
                db.query(LiveActivityToken)
                .options(joinedload(LiveActivityToken.device))
                .filter(
                    LiveActivityToken.train_id == train_id,
                    LiveActivityToken.is_active == True,
                )
                .all()
            )

            if not active_tokens:
                logger.debug(f"📭 No active Live Activity tokens found for train {train_id}")
                return

            logger.info(
                f"📱 Found {len(active_tokens)} active Live Activity tokens for consolidated train {train_id}"
            )

            # Send notifications to all active tokens
            for token in active_tokens:
                try:
                    if alert_type:
                        # Send alert notification
                        results = await self.push_service.send_train_notifications(
                            live_activity_token=token,
                            train_data=current_state,
                            alert_type=alert_type,
                            db=db,
                        )

                        if results["live_activity"] or results["regular_notification"]:
                            logger.info(
                                f"✅ Alert sent for train {train_id}: {alert_type.value} "
                                f"(Live Activity: {results['live_activity']}, Regular: {results['regular_notification']}) to token {token.push_token[:12]}..."
                            )
                        else:
                            logger.warning(
                                f"⚠️ Failed to send alert for train {train_id}: {alert_type.value} to token {token.push_token[:12]}..."
                            )
                    else:
                        # Send silent Live Activity update only
                        results = await self.push_service.send_train_notifications(
                            live_activity_token=token,
                            train_data=current_state,
                            alert_type=None,  # Silent update
                            db=db,
                        )

                        if results["live_activity"]:
                            logger.debug(
                                f"🔕 Silent update sent for train {train_id} to token {token.push_token[:12]}..."
                            )
                        else:
                            logger.warning(
                                f"⚠️ Silent update failed for train {train_id} to token {token.push_token[:12]}..."
                            )

                except Exception as e:
                    logger.error(
                        f"❌ Error sending notification for train {train_id} to token {token.push_token[:12]}...: {str(e)}"
                    )

            # Update last known state
            self.last_train_states[train_key] = current_state
            logger.debug(f"💾 Updated last known state for consolidated train {train_id}")

        except Exception as e:
            logger.error(f"❌ Error checking consolidated train changes: {str(e)}")
            import traceback

            logger.error(f"📋 Traceback: {traceback.format_exc()}")

    def _extract_train_state(self, train: Train) -> Dict[str, Any]:
        """
        Extract relevant state from train for comparison.

        Args:
            train: Train object

        Returns:
            State dictionary
        """
        state = {
            "train_id": train.train_id,
            "track": train.track,
            "status": train.status,
            "delay_minutes": train.delay_minutes or 0,
            "departure_time": train.departure_time.isoformat() if train.departure_time else None,
            "current_location": getattr(train, "current_location", None),
            "journey_percent": getattr(train, "journey_percent", 0),
        }
        logger.debug(
            f"📊 Extracted state for train {train.train_id}: track={state['track']}, status={state['status']}"
        )
        return state

    def _extract_consolidated_train_state(self, consolidated_train: Dict) -> Dict[str, Any]:
        """
        Extract relevant state from consolidated train data for comparison.

        This method extracts state from consolidated train dictionaries,
        utilizing enhanced fields like status_v2 and progress that are only
        available after consolidation.

        Args:
            consolidated_train: Consolidated train dictionary from TrainConsolidationService

        Returns:
            State dictionary with enhanced fields
        """
        # Extract basic fields
        state = {
            "train_id": consolidated_train.get("train_id"),
            "track": consolidated_train.get("track_assignment", {}).get("track"),
            "status": consolidated_train.get("status"),  # Legacy status
            "delay_minutes": consolidated_train.get("delay_minutes", 0),
            "departure_time": consolidated_train.get("origin_station", {}).get("departure_time"),
        }

        # Extract enhanced fields from consolidation
        status_v2 = consolidated_train.get("status_v2", {})
        progress = consolidated_train.get("progress", {})

        # Add enhanced status information
        state["status_v2"] = status_v2.get("current") if status_v2 else None
        state["status_location"] = status_v2.get("location") if status_v2 else None

        # Add journey progress information
        state["journey_percent"] = progress.get("journey_percent", 0) if progress else 0

        # Handle last_departed - it might be None
        last_departed = progress.get("last_departed") if progress else None
        state["current_location"] = (
            last_departed.get("station_code")
            if last_departed and isinstance(last_departed, dict)
            else None
        )

        # Handle next_arrival - it might be None
        next_arrival = progress.get("next_arrival") if progress else None
        state["next_stop"] = (
            next_arrival.get("station_code")
            if next_arrival and isinstance(next_arrival, dict)
            else None
        )
        state["destination_eta"] = (
            next_arrival.get("estimated_time")
            if next_arrival and isinstance(next_arrival, dict)
            else None
        )

        # Add prediction data
        prediction = consolidated_train.get("prediction_data", {})
        state["track_prediction"] = prediction if prediction else None

        # Add consolidation metadata for richer notifications
        state["consolidated_id"] = consolidated_train.get("consolidated_id")
        state["consolidation_confidence"] = consolidated_train.get(
            "consolidation_metadata", {}
        ).get("confidence_score", 0)

        logger.debug(
            f"📊 Extracted consolidated state for train {state['train_id']}: "
            f"track={state['track']}, status_v2={state['status_v2']}, progress={state['journey_percent']}%"
        )
        return state

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
        old_track = old_state.get("track")
        new_track = new_state.get("track")
        if not old_track and new_track:
            logger.info(f"🛤️ Track assigned for train {new_state.get('train_id')}: {new_track}")
            return AlertType.TRACK_ASSIGNED

        # Boarding status change
        old_status = old_state.get("status", "")
        new_status = new_state.get("status", "")

        if "BOARDING" not in old_status and "BOARDING" in new_status:
            logger.info(f"🚆 Boarding started for train {new_state.get('train_id')}")
            return AlertType.BOARDING

        # Departure detection
        if old_status != "DEPARTED" and new_status == "DEPARTED":
            logger.info(f"🛤️ Train {new_state.get('train_id')} departed")
            return AlertType.DEPARTED

        # Significant delay change (5+ minutes)
        old_delay = old_state.get("delay_minutes", 0)
        new_delay = new_state.get("delay_minutes", 0)

        if abs(new_delay - old_delay) >= 5:
            logger.info(
                f"⏰ Significant delay change for train {new_state.get('train_id')}: {old_delay} -> {new_delay} minutes"
            )
            return AlertType.DELAY_UPDATE

        # Other significant status changes
        if old_status != new_status and new_status in ["DELAYED", "CANCELLED"]:
            logger.info(
                f"📢 Status change for train {new_state.get('train_id')}: {old_status} -> {new_status}"
            )
            return AlertType.STATUS_CHANGE

        if old_status != new_status:
            logger.debug(
                f"🔄 Status change (no alert) for train {new_state.get('train_id')}: {old_status} -> {new_status}"
            )

        return None


class LiveActivityEventDetector:
    """
    Service for detecting stop departure and approaching stop events for Live Activities.
    """

    def __init__(self):
        """Initialize the event detector."""
        self.push_service = APNSPushService()
        self.last_train_stops: Dict[str, List[Dict[str, Any]]] = {}
        self.notification_history: Dict[str, datetime] = {}

    async def detect_stop_departures(
        self,
        train: Train,
        previous_stops: List[Dict[str, Any]],
        current_stops: List[Dict[str, Any]],
        db: Session,
    ) -> List[Dict[str, Any]]:
        """
        Detect when a train departs from a stop.

        Args:
            train: Train object
            previous_stops: Previous state of stops
            current_stops: Current state of stops
            db: Database session

        Returns:
            List of stop departure events
        """
        events = []

        # Get active Live Activity tokens for this train
        active_tokens = (
            db.query(LiveActivityToken)
            .filter(
                LiveActivityToken.train_id == train.train_id, LiveActivityToken.is_active == True
            )
            .all()
        )

        if not active_tokens:
            return events

        # Check each stop for departure changes
        for i, stop in enumerate(current_stops):
            # Find corresponding previous stop
            prev_stop = None
            for ps in previous_stops:
                if ps.get("station_code") == stop.get("station_code"):
                    prev_stop = ps
                    break

            if prev_stop:
                # Check if stop just departed
                if not prev_stop.get("departed", False) and stop.get("departed", False):
                    # Check each active Live Activity
                    for token in active_tokens:
                        # Note: LiveActivityToken doesn't store origin/destination station codes
                        # So we'll send notifications for all significant stop events
                        # The iOS app can filter based on user's actual journey

                        # Calculate total stops remaining (simplified without journey context)
                        stops_remaining = (
                            len([s for s in current_stops if not s.get("departed", False)]) - 1
                        )

                        events.append(
                            {
                                "type": "stop_departure",
                                "token": token,
                                "train": train,
                                "event_data": {
                                    "station": stop.get("station_name"),
                                    "is_origin": False,  # Can't determine without station context
                                    "stops_remaining": stops_remaining,
                                    "departed_at": stop.get(
                                        "actual_departure_time", datetime.now()
                                    ).isoformat(),
                                },
                            }
                        )

        return events

    async def detect_approaching_stops(
        self, train: Train, current_stops: List[Dict[str, Any]], db: Session
    ) -> List[Dict[str, Any]]:
        """
        Detect when train is approaching stops.

        Args:
            train: Train object
            current_stops: Current state of stops
            db: Database session

        Returns:
            List of approaching stop events
        """
        events = []
        current_time = get_eastern_now()

        # Get active Live Activity tokens for this train
        active_tokens = (
            db.query(LiveActivityToken)
            .filter(
                LiveActivityToken.train_id == train.train_id, LiveActivityToken.is_active == True
            )
            .all()
        )

        if not active_tokens:
            return events

        # Check each stop for approaching notifications
        for stop in current_stops:
            # Skip departed stops
            if stop.get("departed", False):
                continue

            # Calculate time to arrival
            scheduled_time = stop.get("scheduled_time")
            if scheduled_time:
                try:
                    if isinstance(scheduled_time, str):
                        # Handle various datetime formats safely
                        if scheduled_time.endswith("Z"):
                            scheduled_time = datetime.fromisoformat(
                                scheduled_time.replace("Z", "+00:00")
                            )
                        elif "+" in scheduled_time or scheduled_time.endswith("00:00"):
                            scheduled_time = datetime.fromisoformat(scheduled_time)
                        else:
                            # Assume Eastern time if no timezone info
                            from dateutil import tz

                            scheduled_time = datetime.fromisoformat(scheduled_time).replace(
                                tzinfo=tz.gettz("US/Eastern")
                            )

                    time_to_arrival = scheduled_time - current_time
                    minutes_away = int(time_to_arrival.total_seconds() / 60)
                except Exception as dt_error:
                    logger.error(
                        f"⚠️ Error parsing scheduled_time '{scheduled_time}' for stop: {dt_error}"
                    )
                    continue

                # Check if within notification window (2-3 minutes)
                if 0 < minutes_away <= 3:
                    for token in active_tokens:
                        # Check if notification already sent
                        notification_key = (
                            f"{train.train_id}-{stop.get('station_code')}-approaching"
                        )
                        last_sent = self.notification_history.get(notification_key)

                        # Only send once per stop
                        if not last_sent:
                            # Send approaching notifications for all stops
                            # (iOS app can filter based on user's journey)
                            events.append(
                                {
                                    "type": "approaching_stop",
                                    "token": token,
                                    "train": train,
                                    "event_data": {
                                        "station": stop.get("station_name"),
                                        "minutes_away": minutes_away,
                                        "is_destination": False,  # Can't determine without station context
                                        "estimated_arrival": scheduled_time.isoformat(),
                                    },
                                }
                            )

                            # Mark as sent
                            self.notification_history[notification_key] = current_time

        return events

    async def process_train_for_events(self, train: Train, db: Session):
        """
        Process a train for stop departure and approaching stop events.

        Args:
            train: Train object with stops data
            db: Database session
        """
        try:
            train_key = f"{train.train_id}_{train.origin_station_code}"
            logger.debug(f"🔍 Processing events for train {train.train_id}")

            # Extract current stops
            current_stops = []
            if hasattr(train, "stops") and train.stops:
                for stop in train.stops:
                    current_stops.append(
                        {
                            "station_code": stop.station_code,
                            "station_name": stop.station_name,
                            "scheduled_time": stop.scheduled_arrival,  # Use scheduled_arrival instead
                            "actual_departure_time": stop.actual_departure,
                            "departed": stop.departed,
                        }
                    )
                logger.debug(f"📍 Extracted {len(current_stops)} stops for train {train.train_id}")
            else:
                logger.debug(f"📍 No stops data available for train {train.train_id}")

            # Get previous stops
            previous_stops = self.last_train_stops.get(train_key, [])

            # Detect stop departures
            departure_events = await self.detect_stop_departures(
                train, previous_stops, current_stops, db
            )

            # Detect approaching stops
            approaching_events = await self.detect_approaching_stops(train, current_stops, db)

            # Send notifications for all events
            all_events = departure_events + approaching_events
            logger.info(
                f"📬 Sending {len(all_events)} event notifications for train {train.train_id}"
            )

            for event in all_events:
                token = event["token"]
                train_data = self._extract_train_data(event["train"])

                alert_type = (
                    AlertType.STOP_DEPARTURE
                    if event["type"] == "stop_departure"
                    else AlertType.APPROACHING_STOP
                )

                logger.info(
                    f"🎯 Sending {event['type']} notification for train {train.train_id} at {event['event_data']['station']}"
                )

                results = await self.push_service.send_train_notifications(
                    live_activity_token=token,
                    train_data=train_data,
                    alert_type=alert_type,
                    event_data=event["event_data"],
                    db=db,
                )

                if results["live_activity"]:
                    logger.info(
                        f"✅ Sent {event['type']} notification for train {train.train_id} "
                        f"stop {event['event_data']['station']}"
                    )
                else:
                    logger.error(
                        f"❌ Failed to send {event['type']} notification for train {train.train_id} "
                        f"stop {event['event_data']['station']}"
                    )

            # Update last known stops
            self.last_train_stops[train_key] = current_stops

        except Exception as e:
            logger.error(f"Error processing train events for {train.train_id}: {str(e)}")

    def _is_stop_in_journey(
        self,
        stop: Dict[str, Any],
        origin_code: str,
        destination_code: str,
        all_stops: List[Dict[str, Any]],
    ) -> bool:
        """Check if a stop is within user's journey."""
        # Find indices
        origin_idx = destination_idx = stop_idx = None

        for i, s in enumerate(all_stops):
            if s.get("station_code") == origin_code:
                origin_idx = i
            if s.get("station_code") == destination_code:
                destination_idx = i
            if s.get("station_code") == stop.get("station_code"):
                stop_idx = i

        # Check if stop is between origin and destination
        if origin_idx is not None and destination_idx is not None and stop_idx is not None:
            return origin_idx <= stop_idx <= destination_idx

        return False

    def _count_remaining_stops(
        self, all_stops: List[Dict[str, Any]], current_stop_code: str, destination_code: str
    ) -> int:
        """Count remaining stops to destination."""
        current_idx = destination_idx = None

        for i, s in enumerate(all_stops):
            if s.get("station_code") == current_stop_code:
                current_idx = i
            if s.get("station_code") == destination_code:
                destination_idx = i

        if current_idx is not None and destination_idx is not None:
            return destination_idx - current_idx

        return 0

    def _extract_train_data(self, train: Train) -> Dict[str, Any]:
        """Extract train data for notifications."""
        # Extract status_v2 data if available
        status_v2 = getattr(train, "status_v2", None)
        status_v2_str = train.status
        status_location = None

        if status_v2 and isinstance(status_v2, dict):
            status_v2_str = status_v2.get("current", train.status)
            status_location = status_v2.get("location")
        elif isinstance(status_v2, str):
            status_v2_str = status_v2

        # Extract next stop info
        next_stop_info = None
        progress = getattr(train, "progress", None)
        if progress and isinstance(progress, dict):
            next_arrival = progress.get("next_arrival")
            if next_arrival:
                next_stop_info = {
                    "stationCode": next_arrival.get("station_code"),
                    "stationName": next_arrival.get("station_name"),
                    "scheduledTime": next_arrival.get("scheduled_time"),
                    "minutesAway": next_arrival.get("minutes_away", 0),
                }

        # Extract destination ETA
        destination_eta = None
        if hasattr(train, "stops") and train.stops:
            # Find destination stop and get its scheduled time
            for stop in train.stops:
                if hasattr(stop, "station_code") and hasattr(train, "destination_station_code"):
                    if stop.station_code == train.destination_station_code:
                        destination_eta = (
                            stop.scheduled_arrival.isoformat() if stop.scheduled_arrival else None
                        )
                        break

        # Extract prediction data if available
        trackrat_prediction = None
        if hasattr(train, "prediction_data") and train.prediction_data:
            pred = train.prediction_data
            trackrat_prediction = {
                "predictedTrack": (
                    pred.predicted_track if hasattr(pred, "predicted_track") else None
                ),
                "confidence": pred.confidence if hasattr(pred, "confidence") else 0.0,
                "trackProbabilities": (
                    pred.track_probabilities if hasattr(pred, "track_probabilities") else {}
                ),
            }

        return {
            "train_id": train.train_id,
            "track": train.track,
            "status": train.status,
            "status_v2": status_v2_str,
            "status_location": status_location,
            "delay_minutes": train.delay_minutes or 0,
            "current_location": getattr(train, "current_location", None),
            "journey_percent": getattr(train, "journey_percent", 0),
            "next_stop_info": next_stop_info,
            "destination_eta": destination_eta,
            "trackrat_prediction": trackrat_prediction,
            "has_status_changed": getattr(
                train, "has_status_changed", False
            ),  # Use train attribute if available
        }

    def cleanup_old_notifications(self, hours: int = 24):
        """Remove old notification history entries."""
        cutoff_time = get_eastern_now() - timedelta(hours=hours)
        keys_to_remove = []

        for key, timestamp in self.notification_history.items():
            if timestamp < cutoff_time:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.notification_history[key]

        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} old notification history entries")


# Global instances for use in schedulers and services
notification_service = TrainUpdateNotificationService()
event_detector = LiveActivityEventDetector()
