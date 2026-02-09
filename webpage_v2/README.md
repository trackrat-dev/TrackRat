# TrackRat Web

A mobile-first web application for tracking NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North trains in real-time.

## Features

- 🚂 Real-time train departures and details
- 🔍 Search trains by origin and destination
- ⭐ Favorite stations for quick access
- 📱 Mobile-first responsive design
- 🎨 Dark mode with glassmorphism UI
- 🔄 Auto-refresh every 30 seconds

## Tech Stack

- React 19 + TypeScript
- Vite 7 (build tool)
- Tailwind CSS 3 (styling)
- Zustand 5 (state management)
- React Router v6 (routing)
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

The app connects to the TrackRat backend API at `https://apiv2.trackrat.net/api/v2`.

### Key Endpoints

- `GET /trains/departures` - Get train departures
- `GET /trains/{id}` - Get train details
- `GET /predictions/track` - ML platform predictions
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

### Automated Deployment (GitHub Pages)

The app automatically deploys to GitHub Pages when changes are pushed to the `main` branch.

**Live URL:** https://bokonon1.github.io/TrackRat/

**How it works:**
1. Push changes to `webpage_v2/` directory
2. GitHub Actions automatically builds and deploys
3. Changes appear at the live URL within ~2 minutes

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

### Manual Deployment

The app can be deployed to any static hosting service:

- GitHub Pages (automated via Actions)
- Vercel
- Netlify
- Cloudflare Pages

```bash
# Build for production
npm run build

# The dist/ folder contains the production build
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../LICENSE) for details.
