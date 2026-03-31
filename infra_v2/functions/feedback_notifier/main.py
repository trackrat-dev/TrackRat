"""Cloud Function to send user feedback notifications to Slack."""

import base64
import json
import urllib.request
from google.cloud import secretmanager


def get_slack_webhook():
    """Retrieve Slack webhook URL from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = "projects/trackrat-v2/secrets/slack-feedback-webhook/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def notify_feedback(event, context):
    """Triggered by Pub/Sub when user feedback is submitted."""
    # Decode the Pub/Sub message
    pubsub_data = base64.b64decode(event["data"]).decode("utf-8")
    log_entry = json.loads(pubsub_data)
    payload = log_entry.get("jsonPayload", {})

    # Extract feedback details
    message = payload.get("message", "No message")
    origin = payload.get("origin_code", "?")
    dest = payload.get("destination_code", "?")
    screen = payload.get("screen", "unknown")
    device = payload.get("device_model", "unknown")
    train_id = payload.get("train_id") or "N/A"
    timestamp = payload.get("timestamp", "unknown")

    # Build Slack message
    slack_message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📱 User Feedback: {origin} → {dest}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f">{message}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Screen:* {screen} | *Train:* {train_id} | *Device:* {device} | *Time:* {timestamp}",
                    }
                ],
            },
        ]
    }

    # Send to Slack
    webhook_url = get_slack_webhook()
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(slack_message).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req) as response:
        if response.status != 200:
            raise Exception(f"Slack webhook failed: {response.status}")

    print(f"Feedback notification sent: {origin}→{dest}: {message[:50]}...")
