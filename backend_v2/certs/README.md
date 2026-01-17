# APNS Certificates

Place your Apple Push Notification Service (APNS) auth key file here.

## File naming

Name your key file `apns_auth_key.p8` (or configure `APNS_AUTH_KEY_PATH` env var).

## How to obtain

1. Go to [Apple Developer > Keys](https://developer.apple.com/account/resources/authkeys/list)
2. Create a new key with "Apple Push Notifications service (APNs)" enabled
3. Download the `.p8` file
4. Note the Key ID (shown after creation)

## Required environment variables

```bash
APNS_TEAM_ID=your_team_id
APNS_KEY_ID=your_key_id
APNS_AUTH_KEY_PATH=certs/apns_auth_key.p8
APNS_BUNDLE_ID=your.app.bundle.id
APNS_ENVIRONMENT=dev  # or "prod" for production
```

## Note

APNS is optional. The app works without push notifications - Live Activities will still function locally on the device.
