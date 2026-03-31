# Universal Links Setup for TrackRat

This document explains how to set up Universal Links for TrackRat train sharing functionality.

## Overview

TrackRat now supports sharing trains via Universal Links that work whether the app is installed or not:

- **URL Format**: `https://trackrat.net/train/{train_id}?date=YYYY-MM-DD&from={station_code}&to={station_code}`
- **Example**: `https://trackrat.net/train/NJT-3849?date=2025-01-14&from=NY&to=TR`

## Server Setup Required

### 1. Host the Apple App Site Association File

Upload `apple-app-site-association` to your web server at:
```
https://trackrat.net/.well-known/apple-app-site-association
```

**Important**: 
- Must be served with HTTPS
- Content-Type: `application/json`
- No file extension
- Team ID already configured: `D5RZZ55J9R`

### 2. Host the Web Fallback Page

Upload `web-fallback.html` to handle train URLs when the app isn't installed:
```
https://trackrat.net/train/{train_id}
```

This page will:
- Display train information from the URL
- Attempt to open the TrackRat app automatically on iOS
- Show App Store link if app isn't installed
- Provide manual "Open in TrackRat" button

### 3. Server Configuration

Your web server needs to handle these routes:

```nginx
# Nginx configuration example
server {
    listen 443 ssl;
    server_name trackrat.net www.trackrat.net;
    
    # Apple App Site Association
    location /.well-known/apple-app-site-association {
        return 200 '{
            "applinks": {
                "details": [{
                    "appIDs": ["D5RZZ55J9R.net.trackrat.TrackRat"],
                    "components": [{
                        "path": "/train/*",
                        "comment": "Train details sharing"
                    }]
                }]
            }
        }';
        add_header Content-Type application/json;
    }
    
    # Train sharing pages
    location ~* ^/train/(.+)$ {
        try_files $uri /web-fallback.html;
    }
    
    # Root redirect to App Store
    location = / {
        return 302 https://apps.apple.com/app/trackrat/id123456789;
    }
}
```

### 4. DNS Configuration

Ensure your domain points to the web server:
```
trackrat.net        A    YOUR_SERVER_IP
www.trackrat.net    A    YOUR_SERVER_IP
```

## Testing Universal Links

### 1. Validate Apple App Site Association

Use Apple's validator:
```
https://search.developer.apple.com/appsearch-validation-tool/
```

Enter: `https://trackrat.net`

### 2. Test on Device

1. **With App Installed**:
   - Tap link in Messages/Safari → Opens TrackRat app directly
   - Long press link → Shows "Open in TrackRat" option

2. **Without App Installed**:
   - Tap link → Opens web fallback page
   - Shows train info and App Store link

### 3. Test URL Schemes

For testing during development:
```
trackrat://train/NJT-3849?from=NY&to=TR
```

## Implementation Details

### iOS App Changes

1. **Added Universal Links Support**:
   - Associated Domains entitlement
   - URL handling in `TrackRatApp.swift`
   - Deep link parsing in `DeepLinkService`

2. **Share Button Added**:
   - In train details view navigation bar
   - Generates URLs with context (origin, destination, date)
   - Uses native iOS share sheet

3. **Fallback Support**:
   - Custom URL scheme (`trackrat://`) as backup
   - Both schemes use same URL structure

### URL Structure

- **Path**: `/train/{train_id}`
- **Query Parameters**:
  - `date`: YYYY-MM-DD format (Eastern Time)
  - `from`: Origin station code (NY, NP, TR, PJ, MP)
  - `to`: Destination station code

### Security Considerations

- No sensitive data in URLs
- Train IDs are public information
- Date parameter for context only
- Rate limiting recommended on web server

## Troubleshooting

### Universal Links Not Working

1. **Check AASA file**:
   ```bash
   curl -I https://trackrat.net/.well-known/apple-app-site-association
   ```
   - Should return 200 status
   - Content-Type: application/json

2. **Verify Team ID**:
   - Team ID is configured as D5RZZ55J9R
   - Matches your Apple Developer account

3. **Clear iOS Cache**:
   - Uninstall and reinstall app
   - iOS caches AASA files

### Custom URL Scheme Issues

1. **Check Info.plist**:
   - Verify `CFBundleURLSchemes` contains `trackrat`

2. **Test from Safari**:
   - Type `trackrat://train/123` in address bar
   - Should show "Open in TrackRat" dialog

### Web Fallback Problems

1. **Check server routing**:
   - Ensure `/train/*` routes to fallback page
   - Verify HTTPS certificate

2. **JavaScript errors**:
   - Check browser console
   - Verify URL parsing logic

## Next Steps

1. **Deploy to Production**:
   - Team ID already configured (D5RZZ55J9R)
   - Configure production domain
   - Test with App Store build

2. **Monitor Usage**:
   - Add analytics to web fallback
   - Track conversion rates
   - Monitor error rates

3. **Future Enhancements**:
   - Rich link previews (Open Graph meta tags)
   - Social sharing optimizations
   - Deep link analytics