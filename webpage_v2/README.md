# TrackRat Web

A mobile-first web application for tracking trains across 11 transit systems (NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway, BART, MBTA, Metra, WMATA) in real-time.

## Features

- Real-time train departures and details
- Search trains by origin and destination across 11 transit systems
- 1,500+ stations with system-grouped picker
- Visual train states: departed (dimmed), boarding (highlighted), cancelled (strikethrough), scheduled
- Train number filter on departure list
- Route operations summary
- Track/platform predictions
- Stop timing hierarchy (actual > updated > scheduled) with predicted arrivals
- Favorite stations for quick access
- Last route auto-restoration
- Data freshness indicators and journey date display
- iOS smart app banner
- Mobile-first warm light theme with glassmorphism UI
- Auto-refresh every 30 seconds
- PWA support (installable, offline-capable)
- Web Share API for sharing train links

## Tech Stack

- React 19 + TypeScript
- Vite 8 (build tool)
- Tailwind CSS 4 (styling)
- Zustand 5 (state management)
- React Router v7 (routing)
- date-fns 4 (date formatting)

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── components/       # Reusable UI components
├── pages/           # Page components (Landing, TripSelection, TrainList, TrainDetails, TripDetails, TripHistory, RouteStatus, NetworkStatus, Favorites)
├── services/        # API client (with caching) and localStorage wrapper
├── store/           # Zustand global state
├── types/           # TypeScript type definitions
├── utils/           # Date formatting, status badges, share helpers
├── data/            # Station data and route topology (1,500+ stations, 11 transit systems)
├── App.tsx          # Main app component with route definitions
├── main.tsx         # Entry point
└── index.css        # Global styles
```

## API

The app connects to the TrackRat backend API at `https://apiv2.trackrat.net/api/v2`.

### Key Endpoints

- `GET /trips/search` - Search trips between stations (primary departure endpoint)
- `GET /trains/{id}` - Get train details with all stops
- `GET /predictions/track` - Track/platform predictions
- `GET /routes/summary` - Route operations summary

## Development

### Code Style

- TypeScript with strict mode
- Functional React components with hooks
- Tailwind CSS for styling (no custom CSS classes)
- ESLint for code quality

### Key Patterns

- **State Management**: Zustand for global state with localStorage persistence
- **Data Fetching**: Custom API service with in-memory caching (2min TTL)
- **Routing**: React Router v7 with type-safe routes
- **Styling**: Tailwind CSS with glassmorphism effects
- **Sharing**: Web Share API with clipboard fallback

## Deployment

Deployed to Google Cloud Storage as a static site.

**Live URL:** https://trackrat.net

```bash
# Deploy from repo root
./scripts/deploy-webpage.sh

# Dry run
./scripts/deploy-webpage.sh --dry-run
```

The deploy script syncs the `dist/` build output to GCS with appropriate cache headers (`no-cache` for `index.html` and service worker, `max-age=1yr` for hashed assets).

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](../LICENSE) for details.
