/**
 * Shared MapLibre GL setup for the lazily-loaded map components.
 *
 * maplibre-gl v6 is ESM-only with no default export, and under a bundler it
 * cannot resolve its own worker from `import.meta.url`, so every consumer has
 * to call `setWorkerUrl()` once. Vite's `?worker&url` query routes the dist
 * worker through the worker pipeline, emitting a self-contained chunk; plain
 * `?url` would copy the file verbatim without its `maplibre-gl-shared.mjs`
 * sibling and no vector tiles would load in a production build.
 */
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl };
