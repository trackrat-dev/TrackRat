"""Cloud Function to notify when users follow trains via Live Activity."""

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


def notify_train_follow(event, context):
    """Triggered by Pub/Sub when user follows a train."""
    # Decode the Pub/Sub message
    pubsub_data = base64.b64decode(event["data"]).decode("utf-8")
    log_entry = json.loads(pubsub_data)
    payload = log_entry.get("jsonPayload", {})

    # Extract train follow details
    train = payload.get("train_number", "?")
    origin = payload.get("origin", "?")
    dest = payload.get("destination", "?")

    # Build Slack message
    slack_message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":steam_locomotive: *Train {train}* followed: {origin} -> {dest}",
                },
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

    print(f"Train follow notification sent: {train} ({origin}->{dest})")
