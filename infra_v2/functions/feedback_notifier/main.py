"""Cloud Function to send user feedback notifications to Slack and create GitHub issues."""

import base64
import json
import urllib.error
import urllib.request


def get_secret(secret_id):
    """Retrieve a secret from Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/trackrat-v2/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def format_github_issue(payload):
    """Format feedback payload into a GitHub issue title and body.

    Returns (title, body) tuple.
    """
    message = payload.get("message", "No message")
    origin = payload.get("origin_code", "?")
    dest = payload.get("destination_code", "?")
    screen = payload.get("screen", "unknown")
    device = payload.get("device_model", "unknown")
    train_id = payload.get("train_id") or "N/A"
    app_version = payload.get("app_version") or "unknown"
    timestamp = payload.get("timestamp", "unknown")

    is_suggestion = message.startswith("[Improvement Suggestion] ")
    if is_suggestion:
        display_message = message[len("[Improvement Suggestion] "):]
        heading = "Improvement Suggestion"
    else:
        display_message = message
        heading = "Issue Report"

    title_msg = display_message[:80].replace("\n", " ")
    if len(display_message) > 80:
        title_msg += "..."

    route = f"{origin} → {dest}" if origin != "?" or dest != "?" else "N/A"

    title = f"[User Feedback] {title_msg}"

    body = "\n".join([
        f"## {heading}",
        "",
        f"> {display_message}",
        "",
        "### Context",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Route** | {route} |",
        f"| **Screen** | {screen} |",
        f"| **Train** | {train_id} |",
        f"| **Device** | {device} |",
        f"| **App Version** | {app_version} |",
        f"| **Submitted** | {timestamp} |",
        "",
        "---",
        "*Automatically created from in-app feedback.*",
    ])

    return title, body


# Bounded timeout keeps GitHub creation non-fatal: a stalled request can't
# outlast the Cloud Function and trigger a Pub/Sub retry that would duplicate
# the Slack post (and potentially the GitHub issue).
GITHUB_API_TIMEOUT_SECONDS = 10


def create_github_issue(token, title, body):
    """Create a GitHub issue in the trackrat-dev/TrackRat repository.

    Returns the HTML URL of the created issue.
    """
    url = "https://api.github.com/repos/trackrat-dev/TrackRat/issues"
    data = json.dumps({"title": title, "body": body, "labels": ["user-feedback"]})
    req = urllib.request.Request(
        url,
        data=data.encode("utf-8"),
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "User-Agent": "TrackRat-Feedback-Notifier",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=GITHUB_API_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("html_url")
    except urllib.error.HTTPError as e:
        if e.code == 422:
            # Label might not exist — retry without labels
            data = json.dumps({"title": title, "body": body})
            req = urllib.request.Request(
                url,
                data=data.encode("utf-8"),
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": f"token {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "TrackRat-Feedback-Notifier",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=GITHUB_API_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("html_url")
        raise


def notify_feedback(event, context):
    """Triggered by Pub/Sub when user feedback is submitted."""
    pubsub_data = base64.b64decode(event["data"]).decode("utf-8")
    log_entry = json.loads(pubsub_data)
    payload = log_entry.get("jsonPayload", {})

    message = payload.get("message", "No message")
    origin = payload.get("origin_code", "?")
    dest = payload.get("destination_code", "?")
    screen = payload.get("screen", "unknown")
    device = payload.get("device_model", "unknown")
    train_id = payload.get("train_id") or "N/A"
    timestamp = payload.get("timestamp", "unknown")

    # Send Slack notification
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

    webhook_url = get_secret("slack-feedback-webhook")
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

    # Create GitHub issue
    try:
        github_token = get_secret("github-feedback-token")
        title, body = format_github_issue(payload)
        issue_url = create_github_issue(github_token, title, body)
        print(f"GitHub issue created: {issue_url}")
    except Exception as e:
        # Non-fatal: Slack notification already succeeded
        print(f"Failed to create GitHub issue: {e}")
