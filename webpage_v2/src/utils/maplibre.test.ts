import { describe, it, expect } from 'vitest';
import { getWorkerUrl } from 'maplibre-gl';
import { maplibregl } from './maplibre';

// Deliberately unmocked: the whole point of this module is what it does to the
// real maplibre-gl config at import time.
describe('maplibre setup', () => {
  it('points maplibre at a bundled worker script', () => {
    // maplibre-gl v6 cannot resolve its own worker from `import.meta.url` once
    // bundled. Left unset, `new Worker()` requests a file the bundle never
    // emits, and the map silently never fires `load` — no tiles, no error.
    const url = getWorkerUrl();
    expect(url).not.toBe('');
    expect(url).toMatch(/maplibre-gl-worker/);
  });

  it('exports the module namespace, which has no default export in v6', () => {
    // `import maplibregl from 'maplibre-gl'` is a build error on v6; consumers
    // get the namespace from here instead.
    expect(typeof maplibregl.Map).toBe('function');
    expect(typeof maplibregl.NavigationControl).toBe('function');
    expect(maplibregl.getWorkerUrl()).toBe(getWorkerUrl());
  });
});
