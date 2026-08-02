// @vitest-environment node
import { describe, it, expect, beforeAll } from 'vitest';
import { build } from 'vite';
import { readFileSync, existsSync, rmSync, readdirSync } from 'fs';
import path from 'path';
import viteConfig, {
  MAPLIBRE_PRECACHE_EXCLUSIONS,
  MAPLIBRE_ASSET_URL_PATTERN,
} from './vite.config';

/**
 * These assertions run against a REAL production build, not against the config
 * object. That distinction is the whole point: `globIgnores` patterns are
 * matched against emitted filenames, so a chunk rename (a maplibre major, a
 * Vite/rolldown chunk-naming change) makes the pattern quietly match nothing.
 * The precache silently grows back by ~1.5 MB and the config still *looks*
 * correct. Only the build output can tell us the difference.
 */

const OUT_DIR = path.resolve(__dirname, 'dist-precache-test');
const SW_PATH = path.join(OUT_DIR, 'sw.js');

/** Emitted assets, relative to the build output root (e.g. `assets/foo-hash.js`). */
let emittedAssets: string[] = [];
/** `url` entries from the generated service worker's `precacheAndRoute([...])`. */
let precachedUrls: string[] = [];

beforeAll(async () => {
  rmSync(OUT_DIR, { recursive: true, force: true });

  // vitest sets NODE_ENV=test, which both Vite's minifier and workbox-build read
  // directly. Without this the emitted bundles are unminified and the byte
  // budget below would be measured against sizes the deploy never ships.
  const priorNodeEnv = process.env.NODE_ENV;
  process.env.NODE_ENV = 'production';
  try {
  await build({
    ...viteConfig,
    // `configFile: false` stops Vite ALSO loading vite.config.ts from disk and
    // concatenating its plugins onto the spread ones — that would run VitePWA
    // twice and generate a service worker from a doubled plugin pipeline.
    configFile: false,
    // Pin production so chunking and hashing match what `npm run build` ships.
    // Workbox's own minification keys off NODE_ENV (which vitest sets to
    // 'test') rather than this, so the manifest parser below tolerates both the
    // minified and pretty-printed service worker shapes.
    mode: 'production',
    // Keep the real dist/ (and the deploy script that reads it) untouched.
    build: { ...viteConfig.build, outDir: OUT_DIR, emptyOutDir: true },
    logLevel: 'silent',
  });
  } finally {
    if (priorNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = priorNodeEnv;
  }

  emittedAssets = readdirSync(path.join(OUT_DIR, 'assets')).map((f) => `assets/${f}`);

  const sw = readFileSync(SW_PATH, 'utf-8');
  // Minified: `precacheAndRoute([{url:"a",revision:"b"}])`
  // Pretty:   `workbox.precacheAndRoute([{\n  "url": "a",\n ... \n}], {})`
  const manifest = sw.match(/precacheAndRoute\(\s*\[([\s\S]*?)\]\s*[,)]/);
  if (!manifest) {
    throw new Error(
      `No precacheAndRoute([...]) found in ${SW_PATH}. vite-plugin-pwa output shape changed; ` +
        `this test can no longer see the precache manifest and must be updated.`,
    );
  }
  precachedUrls = [...manifest[1].matchAll(/"?url"?\s*:\s*"([^"]+)"/g)].map((m) => m[1]);
  if (precachedUrls.length === 0) {
    throw new Error(`Parsed an empty precache manifest from ${SW_PATH}; the parser is stale.`);
  }
}, 180_000);

/** The three assets reachable only through the React.lazy() map components. */
const maplibreAssets = () =>
  emittedAssets.filter((a) => path.basename(a).startsWith('maplibre-'));

describe('PWA precache: MapLibre exclusion (issue #1702)', () => {
  it('still emits the map chunk, the worker chunk and the stylesheet', () => {
    // Excluding from the precache must not stop Vite emitting them. maplibre v6
    // without a resolvable worker never fires `load` — an empty map with no
    // console error — so a missing worker chunk is the silent failure here.
    const names = maplibreAssets().map((a) => path.basename(a));

    expect(names, `emitted assets were: ${emittedAssets.join(', ')}`).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/^maplibre-gl-worker-.*\.js$/),
        expect.stringMatching(/^maplibre-.*\.js$/),
        expect.stringMatching(/^maplibre-.*\.css$/),
      ]),
    );
    expect(names.length).toBe(3);
  });

  it('keeps every MapLibre asset out of the precache manifest', () => {
    const leaked = precachedUrls.filter((u) => path.basename(u).startsWith('maplibre-'));

    expect(
      leaked,
      `globIgnores ${JSON.stringify(MAPLIBRE_PRECACHE_EXCLUSIONS)} did not match these ` +
        `emitted assets. If a chunk was renamed, update the patterns to match.`,
    ).toEqual([]);
  });

  it('matches every emitted MapLibre asset with the runtime-cache pattern', () => {
    // Guards the other half: an asset excluded from the precache but NOT matched
    // by the runtime route would be re-downloaded on every single map open.
    const unmatched = maplibreAssets().filter(
      (a) => !MAPLIBRE_ASSET_URL_PATTERN.test(`/${a}`),
    );

    expect(
      unmatched,
      `these assets are excluded from the precache but no runtime cache rule covers them`,
    ).toEqual([]);
  });

  it('still precaches the app shell, so the exclusion is not over-broad', () => {
    // A pattern like `assets/*` would satisfy the two tests above while
    // destroying the PWA. Pin the things that must stay precached.
    expect(precachedUrls).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/^index\.html$/),
        expect.stringMatching(/^assets\/index-.*\.js$/),
        expect.stringMatching(/^assets\/index-.*\.css$/),
      ]),
    );
    // The lazy map components themselves are tiny wrappers and stay precached;
    // only the heavy maplibre library chunks are excluded.
    expect(precachedUrls).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/^assets\/RouteMap-.*\.js$/),
        expect.stringMatching(/^assets\/CongestionMap-.*\.js$/),
      ]),
    );
  });

  it('holds the precache under the pre-upgrade budget', () => {
    // #1702's acceptance criterion: back to roughly the maplibre-v5 figure of
    // ~2,646 KiB. Excluding the map chunk as well as the worker lands far
    // below that. The ceiling is a regression guard, not a target.
    const PRECACHE_BUDGET_BYTES = 2_646 * 1024;

    const total = precachedUrls.reduce((sum, url) => {
      const file = path.join(OUT_DIR, url);
      return existsSync(file) ? sum + readFileSync(file).byteLength : sum;
    }, 0);

    expect(
      total,
      `precache is ${Math.round(total / 1024)} KiB across ${precachedUrls.length} entries`,
    ).toBeLessThan(PRECACHE_BUDGET_BYTES);
  });
});
