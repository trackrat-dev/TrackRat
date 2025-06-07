# TrackRat Web App Guide for Claude

This file provides specific guidance for Claude Code when working with the TrackRat web application component.

## Overview

The TrackRat web app is a responsive, mobile-first web application that provides core train tracking functionality without the complexity of Live Activities or push notifications. It serves as a cross-platform alternative to the iOS app, accessible on any device with a web browser.

## Architecture

### Core Technologies
- **HTML5**: Semantic structure with accessibility considerations
- **CSS3**: Modern responsive design with glassmorphism effects
- **Vanilla JavaScript**: No external dependencies, ES6+ syntax
- **Python Proxy**: Development server for CORS handling (proxy.py)

### Design Philosophy
- **Mobile-first**: Optimized primarily for mobile devices
- **Responsive**: Works across all screen sizes (320px to 1200px+)
- **Progressive Enhancement**: Core functionality works without JavaScript
- **No Dependencies**: Zero external libraries or frameworks
- **Privacy-focused**: No tracking, minimal local storage usage

## File Structure

```
webpage/
├── index.html          # Main application structure
├── script.js           # Core application logic
├── styles.css          # Responsive styling and animations
├── proxy.py            # Development proxy server
├── owl-outline.svg     # Logo/background image
├── V2_DESIGN_PLAN.md   # Implementation plan documentation
└── CLAUDE.md           # This file
```

## Key Features

### Core Functionality
1. **Station Selection**: Choose departure station from 5 major stations
2. **Destination Search**: Autocomplete search for destination stations
3. **Train Listing**: Real-time train schedules with boarding indicators
4. **Train Details**: Comprehensive train information with progress tracking
5. **Historical Data**: Past performance analysis for reliability insights

### Enhanced Features (V2)
1. **Status Resolution**: Uses `status_v2` with fallback to legacy `status`
2. **Train Consolidation**: Automatically enabled via `?consolidate=true`
3. **Progress Visualization**: Journey completion bars and time-to-arrival
4. **Prominent Boarding Alerts**: Animated indicators for boarding trains
5. **Eastern Time Handling**: Proper timezone display throughout

## API Integration

### Base Configuration
```javascript
apiBaseUrl: '/api'  // Proxied through proxy.py in development
```

### Key API Patterns
All API calls include:
- `from_station_code`: Origin station context
- `consolidate=true`: Enable train consolidation
- Proper error handling with fallbacks

### Critical Endpoints
```javascript
// Train search with consolidation
GET /api/trains/?from_station_code=NY&to_station_code=PHL&departure_time_after=2024-01-01T12:00:00&consolidate=true

// Train details with context
GET /api/trains/123?from_station_code=NY&consolidate=true

// Historical data
GET /api/trains/?train_id=ABC123&from_station_code=NY&consolidate=true&no_pagination=true
```

## Data Model Usage

### Train Object Handling
```javascript
// Always use effective status with fallback
const effectiveStatus = train.status_v2 || train.status;

// Progress visualization when available
if (train.progress) {
    // Display journey completion, stops completed, time to arrival
}

// Proper time formatting in Eastern Time
const formattedTime = this.formatTimeInEastern(train.departure_time);
```

### Station Code Mapping
Comprehensive mapping of station names to codes:
- Major stations: NY, NP, TR, PJ, MP
- Extended Amtrak network: 200+ stations supported
- Consistent with backend and iOS implementations

## UI/UX Design

### Visual Design
- **Glassmorphism**: Translucent backgrounds with blur effects
- **Gradient Background**: Purple gradient with owl logo overlay
- **Responsive Typography**: Scales appropriately across devices
- **Color Scheme**: Consistent with brand (oranges, purples, whites)

### Responsive Breakpoints
```css
/* Mobile First (≤480px) */
/* Tablet (481px - 767px) */
/* Desktop (≥768px) */
```

### Key Visual Elements
1. **Boarding Indicators**: Animated orange glow with "BOARDING NOW" badge
2. **Progress Bars**: Green gradient bars showing journey completion
3. **Status Colors**: Consistent color coding for train statuses
4. **Touch Targets**: Minimum 44px for mobile accessibility

## State Management

### Application State
```javascript
class NYPScout {
    currentScreen: 'departure-screen' | 'main-screen' | 'leaving-soon-screen' | ...
    selectedDestination: string | null
    selectedDeparture: string | null
    departureStationCode: string | null
    currentTrainId: string | null
}
```

### Local Storage Usage
- **Recent Destinations**: Maximum 5 recent searches
- **No Personal Data**: Privacy-first approach
- **Automatic Cleanup**: Old data removed automatically

## Performance Considerations

### Optimization Strategies
1. **Minimal DOM Manipulation**: Direct innerHTML updates
2. **Efficient Polling**: 30-second intervals for real-time updates
3. **Debounced Search**: Autocomplete with input debouncing
4. **Image Optimization**: SVG icons and logos
5. **CSS Animation**: Hardware-accelerated transforms

### Network Efficiency
- **Consolidated API Calls**: Reduce redundant requests
- **Error Recovery**: Automatic retry with exponential backoff
- **Graceful Degradation**: Functionality without real-time updates

## Mobile Considerations

### Touch Interface
- **Large Touch Targets**: Minimum 44px for buttons
- **Gesture Support**: Swipe and tap interactions
- **Viewport Optimization**: Proper meta viewport configuration

### Performance on Mobile
- **Battery Efficiency**: Reasonable polling intervals
- **Network Awareness**: Minimal data usage
- **Smooth Animations**: 60fps animations where possible

## Testing Strategy

### Development Testing
```bash
# Start backend API
cd backend && trackcast start-api

# Start web proxy
cd webpage && python proxy.py

# Test at http://localhost:9998
```

### Cross-Device Testing
1. **Chrome DevTools**: Mobile simulation
2. **Real Devices**: iOS Safari, Android Chrome
3. **Different Networks**: WiFi, 4G, slow connections
4. **Screen Orientations**: Portrait and landscape

### Browser Compatibility
- **Modern Browsers**: Chrome 90+, Safari 14+, Firefox 88+
- **Mobile Browsers**: iOS Safari, Chrome Mobile, Samsung Internet
- **Feature Detection**: Graceful fallbacks for older browsers

## Error Handling

### API Error Recovery
```javascript
// Graceful degradation for API failures
try {
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error('API request failed');
    // Handle success
} catch (error) {
    // Display user-friendly error message
    // Retry with exponential backoff
}
```

### User Experience During Errors
1. **Clear Error Messages**: User-friendly explanations
2. **Retry Mechanisms**: Automatic and manual retry options
3. **Fallback Content**: Show cached data when possible
4. **Loading States**: Clear feedback during operations

## Accessibility

### WCAG Compliance
- **Semantic HTML**: Proper heading hierarchy and landmarks
- **Keyboard Navigation**: Full functionality via keyboard
- **Color Contrast**: Minimum 4.5:1 ratio for text
- **Screen Reader Support**: ARIA labels and descriptions

### Mobile Accessibility
- **Touch Target Size**: Minimum 44px for interactive elements
- **Zoom Support**: Works up to 200% zoom
- **Voice Control**: Compatible with voice navigation

## Security Considerations

### Data Privacy
- **No User Tracking**: No analytics or tracking scripts
- **Minimal Data Storage**: Only recent destinations in localStorage
- **No Third-Party Dependencies**: Eliminates supply chain risks

### API Security
- **HTTPS Only**: All production API calls over HTTPS
- **No Credentials**: Stateless API, no authentication required
- **Input Validation**: Sanitize all user inputs

## Development Workflow

### Code Style Guidelines
```javascript
// Use modern ES6+ syntax
const trains = await this.fetchTrains();

// Consistent naming conventions
getEffectiveStatus(train)
formatTimeInEastern(dateString)

// Minimal DOM manipulation
element.innerHTML = this.generateTrainHTML(train);
```

### CSS Conventions
```css
/* Mobile-first media queries */
@media (min-width: 481px) { /* Tablet styles */ }
@media (min-width: 768px) { /* Desktop styles */ }

/* BEM-style naming for complex components */
.train-item--boarding
.progress-bar__fill
```

## Deployment

### Development
- Use `proxy.py` for local development
- Backend must be running on port 8000
- Web app served on port 9998

### Production
- Serve static files from any web server
- Proxy `/api/*` requests to backend server
- Ensure proper CORS headers
- Enable HTTPS and compression

### Environment Configuration
```javascript
// Development
apiBaseUrl: '/api'  // Proxied by proxy.py

// Production
apiBaseUrl: 'https://trackcast.andymartin.cc/api'
```

## Common Issues and Solutions

### CORS Issues
- **Development**: Use proxy.py to handle CORS
- **Production**: Configure server to include proper headers

### Mobile Safari Issues
- **Viewport Zoom**: Disable zoom on input focus if needed
- **Touch Delays**: Use `touch-action: manipulation`
- **Smooth Scrolling**: Test momentum scrolling

### Performance Issues
- **Large Station Lists**: Consider virtualization for very long lists
- **Memory Leaks**: Clear intervals and event listeners properly
- **Render Blocking**: Minimize synchronous operations

## Future Enhancements

### Progressive Web App
- **Service Worker**: Offline caching of core functionality
- **App Manifest**: Installation prompt for home screen
- **Push Notifications**: Web-based notifications for boarding alerts

### Advanced Features
- **Geolocation**: Auto-detect nearest station
- **Dark Mode**: Automatic theme switching
- **Voice Search**: Speech-to-text for destination input
- **Offline Mode**: Basic functionality without network

## Integration with Other Platforms

### API Consistency
- Uses same endpoints as iOS app
- Handles same data models and formats
- Consistent error handling patterns

### Feature Parity
- **Core Features**: All essential functionality from iOS
- **Simplified Features**: No Live Activities or push notifications
- **Enhanced Web Features**: Better keyboard navigation, URL sharing

### Data Synchronization
- **No Cross-Device Sync**: Each browser instance is independent
- **Consistent Data**: Same real-time data as iOS app
- **URL Sharing**: Future capability for sharing specific trains

## Best Practices

### When Adding New Features
1. **Mobile First**: Design for smallest screens first
2. **Progressive Enhancement**: Core functionality without JavaScript
3. **Performance Budget**: Keep bundle size minimal
4. **Accessibility**: Test with screen readers and keyboard navigation
5. **Error Handling**: Graceful fallbacks for all failure modes

### Code Maintenance
1. **No Dependencies**: Avoid adding external libraries
2. **Vanilla JavaScript**: Keep using plain JavaScript
3. **CSS Variables**: Use custom properties for theming
4. **Documentation**: Update this file for major changes

### Testing Requirements
1. **Cross-Browser**: Test in major browsers
2. **Mobile Devices**: Test on real devices
3. **Network Conditions**: Test with slow connections
4. **Edge Cases**: Test error scenarios and edge cases

Remember: The web app should feel like a native mobile app while maintaining broad compatibility and excellent performance across all devices and network conditions.