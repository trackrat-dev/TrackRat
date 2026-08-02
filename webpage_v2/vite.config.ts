import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

/**
 * Emitted MapLibre assets kept out of the precache manifest.
 *
 * maplibre-gl v5 inlined its web worker; v6 is ESM-only and must emit it as a
 * standalone chunk, so `maplibre-gl-shared` is duplicated across the map chunk
 * and the worker chunk. Left in the precache these are ~1.5 MB that every
 * first-time visitor downloads on the service worker's install, including the
 * majority who never open a map.
 *
 * `assets/maplibre-*.js` matches both the shared map chunk (`maplibre-<hash>.js`)
 * and the worker chunk (`maplibre-gl-worker-<hash>.js`); the `.css` entry is
 * maplibre's stylesheet, imported alongside it in `src/utils/maplibre.ts`.
 *
 * Exported so `vite.config.test.ts` can assert against the real build output —
 * a pattern that stops matching would otherwise silently no-op and look fixed.
 */
export const MAPLIBRE_PRECACHE_EXCLUSIONS = [
  'assets/maplibre-*.js',
  'assets/maplibre-*.css',
] as const;

/**
 * Runtime cache for the assets excluded above. They are content-hashed and
 * therefore immutable, so CacheFirst is safe: a new build emits a new filename
 * rather than mutating one, and the entries below age out on their own.
 */
export const MAPLIBRE_ASSET_URL_PATTERN = /\/assets\/maplibre-[^/]*\.(?:js|css)$/;

/**
 * Runtime cache route for the predictions/supported-stations lookup — the only
 * API response static enough to serve from cache.
 *
 * Must track the API hosts baked in by `infra_v2/cloudbuild-webpage*.yaml` as
 * `VITE_API_BASE_URL`. It previously matched `staging.apiv2.trackrat.net`,
 * which #1712 renamed to `staging-api.trackrat.net` because Cloudflare's
 * Universal SSL does not cover two-label subdomains — so the route quietly
 * stopped matching anything on staging. Exported so `vite.config.test.ts` can
 * assert it against both deployed base URLs rather than leaving that to review.
 */
export const SUPPORTED_STATIONS_URL_PATTERN =
  /^https:\/\/(apiv2|staging-api)\.trackrat\.net\/api\/v2\/predictions\/supported-stations/i;

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
  base: '/', // Root path for trackrat.net hosting
  plugins: [
    tailwindcss(),
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.png'],
      manifest: {
        name: 'TrackRat - Train Tracking',
        short_name: 'TrackRat',
        description: 'Real-time train tracking for NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North',
        theme_color: '#CC5500',
        background_color: '#F5F1E8',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: 'icon.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,jpg,jpeg,gif,webp,woff,woff2}'],
        // The MapLibre chunks are ~1.5 MB of the precache and every first-time
        // visitor pays for them on the service worker's install, including the
        // majority who never open a map. All three assets are reached only
        // through the React.lazy() map components, and a map cannot render
        // anything without network tiles anyway, so precaching them buys no
        // offline capability — see MAPLIBRE_PRECACHE_EXCLUSIONS.
        //
        // `assets/maplibre-*.js` covers both the shared map chunk
        // (maplibre-<hash>.js) and the worker chunk that v6 must emit
        // standalone (maplibre-gl-worker-<hash>.js).
        globIgnores: [...MAPLIBRE_PRECACHE_EXCLUSIONS],
        // Static-ish lookup data is the only API response safe to serve from
        // cache: the predictions/supported-stations list rarely changes.
        // Real-time endpoints (trips/search, trains/*, predictions/track,
        // predictions/delay, routes/congestion, routes/summary, routes/history,
        // alerts/service, trains/*/history) MUST NOT be cached by the service
        // worker — a 5-minute-stale departure board is worse than no data,
        // and the in-app polling layer already handles transient failures.
        runtimeCaching: [
          {
            // Pairs with globIgnores above: the map is fetched from the network
            // on first open, then served from this cache on every open after.
            urlPattern: MAPLIBRE_ASSET_URL_PATTERN,
            handler: 'CacheFirst',
            options: {
              cacheName: 'trackrat-maplibre-cache',
              expiration: {
                maxEntries: 8,
                maxAgeSeconds: 30 * 24 * 60 * 60 // 30 days
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: SUPPORTED_STATIONS_URL_PATTERN,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'trackrat-supported-stations-cache',
              networkTimeoutSeconds: 5,
              expiration: {
                maxEntries: 4,
                maxAgeSeconds: 24 * 60 * 60 // 24 hours
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          }
        ],
        navigateFallback: '/index.html' // Serve index.html for SPA client-side routes
      },
      devOptions: {
        enabled: true // Enable PWA in development for testing
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
  },
});
