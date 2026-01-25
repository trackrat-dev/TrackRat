"""
Minimal APNS service for Live Activity updates.

Simplified implementation focused on just Live Activity push notifications.
"""

import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from structlog import get_logger

from trackrat.settings import get_settings

logger = get_logger(__name__)


class SimpleAPNSService:
    """Minimal Apple Push Notification Service client."""

    def __init__(self) -> None:
        """Initialize APNS service with minimal configuration."""
        settings = get_settings()

        # Use sandbox for dev APNS environment, production for prod APNS environment
        if settings.apns_environment == "prod":
            self.base_url = "https://api.push.apple.com"
        else:
            self.base_url = "https://api.sandbox.push.apple.com"

        # APNS configuration from settings
        self.team_id = settings.apns_team_id
        self.key_id = settings.apns_key_id
        self.auth_key = (
            settings.apns_auth_key_content
        )  # P8 key content (from file or env var)
        self.bundle_id = settings.apns_bundle_id

        # JWT token cache
        self._jwt_token: str | None = None
        self._jwt_expires_at = 0

        # Check if configured
        self.is_configured = all(
            [self.team_id, self.key_id, self.auth_key, self.bundle_id]
        )

        if not self.is_configured:
            missing_fields = []
            if not self.team_id:
                missing_fields.append("team_id")
            if not self.key_id:
                missing_fields.append("key_id")
            if not self.auth_key:
                missing_fields.append("auth_key")
            if not self.bundle_id:
                missing_fields.append("bundle_id")

            logger.warning(
                "apns_not_configured",
                reason="Missing APNS credentials",
                missing_fields=missing_fields,
                auth_key_path=settings.apns_auth_key_path,
                has_auth_key_env_var=bool(settings.apns_auth_key),
            )

    def _get_jwt_token(self) -> str:
        """Generate or return cached JWT token for APNS."""
        now = int(time.time())

        # Check if token is still valid (with 5 minute buffer)
        if self._jwt_token and now < (self._jwt_expires_at - 300):
            return self._jwt_token

        if not (self.team_id and self.key_id and self.auth_key):
            raise ValueError(
                "JWT authentication requires team_id, key_id, and auth_key"
            )

        try:
            # Parse the P8 private key content (similar to V1 backend)
            private_key = serialization.load_pem_private_key(
                self.auth_key.encode("utf-8"), password=None
            )

            # Create JWT payload
            payload = {
                "iss": self.team_id,
                "iat": now,
                "exp": now + 3600,  # Expire in 1 hour
            }

            # Generate the token using the parsed private key
            self._jwt_token = jwt.encode(
                payload,
                private_key,  # type: ignore[arg-type]
                algorithm="ES256",
                headers={"kid": self.key_id},
            )
            self._jwt_expires_at = now + 3600

            return self._jwt_token

        except Exception as e:
            logger.error(
                "Failed to generate JWT token",
                error=str(e),
                error_type=type(e).__name__,
                auth_key_length=len(self.auth_key) if self.auth_key else 0,
                auth_key_starts_with_begin=(
                    self.auth_key.startswith("-----BEGIN") if self.auth_key else False
                ),
                auth_key_ends_with_end=(
                    self.auth_key.endswith("-----") if self.auth_key else False
                ),
            )
            raise

    async def send_live_activity_update(
        self, push_token: str, content_state: dict[str, Any]
    ) -> bool:
        """
        Send a Live Activity update to iOS device.

        Args:
            push_token: The Live Activity push token
            content_state: The content-state dictionary with train data

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.warning("apns_send_skipped", reason="Not configured")
            return False

        # Build minimal Live Activity payload
        payload = {
            "aps": {
                "timestamp": int(time.time()),
                "event": "update",
                "content-state": content_state,
            }
        }

        # Log the full payload for debugging
        logger.debug(
            "apns_payload_debug",
            push_token=push_token[:10] + "...",
            content_state_keys=list(content_state.keys()),
            journey_progress=content_state.get("journeyProgress"),
            has_departed=content_state.get("hasTrainDeparted"),
            status=content_state.get("status"),
            track=content_state.get("track"),
        )

        # APNS headers (include content-type like V1)
        headers = {
            "authorization": f"bearer {self._get_jwt_token()}",
            "apns-topic": f"{self.bundle_id}.push-type.liveactivity",
            "apns-push-type": "liveactivity",
            "apns-priority": "10",
            "content-type": "application/json",
        }

        # Send request
        url = f"{self.base_url}/3/device/{push_token}"

        try:
            # Configure HTTP/2 client like V1 backend
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(10.0),
            ) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    logger.info(
                        "apns_update_sent",
                        push_token=push_token[:10] + "...",
                        status_code=response.status_code,
                    )
                    return True

                # Handle specific errors
                if response.status_code == 410:
                    # Token is no longer valid
                    logger.warning(
                        "apns_token_invalid",
                        push_token=push_token[:10] + "...",
                        status_code=410,
                    )
                    return False

                logger.error(
                    "apns_error",
                    push_token=push_token[:10] + "...",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

        except Exception as e:
            logger.exception(
                "apns_exception", push_token=push_token[:10] + "...", error=str(e)
            )
            return False

    async def send_live_activity_end(
        self,
        push_token: str,
        content_state: dict[str, Any],
        dismissal_date: int | None = None,
    ) -> bool:
        """
        Send a Live Activity end event to iOS device.

        This tells iOS to end the Live Activity and remove it from the Lock Screen.

        Args:
            push_token: The Live Activity push token
            content_state: Final content-state to show before dismissal
            dismissal_date: Unix timestamp for when to remove from Lock Screen.
                           If None, uses current time + 4 hours (keeps on Lock Screen briefly).

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.warning("apns_end_skipped", reason="Not configured")
            return False

        # Default: dismiss from Lock Screen after 4 hours
        if dismissal_date is None:
            dismissal_date = int(time.time()) + (4 * 60 * 60)

        # Build Live Activity end payload
        payload = {
            "aps": {
                "timestamp": int(time.time()),
                "event": "end",
                "dismissal-date": dismissal_date,
                "content-state": content_state,
            }
        }

        logger.info(
            "apns_sending_end",
            push_token=push_token[:10] + "...",
            dismissal_date=dismissal_date,
            content_state_keys=list(content_state.keys()),
        )

        # APNS headers
        headers = {
            "authorization": f"bearer {self._get_jwt_token()}",
            "apns-topic": f"{self.bundle_id}.push-type.liveactivity",
            "apns-push-type": "liveactivity",
            "apns-priority": "10",
            "content-type": "application/json",
        }

        url = f"{self.base_url}/3/device/{push_token}"

        try:
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(10.0),
            ) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    logger.info(
                        "apns_end_sent",
                        push_token=push_token[:10] + "...",
                        status_code=response.status_code,
                    )
                    return True

                if response.status_code == 410:
                    logger.warning(
                        "apns_token_invalid",
                        push_token=push_token[:10] + "...",
                        status_code=410,
                    )
                    return False

                logger.error(
                    "apns_end_error",
                    push_token=push_token[:10] + "...",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

        except Exception as e:
            logger.exception(
                "apns_end_exception", push_token=push_token[:10] + "...", error=str(e)
            )
            return False
