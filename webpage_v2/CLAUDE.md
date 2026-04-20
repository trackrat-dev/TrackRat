# TrackRat Web Frontend (webpage_v2)

> Mobile-first React web application for transit tracking with minimal dependencies and simple polling-based real-time updates.

## Technology Stack

- **Framework**: React 19.2 + TypeScript 6.0 + PWA (vite-plugin-pwa)
- **Build Tool**: Vite 8.0 (fast dev server, optimized builds)
- **Styling**: Tailwind CSS 4.2 (utility-first, custom design system)
- **State Management**: Zustand 5.0 (lightweight, no boilerplate)
- **Routing**: React Router DOM 7.14
- **Date Handling**: date-fns 4.1
- **HTTP Client**: Native `fetch` (no axios)
- **Maps**: MapLibre GL 5.22 + react-map-gl 8.1
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
  - `trackrat:favoriteRoutes` - favorite routes
  - `trackrat:lastRoute` - last selected from/to pair (auto-restored on mount)
  - `trackrat:systems` - enabled transit systems
  - `trackrat:homeStation` - home station for quick access
  - `trackrat:workStation` - work station for quick access
  - `trackrat:tripHistory` - trip search history
- **Pattern**: Store serializes/deserializes, handles errors gracefully

## Design System

### Colors (index.css @theme)
- **Primary**: Brown gradient (`#8B5A3C` → `#D4753E`)
- **Accent**: Burnt orange (`#CC5500`)
- **Background**: Light cream (`#F5F1E8`)
- **Surface**: Darker cream (`#EAE3D2`)
- **Success**: Olive green (`#6B8E23`), **Warning**: Orange (`#D4753E`), **Error**: Dark red (`#A52A2A`)
- **Text**: Warm dark tones (`#2D1B0E` primary, `#4A3728` secondary, `#7B6C5D` muted)

### Glassmorphism Pattern
```tsx
className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl"
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
- **Override**: Set `VITE_API_BASE_URL` env var to use a different base URL (e.g., staging)
- **Cache Duration**: 2 minutes for cacheable endpoints
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
1. `GET /trips/search?from={code}&to={code}&limit=50&hide_departed=true&date={YYYY-MM-DD}` (departure/trip list, optional date)
2. `GET /trains/{trainId}?date={YYYY-MM-DD}` (train details, polled every 30s)
3. `GET /trains/{trainId}/history?days=365&from_station={code}&to_station={code}` (historical performance)
4. `GET /predictions/track?station_code={code}&train_id={id}&journey_date={date}` (optional, fail-silent)
5. `GET /predictions/supported-stations` (cached, determines which stations show predictions)
6. `GET /predictions/delay?train_id={id}&station_code={code}&journey_date={date}` (delay forecast, fail-silent)
7. `GET /routes/summary?scope=route&from_station={code}&to_station={code}` (optional, fail-silent)
8. `GET /routes/summary?scope=network` (network-wide summary for status page)
9. `GET /routes/history?from_station={code}&to_station={code}&data_source={src}&days={n}` (route performance)
10. `GET /routes/congestion` (network congestion, 60s polling on status page)
11. `GET /alerts/service?data_source={src}` (MTA service alerts, cached 2min)
12. `POST /feedback` (user feedback submission)

## Key File Locations

```
webpage_v2/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Layout.tsx       # App shell with header + navigation
│   │   ├── Navigation.tsx   # Bottom tab bar (mobile-first)
│   │   ├── StationPicker.tsx # Searchable station selector (grouped by system)
│   │   ├── TrainCard.tsx    # Departure list item (visual states: departed/boarding/cancelled/scheduled)
│   │   ├── StopCard.tsx     # Individual stop in train details (timing hierarchy)
│   │   ├── TrackPredictionBar.tsx # Track/platform predictions
│   │   ├── ShareButton.tsx  # Web Share API with clipboard fallback
│   │   ├── LoadingSpinner.tsx
│   │   ├── DelayForecastCard.tsx  # Delay/cancellation forecast
│   │   ├── FeedbackModal.tsx     # In-app feedback submission
│   │   ├── HistoricalPerformance.tsx # Train history + track distribution
│   │   ├── ServiceAlertBanner.tsx # MTA service alerts (collapsible)
│   │   ├── TransferTripCard.tsx  # Multi-leg trip result card
│   │   ├── RouteMap.tsx          # MapLibre GL route map
│   │   ├── SimilarTrainsPanel.tsx # Similar trains suggestion panel
│   │   ├── TrainDistributionChart.tsx # Track distribution chart
│   │   ├── UpcomingTrains.tsx    # Upcoming trains widget
│   │   ├── ErrorBoundary.tsx     # React error boundary
│   │   └── ErrorMessage.tsx
│   ├── pages/              # Route components
│   │   ├── LandingPage.tsx        # Marketing landing (/, open-source section, iOS banner)
│   │   ├── TripSelectionPage.tsx  # Station selection (/departures)
│   │   ├── TrainListPage.tsx      # Departures for route (filter, summary, date picker)
│   │   ├── TrainDetailsPage.tsx   # Stop-by-stop view (predictions, history, alerts)
│   │   ├── RouteStatusPage.tsx    # Route performance over time
│   │   ├── NetworkStatusPage.tsx  # System-wide congestion overview
│   │   ├── TripDetailsPage.tsx    # Multi-leg trip details view
│   │   ├── TripHistoryPage.tsx    # Trip search history
│   │   └── FavoritesPage.tsx      # Manage favorite stations
│   ├── services/
│   │   ├── api.ts          # API client with caching
│   │   └── storage.ts      # localStorage wrapper
│   ├── store/
│   │   └── appStore.ts     # Zustand global state
│   ├── data/
│   │   ├── stations.ts     # Static station list (1500+ stations, 11 transit systems)
│   │   └── routeTopology.ts # Route topology for smart search and filtering
│   ├── types/
│   │   └── index.ts        # TypeScript interfaces
│   └── utils/
│       ├── date.ts         # date-fns wrappers
│       ├── formatting.ts   # Status badge classes
│       ├── ratsense.ts     # AI journey predictions (RatSense)
│       ├── routes.ts       # Route path helpers and URL builders
│       ├── share.ts        # Web Share API helper + train URL builder
│       └── trainSearch.ts  # Train search and filtering logic
├── public/                 # Static assets
├── index.html             # SPA entry point
├── vite.config.ts         # Build config (PWA, Workbox, path aliases)
└── src/index.css          # Design system tokens (Tailwind CSS 4 @theme)
```

## Routes

- `/` - Landing page (marketing, open-source info, iOS banner)
- `/departures` - Trip selection (origin + destination pickers, last route restore)
- `/trains/:from/:to` - Train list for route (filter, summary, date picker, alerts)
- `/train/:trainId/:from?/:to?` - Train details (predictions, history, alerts)
- `/trip` - Multi-leg trip details view (transfer connections)
- `/route/:from/:to` - Route performance history (7d/30d/90d)
- `/status` - Network-wide congestion overview by system
- `/favorites` - Manage favorite stations
- `/history` - Trip search history

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
- `formatTimeAgo()` - "2 minutes ago"
- `formatDate()` - "Jan 15, 2025"
- `getDelayMinutes()` - Calculate delay from scheduled vs actual
- `isToday()` - Check if date string is today
- `getTodayDateString()` - "2025-01-15" format

## Key Constraints

### What This App Does NOT Have
- **No WebSocket** - Simple 30-second polling instead
- **No Push Notifications** - Browser notifications not implemented
- **Minimal Maps** - Inline route map via MapLibre GL JS on TrainListPage (CARTO Dark Matter tiles, no API key)
- **No Backend Auth** - Stateless, no user accounts

### Intentional Simplifications
- **Polling over WebSocket**: Simpler, no connection management
- **In-Memory Cache**: No IndexedDB, clears on refresh
- **LocalStorage Only**: No backend user preferences
- **Static Station List**: No dynamic station API calls
- **Minimal Code Splitting**: `React.lazy()` used for heavy components (e.g., RouteMap)

## Data Model

### Station
```typescript
type TransitSystem = 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART' | 'MBTA';

interface Station {
  code: string;           // "NY", "PNK", "S127", etc.
  name: string;           // "New York Penn Station", "Newark PATH"
  system?: TransitSystem; // Transit system this station belongs to
  coordinates?: {         // Optional GPS coordinates
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
  train_position?: { ... };   // Current location (at_station_code, etc.)
  data_freshness: { ... };    // Last updated info
  data_source: TransitSystem;
  observation_type: 'OBSERVED' | 'SCHEDULED';
  is_cancelled: boolean;
}
```

### Stop (Train Details)
```typescript
interface Stop {
  station: StationInfo;
  stop_sequence: number;
  scheduled_arrival?: string;
  scheduled_departure?: string;
  updated_arrival?: string;      // Estimated/updated time from provider
  updated_departure?: string;
  actual_arrival?: string;
  actual_departure?: string;
  predicted_arrival?: string;    // ML-predicted arrival
  predicted_arrival_samples?: number;
  track?: string;
  track_assigned_at?: string;
  has_departed_station: boolean;
}
```

### OperationsSummaryResponse
```typescript
interface OperationsSummaryResponse {
  headline: string;         // Short summary for collapsed view
  body: string;             // Detailed summary (2-4 sentences)
  scope: 'network' | 'route' | 'train';
  time_window_minutes: number;
  data_freshness_seconds: number;
  generated_at: string;
}
```

### PlatformPrediction (Track Predictions)
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

**Framework**: Vitest 4.x + React Testing Library + jsdom

```bash
npm test          # Run all tests once
npm run test:watch  # Watch mode for development
```

**Test files**: Colocated with source (`*.test.ts` next to source file)
**Setup**: `src/test/setup.ts` loads `@testing-library/jest-dom/vitest` matchers

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

- **Bundle Size**: <200KB gzipped (currently ~107KB)
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
1. Update `src/index.css` `@theme` block for colors/spacing
2. Update `src/components/Layout.tsx` for global styles
3. No CSS files needed (Tailwind only)

## Differences from iOS/Android Apps

| Feature | iOS/Android | Web |
|---------|-------------|-----|
| **Real-time Updates** | 30s polling + push | 30s polling |
| **Notifications** | APNs/FCM push | None |
| **Live Activities** | WidgetKit/Widgets | None |
| **Offline Mode** | Core Data cache | PWA service worker (Workbox) |
| **Maps** | MapKit/Google Maps | MapLibre GL (inline route map) |
| **Background Refresh** | Yes | No |
| **Install** | App Store | PWA install prompt |
| **Auth** | Potential | None |
