import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

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
        // Static-ish lookup data is the only API response safe to serve from
        // cache: the predictions/supported-stations list rarely changes.
        // Real-time endpoints (trips/search, trains/*, predictions/track,
        // predictions/delay, routes/congestion, routes/summary, routes/history,
        // alerts/service, trains/*/history) MUST NOT be cached by the service
        // worker — a 5-minute-stale departure board is worse than no data,
        // and the in-app polling layer already handles transient failures.
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/(apiv2|staging\.apiv2)\.trackrat\.net\/api\/v2\/predictions\/supported-stations/i,
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
