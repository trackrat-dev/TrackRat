# TrackRat Web Frontend (webpage_v2)

> Mobile-first React web application for transit tracking with minimal dependencies and simple polling-based real-time updates.

## Technology Stack

- **Framework**: React 19.2 + TypeScript 5.5 + PWA (vite-plugin-pwa)
- **Build Tool**: Vite 7.3 (fast dev server, optimized builds)
- **Styling**: Tailwind CSS 4.1 (utility-first, custom design system)
- **State Management**: Zustand 5.0 (lightweight, no boilerplate)
- **Routing**: React Router DOM 7.13
- **Date Handling**: date-fns 4.1
- **HTTP Client**: Native `fetch` (no axios)
- **Deployment**: GCS static hosting (`scripts/deploy-webpage.sh`)

## Architecture Patterns

### State Management (Zustand)
- **Global Store**: `src/store/appStore.ts` - single store for entire app
- **Pattern**: Direct state mutations via actions (no reducers)
- **Persistence**: Syncs with localStorage via `storageService`
- **No Props Drilling**: Components access store directly via `useAppStore` hook

### Component Structure
- **Functional Components**: All components use hooks (no class components)
- **Colocation**: Keep related logic together (no separate files for hooks)
- **Composition**: Small, focused components composed into pages
- **No Component Libraries**: All UI components are custom-built

### Data Flow
```
API Service (fetch + cache)
  → Component (useEffect polling)
  → Local State (useState)
  → Render
```

### LocalStorage Persistence
- **Service**: `src/services/storage.ts` (singleton pattern)
- **Keys**:
  - `trackrat:recentTrips` - last 10 trips, sorted by usage
  - `trackrat:favorites` - favorite stations, sorted by date added
  - `trackrat:lastRoute` - last selected from/to pair
- **Pattern**: Store serializes/deserializes, handles errors gracefully

## Design System

### Colors (tailwind.config.js)
- **Primary**: Purple gradient (`#667eea` → `#764ba2`)
- **Accent**: Orange (`#ff6b35`)
- **Background**: Near-black (`#0a0a0a`)
- **Surface**: Dark gray (`#1a1a1a`)
- **Status**: Success green, warning yellow, error red

### Glassmorphism Pattern
```tsx
className="bg-surface/80 backdrop-blur-xl border border-white/10 rounded-2xl"
```

### Typography
- System font stack (Apple → Segoe → Roboto fallback)
- Headlines: 24-28px, semi-bold
- Body: 16px base
- Mobile-first sizing

### Spacing
- 8px grid system (Tailwind's default)
- Consistent padding: `px-4 py-3` for cards
- Gap utilities: `gap-2`, `gap-4` for flex/grid

## API Integration

### Base Configuration (src/services/api.ts)
- **Production**: `https://apiv2.trackrat.net/api/v2`
- **Staging**: Not used in web (iOS uses staging)
- **Cache Duration**: 2 minutes for departure lists
- **Cache Strategy**: In-memory Map with timestamp checks

### Polling Pattern
```tsx
useEffect(() => {
  const fetchData = async () => { /* ... */ };
  fetchData();
  const interval = setInterval(fetchData, 30000); // 30s
  return () => clearInterval(interval);
}, [dependencies]);
```

### Error Handling
- Try/catch in API service
- Graceful degradation (show cached data if available)
- User-friendly error messages via `ErrorMessage` component

### Endpoints Used
1. `GET /trains/departures?from={code}&to={code}&limit=100`
2. `GET /trains/{trainId}?date={YYYY-MM-DD}`
3. `GET /predictions/track?station_code={code}&train_id={id}&journey_date={date}` (optional)
4. `GET /health` (not actively used)

## Key File Locations

```
webpage_v2/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Layout.tsx       # App shell with header + navigation
│   │   ├── Navigation.tsx   # Bottom tab bar (mobile-first)
│   │   ├── StationPicker.tsx # Searchable station selector
│   │   ├── TrainCard.tsx    # Departure list item
│   │   ├── StopCard.tsx     # Individual stop in train details
│   │   ├── TrackPredictionBar.tsx # ML platform predictions
│   │   ├── LoadingSpinner.tsx
│   │   └── ErrorMessage.tsx
│   ├── pages/              # Route components
│   │   ├── TripSelectionPage.tsx  # Home / station selection
│   │   ├── TrainListPage.tsx      # Departures for route
│   │   ├── TrainDetailsPage.tsx   # Stop-by-stop view
│   │   └── FavoritesPage.tsx      # Manage favorites
│   ├── services/
│   │   ├── api.ts          # API client with caching
│   │   └── storage.ts      # localStorage wrapper
│   ├── store/
│   │   └── appStore.ts     # Zustand global state
│   ├── data/
│   │   └── stations.ts     # Static station list (250+ stations)
│   ├── types/
│   │   └── index.ts        # TypeScript interfaces
│   └── utils/
│       ├── date.ts         # date-fns wrappers
│       └── formatting.ts   # Text/color utilities
├── public/                 # Static assets
├── index.html             # SPA entry point
├── vite.config.ts         # Build config (PWA, Workbox, path aliases)
└── tailwind.config.js     # Design system tokens
```

## Routes

- `/` - Trip selection (origin + destination pickers)
- `/trains/:from/:to` - Train list for route
- `/train/:trainId/:from?/:to?` - Train details with stops
- `/favorites` - Manage favorite stations

**Base Path**: `/` (hosted at `trackrat.net`)

## Development Workflow

### Local Development
```bash
cd webpage_v2
npm install
npm run dev        # Starts on http://localhost:3000
```

### Building
```bash
npm run build      # TypeScript compile + Vite build
npm run preview    # Preview production build locally
```

### Deployment
- **Manual**: Run `./scripts/deploy-webpage.sh` from repo root
- **Dry run**: `./scripts/deploy-webpage.sh --dry-run` to preview changes
- **Target**: `gs://trackrat-links-2caf78c68fded156/` → `https://trackrat.net`
- **Cache**: `index.html` and service worker get `no-cache`; hashed assets get `max-age=1yr`

## Common Patterns

### Fetching Train Data
```tsx
const [trains, setTrains] = useState<Train[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  const fetchTrains = async () => {
    try {
      setLoading(true);
      const data = await apiService.getDepartures(from, to);
      setTrains(data.departures);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  fetchTrains();
  const interval = setInterval(fetchTrains, 30000);
  return () => clearInterval(interval);
}, [from, to]);
```

### Status Badge Colors
Use `getStatusBadgeClass()` from `utils/formatting.ts`:
- Scheduled → Green
- Boarding → Orange
- Departed → Blue
- Delayed → Yellow
- Cancelled → Red

### Time Formatting
- `formatTime()` - "3:45 PM"
- `formatDateTime()` - "Jan 15, 3:45 PM"
- `formatTimeAgo()` - "2 minutes ago"
- `getDelayMinutes()` - Calculate delay from scheduled vs actual

## Key Constraints

### What This App Does NOT Have
- **No WebSocket** - Simple 30-second polling instead
- **No Push Notifications** - Browser notifications not implemented
- **No Maps** - No Leaflet/Mapbox integration
- **No Charts** - No historical performance visualization
- **No Backend Auth** - Stateless, no user accounts

### Intentional Simplifications
- **Polling over WebSocket**: Simpler, no connection management
- **In-Memory Cache**: No IndexedDB, clears on refresh
- **LocalStorage Only**: No backend user preferences
- **Static Station List**: No dynamic station API calls
- **No Code Splitting**: Small enough to ship as single bundle

## Data Model

### Station
```typescript
interface Station {
  code: string;        // "NY", "PJ", etc.
  name: string;        // "New York Penn", "Secaucus Junction"
  coordinates?: {      // Optional GPS coordinates
    lat: number;
    lon: number;
  };
}
```

### Train (Departure List)
```typescript
interface Train {
  train_id: string;           // "3515" or "A2121"
  journey_date: string;       // "2025-01-15"
  line: LineInfo;             // { code, name, color }
  destination: string;        // Terminal station name
  departure: StationTiming;   // Origin timing
  arrival: StationTiming;     // Destination timing
  train_position?: { ... };   // Current location
  data_freshness: { ... };    // Last updated info
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR';
  observation_type: 'OBSERVED' | 'SCHEDULED';
  is_cancelled: boolean;
}
```

### TrainDetails (Full Journey)
```typescript
interface TrainDetails {
  train_id: string;
  journey_date: string;
  line: LineInfo;
  route: TrainRoute;
  train_position?: { ... };
  stops: Stop[];              // All stops on route
  data_freshness: { ... };
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR';
  is_cancelled: boolean;
  is_completed: boolean;
}
```

### PlatformPrediction (ML Track Predictions)
```typescript
interface PlatformPrediction {
  platform_probabilities: Record<string, number>; // "1": 0.85
  primary_prediction: string;                     // "1"
  confidence: number;                             // 0.85
  top_3: string[];                                // ["1", "2", "3"]
  model_version: string;
  station_code: string;
  train_id: string;
}
```

## Testing

**Current Status**: No automated tests (MVP phase)

**Future**: Add Vitest for unit tests, React Testing Library for components

## Naming Conventions

- **Files**: PascalCase for components (`TrainCard.tsx`), camelCase for utils (`date.ts`)
- **Components**: PascalCase (`StationPicker`, `TrainDetailsPage`)
- **Functions**: camelCase (`formatTime`, `getDepartures`)
- **Types**: PascalCase (`Train`, `Station`, `DeparturesResponse`)
- **CSS Classes**: Tailwind utilities only (no custom classes)

## Mobile-First Approach

- Design for 375px viewport first (iPhone SE)
- Bottom navigation (not top tabs)
- Large touch targets (min 44px height)
- Sticky headers on scroll
- Safe area insets for notched devices

## Performance Targets

- **Bundle Size**: <200KB gzipped (currently ~150KB)
- **First Contentful Paint**: <2s
- **Time to Interactive**: <3s
- **3G Network**: App remains usable on slow connections
- **Cache Hit Rate**: ~80% on typical usage (2min cache)

## Common Tasks

### Add a New Page
1. Create component in `src/pages/NewPage.tsx`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/Navigation.tsx`

### Add a New API Endpoint
1. Define types in `src/types/index.ts`
2. Add method to `APIService` class in `src/services/api.ts`
3. Use in component via `apiService.methodName()`

### Modify Design System
1. Update `tailwind.config.js` for colors/spacing
2. Update `src/components/Layout.tsx` for global styles
3. No CSS files needed (Tailwind only)

### Debug Polling Issues
1. Check browser console for API errors
2. Use `apiService.getCacheAge(url)` to verify cache
3. Clear cache with `apiService.clearCache()`
4. Verify interval cleanup in useEffect return

## Differences from iOS/Android Apps

| Feature | iOS/Android | Web |
|---------|-------------|-----|
| **Real-time Updates** | 30s polling + push | 30s polling |
| **Notifications** | APNs/FCM push | None |
| **Live Activities** | WidgetKit/Widgets | None |
| **Offline Mode** | Core Data cache | PWA service worker (Workbox) |
| **Maps** | MapKit/Google Maps | None |
| **Background Refresh** | Yes | No |
| **Install** | App Store | PWA install prompt |
| **Auth** | Potential | None |

## Future Enhancements (Not Planned for MVP)

- WebSocket for real-time updates
- Browser push notifications
- Historical performance charts
- Network congestion visualization
- Code splitting for faster initial load
- Automated testing suite
