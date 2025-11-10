# TrackRat Web Frontend - Design Proposal

## Executive Summary

The web version focuses on **essential train search and viewing functionality** with a **mobile-first responsive design**. This stripped-down approach prioritizes speed of delivery and simplicity.

**Target User:** Commuters accessing TrackRat on mobile browsers who want quick train lookup without installing an app.

---

## Core Features (MVP Only)

### ✅ Include

1. **Trip Selection & Search**
   - Origin/destination station selection with search
   - Train number search (both NJT and Amtrak formats)
   - Recent trips (localStorage, max 10)
   - Favorite stations (localStorage, unlimited)

2. **Train List Display**
   - Departures for selected route
   - Auto-refresh every 30 seconds (polling)
   - Manual refresh button
   - Sorted by departure time

3. **Train Details**
   - Stop-by-stop list with scheduled times
   - Actual departure/arrival times when available
   - Delay information
   - Track assignments
   - Train status (scheduled/boarding/departed/delayed)
   - 30-second polling for updates

4. **Basic Real-time Updates**
   - Simple polling (no WebSocket)
   - "Last updated X seconds ago" indicator
   - Manual refresh button

### ❌ Deferred

- Historical performance charts
- Network congestion map
- WebSocket real-time updates
- Browser push notifications
- RatSense AI suggestions
- Interactive maps
- Background tracking
- PWA features (service workers)

---

## Technical Stack

- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **State Management:** Zustand
- **Routing:** React Router v6
- **Date Handling:** date-fns
- **HTTP Client:** fetch (native)
- **Hosting:** Vercel/Netlify

---

## Architecture

### Routes

```
/                          → Home/Trip Selection
/trains/:from/:to         → Train List
/train/:id                → Train Details
/favorites                → Manage Favorites
```

### Component Structure

```
App
├─ Layout
│  └─ Navigation
└─ Routes
   ├─ TripSelectionPage
   │  ├─ StationPicker (origin)
   │  ├─ StationPicker (destination)
   │  ├─ TrainNumberSearch
   │  ├─ RecentTrips
   │  └─ FavoriteStations
   ├─ TrainListPage
   │  ├─ RouteHeader
   │  ├─ RefreshButton
   │  ├─ LastUpdatedIndicator
   │  └─ TrainCard[]
   ├─ TrainDetailsPage
   │  ├─ TrainHeader
   │  ├─ JourneyInfo
   │  ├─ RefreshButton
   │  └─ StopsList
   └─ FavoritesPage
      └─ FavoritesList
```

### State Management (Zustand)

```typescript
interface AppState {
  selectedDeparture: Station | null;
  selectedDestination: Station | null;
  recentTrips: TripPair[];
  favoriteStations: FavoriteStation[];

  setRoute: (from: Station, to: Station) => void;
  addRecentTrip: (trip: TripPair) => void;
  addFavorite: (station: FavoriteStation) => void;
  removeFavorite: (stationId: string) => void;
}
```

---

## Design System

### Colors

- **Primary:** Purple gradient (#667eea → #764ba2)
- **Accent:** Orange (#ff6b35)
- **Background:** Dark (#0a0a0a)
- **Surface:** Dark gray (#1a1a1a) with glassmorphism
- **Text:** White (#ffffff)
- **Success:** Green (#10b981)
- **Warning:** Yellow (#fbbf24)
- **Error:** Red (#ef4444)

### Typography

- **System font:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`
- **Headlines:** 24-28px, semi-bold
- **Body:** 16px, regular
- **Captions:** 12-14px

### Spacing

- 8px grid system (0.5rem = 8px)
- Mobile padding: 16px horizontal, 12px vertical
- Component gaps: 8-16px

### Glassmorphism

```css
background: rgba(26, 26, 26, 0.7);
backdrop-filter: blur(20px);
border: 1px solid rgba(255, 255, 255, 0.1);
border-radius: 16px;
```

---

## API Integration

### Endpoints Used

1. `GET /api/v2/trains/departures?from={code}&to={code}&limit=100`
2. `GET /api/v2/trains/{trainId}?date={YYYY-MM-DD}`
3. `GET /health` (on initialization)

### Polling Strategy

- **Train List:** Poll every 30 seconds
- **Train Details:** Poll every 30 seconds
- **Cache:** 2-minute cache for departures list
- **Error Handling:** Show friendly errors, offer retry

---

## Local Storage Schema

```typescript
// Recent Trips (max 10)
'trackrat:recentTrips': TripPair[]

// Favorite Stations (unlimited)
'trackrat:favorites': FavoriteStation[]

// Last Selected Route
'trackrat:lastRoute': { from: Station, to: Station }
```

---

## Station Data

Convert iOS `Stations.swift` to TypeScript constant (~144 stations, ~20KB).

```typescript
export const STATIONS: Station[] = [
  { code: 'NY', name: 'New York Penn', coordinates: { lat: 40.7506, lon: -73.9935 } },
  // ... 143 more
];
```

---

## Implementation Timeline

### Week 1
- Project setup (Vite + React + TypeScript + Tailwind)
- Design system implementation
- Station data conversion
- Trip selection page (origin/destination pickers, search, recent trips, favorites)

### Week 2
- API client with caching
- Train list page (departures, polling, loading states)
- Train details page (stops, polling, status)
- LocalStorage integration
- Responsive layout
- Error handling
- Deployment

---

## Success Criteria

### Functional
- ✅ Select origin/destination stations
- ✅ View departures for route
- ✅ View detailed stop information
- ✅ Search trains by number
- ✅ Save/view recent trips and favorites
- ✅ Auto-refresh every 30 seconds
- ✅ Manual refresh works

### Performance
- ✅ First Contentful Paint: <2s
- ✅ Time to Interactive: <3s
- ✅ Bundle size: <200KB gzipped
- ✅ Works on 3G networks

### Compatibility
- ✅ iOS Safari 15+
- ✅ Chrome Mobile 100+
- ✅ Firefox Mobile 100+
- ✅ Desktop browsers (latest)

---

## Project Structure

```
webpage_v2/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── Navigation.tsx
│   │   ├── StationPicker.tsx
│   │   ├── TrainCard.tsx
│   │   ├── StopCard.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── ErrorMessage.tsx
│   ├── pages/
│   │   ├── TripSelectionPage.tsx
│   │   ├── TrainListPage.tsx
│   │   ├── TrainDetailsPage.tsx
│   │   └── FavoritesPage.tsx
│   ├── services/
│   │   ├── api.ts
│   │   └── storage.ts
│   ├── store/
│   │   └── appStore.ts
│   ├── data/
│   │   └── stations.ts
│   ├── types/
│   │   └── index.ts
│   ├── utils/
│   │   ├── date.ts
│   │   └── formatting.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── PLAN.md
```

---

## Key Simplifications

| Feature | Original | Simplified |
|---------|----------|------------|
| Real-time | WebSocket | 30s polling |
| Notifications | Browser push | None |
| Maps | Leaflet.js | None |
| Historical | Charts | None |
| Congestion | Network viz | None |
| AI | RatSense | None |
| PWA | Service worker | None |
| Background | Sync | None |

---

## Future Enhancements (Post-MVP)

1. PWA features (service worker, offline)
2. Historical performance charts
3. WebSocket real-time updates
4. Network congestion visualization
5. RatSense Lite (recent trip suggestions)

---

## Next Steps

1. ✅ Set up Vite + React + TypeScript + Tailwind
2. ✅ Extract station data from iOS app
3. ✅ Implement design system
4. ✅ Build core pages
5. ✅ Deploy to Vercel/Netlify
6. ✅ Test on mobile devices
