# TrackRat Web

A mobile-first web application for tracking NJ Transit and Amtrak trains in real-time.

## Features

- 🚂 Real-time train departures and details
- 🔍 Search trains by origin and destination
- ⭐ Favorite stations for quick access
- 📱 Mobile-first responsive design
- 🎨 Dark mode with glassmorphism UI
- 🔄 Auto-refresh every 30 seconds

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Zustand (state management)
- React Router v6 (routing)
- date-fns (date formatting)

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
├── pages/           # Page components
├── services/        # API and storage services
├── store/           # Zustand state management
├── types/           # TypeScript type definitions
├── utils/           # Utility functions
├── data/            # Station data
├── App.tsx          # Main app component
├── main.tsx         # Entry point
└── index.css        # Global styles
```

## API

The app connects to the TrackRat backend API at `https://prod.api.trackrat.net/api/v2`.

### Key Endpoints

- `GET /trains/departures` - Get train departures
- `GET /trains/{id}` - Get train details
- `GET /health` - Health check

## Development

### Code Style

- TypeScript with strict mode
- Functional React components with hooks
- Tailwind CSS for styling
- ESLint for code quality

### Key Patterns

- **State Management**: Zustand for global state
- **Data Fetching**: Custom API service with caching
- **Routing**: React Router v6 with type-safe routes
- **Styling**: Tailwind CSS with glassmorphism effects

## Deployment

The app can be deployed to any static hosting service:

- Vercel (recommended)
- Netlify
- GitHub Pages
- Cloudflare Pages

```bash
# Build for production
npm run build

# The dist/ folder contains the production build
```

## License

MIT
