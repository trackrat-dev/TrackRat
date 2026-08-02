// @vitest-environment node
import { describe, it, expect, beforeAll } from 'vitest';
import { build } from 'vite';
import { readFileSync, existsSync, rmSync, readdirSync } from 'fs';
import path from 'path';
import viteConfig, {
  MAPLIBRE_PRECACHE_EXCLUSIONS,
  MAPLIBRE_ASSET_URL_PATTERN,
  SUPPORTED_STATIONS_URL_PATTERN,
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
const HEADERS_PATH = path.join(OUT_DIR, '_headers');

/** One `_headers` block: a URL pattern plus the headers it contributes. */
interface HeaderRule {
  pattern: string;
  headers: Array<{ name: string; value: string }>;
}

/**
 * Parse Cloudflare's `_headers` format: an unindented URL pattern, followed by
 * indented `Name: Value` lines, `#` comments and blank lines ignored.
 *
 * Hand-rolled rather than asserted against with a substring match because the
 * interesting properties of this file are structural — which rules a given
 * request path matches, and whether two of them set the same header name.
 */
export function parseHeadersFile(contents: string): HeaderRule[] {
  const rules: HeaderRule[] = [];

  contents.split('\n').forEach((raw, index) => {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim() || line.trimStart().startsWith('#')) return;

    if (!/^\s/.test(line)) {
      rules.push({ pattern: line.trim(), headers: [] });
      return;
    }

    const rule = rules[rules.length - 1];
    if (!rule) {
      throw new Error(`_headers line ${index + 1}: header line before any URL pattern: "${line}"`);
    }
    const separator = line.indexOf(':');
    if (separator === -1) {
      throw new Error(`_headers line ${index + 1}: expected "Name: Value", got "${line}"`);
    }
    rule.headers.push({
      name: line.slice(0, separator).trim(),
      value: line.slice(separator + 1).trim(),
    });
  });

  return rules;
}

/**
 * Cloudflare's path matching: a splat (`*`) greedily matches all characters,
 * and at most one may appear. Everything else is literal.
 */
export function matchesHeaderPattern(pattern: string, requestPath: string): boolean {
  const splats = (pattern.match(/\*/g) ?? []).length;
  if (splats > 1) {
    throw new Error(`_headers pattern "${pattern}" has ${splats} splats; Cloudflare allows at most 1`);
  }
  const source = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\\*/g, '.*');
  return new RegExp(`^${source}$`).test(requestPath);
}

/** Every header contributed to `requestPath`, in file order, duplicates kept. */
function headersFor(rules: HeaderRule[], requestPath: string): Array<{ name: string; value: string }> {
  return rules
    .filter((rule) => matchesHeaderPattern(rule.pattern, requestPath))
    .flatMap((rule) => rule.headers);
}

/** Emitted assets, relative to the build output root (e.g. `assets/foo-hash.js`). */
let emittedAssets: string[] = [];
/** `url` entries from the generated service worker's `precacheAndRoute([...])`. */
let precachedUrls: string[] = [];
/** Parsed rules from the emitted `_headers` file. */
let headerRules: HeaderRule[] = [];

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

  headerRules = existsSync(HEADERS_PATH) ? parseHeadersFile(readFileSync(HEADERS_PATH, 'utf-8')) : [];
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

/**
 * The Cloudflare hosting contract (issue #1713).
 *
 * Serving policy used to live in `infra_v2/cloudbuild-webpage*.yaml` as a list
 * of `gsutil setmeta` calls run after each GCS sync. On Cloudflare it is
 * `webpage_v2/public/_headers`, plus two files that must NOT exist. All of it
 * is invisible at build time and only observable in production, so it is
 * asserted here against a real build rather than trusted to review.
 */
describe('Cloudflare hosting contract (issue #1713)', () => {
  /** A real content-hashed entry chunk, e.g. `assets/index-CinxXL8-.js`. */
  const hashedEntryAsset = () => {
    const asset = emittedAssets.find((a) => /^assets\/index-.*\.js$/.test(a));
    if (!asset) throw new Error(`No hashed entry chunk in: ${emittedAssets.join(', ')}`);
    return `/${asset}`;
  };

  it('emits _headers at the root of the build output', () => {
    // Vite copies public/ to the dist root, which is the only place Cloudflare
    // looks. A move of the file into a subdirectory is silent: the deploy
    // succeeds and every rule below simply stops applying.
    expect(
      existsSync(HEADERS_PATH),
      `_headers is missing from ${OUT_DIR}. It must live in webpage_v2/public/ so Vite copies it to the dist root.`,
    ).toBe(true);
    expect(headerRules.length, 'parsed _headers contained no rules').toBeGreaterThan(0);
  });

  it('reproduces every response header the GCS pipeline used to set', () => {
    // Left column is what `gsutil setmeta` set (or the LB's
    // custom_response_headers, for HSTS); right column is what a request must
    // now receive from Cloudflare.
    const expected: Array<[string, string, string]> = [
      ['/', 'Cache-Control', 'no-cache, no-store, must-revalidate'],
      ['/', 'Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload'],
      [hashedEntryAsset(), 'Cache-Control', 'public, max-age=31536000, immutable'],
      ['/sw.js', 'Cache-Control', 'no-cache, no-store, must-revalidate'],
      ['/registerSW.js', 'Cache-Control', 'no-cache, no-store, must-revalidate'],
      ['/.well-known/apple-app-site-association', 'Content-Type', 'application/json'],
    ];

    for (const [requestPath, name, value] of expected) {
      const applied = headersFor(headerRules, requestPath).filter((h) => h.name === name);
      expect(
        applied.map((h) => h.value),
        `${requestPath} must receive "${name}: ${value}". Matching patterns were: ` +
          `${headerRules.filter((r) => matchesHeaderPattern(r.pattern, requestPath)).map((r) => r.pattern).join(', ') || '(none)'}`,
      ).toEqual([value]);
    }
  });

  it('never sets one header name from two rules matching the same path', () => {
    // Cloudflare JOINS duplicate header values with a comma rather than letting
    // the more specific rule win. A `Cache-Control` under `/*` would therefore
    // turn the immutable asset rule into
    // "no-store, ..., public, max-age=31536000, immutable" — a value no browser
    // handles the way either rule intended, and one that no amount of reading
    // the file makes obvious.
    const requestPaths = [
      '/',
      hashedEntryAsset(),
      '/sw.js',
      '/registerSW.js',
      '/.well-known/apple-app-site-association',
      '/index.html',
      '/trains/TR/NY',
    ];

    for (const requestPath of requestPaths) {
      const applied = headersFor(headerRules, requestPath);
      const duplicated = applied
        .map((h) => h.name)
        .filter((name, i, all) => all.indexOf(name) !== i);

      expect(
        [...new Set(duplicated)],
        `${requestPath} matches rules that set the same header more than once; ` +
          `Cloudflare would comma-join the values. Applied: ${JSON.stringify(applied)}`,
      ).toEqual([]);
    }
  });

  it('does not key the app shell on /index.html', () => {
    // Cloudflare redirects /index.html to / before serving it, so a rule keyed
    // on /index.html decorates the redirect and never the HTML. This is the
    // exact shape the issue's original proposal had.
    expect(
      headerRules.map((r) => r.pattern),
      'a rule is keyed on /index.html; Cloudflare redirects that path to "/", so key the app shell on "/" instead',
    ).not.toContain('/index.html');
  });

  it('only names paths that the build actually emits', () => {
    // The reverse rot: vite-plugin-pwa renames or drops an output and the rule
    // for it silently stops applying. Splat patterns are covered by the
    // header-value assertions above; these are the literal ones.
    const literalPaths = headerRules
      .map((r) => r.pattern)
      .filter((p) => !p.includes('*') && p !== '/');

    expect(literalPaths.length, 'expected _headers to pin some literal paths').toBeGreaterThan(0);

    for (const literalPath of literalPaths) {
      const onDisk = path.join(OUT_DIR, literalPath);
      expect(
        existsSync(onDisk),
        `_headers has a rule for "${literalPath}" but the build does not emit it. ` +
          `Either the output was renamed or the rule is dead.`,
      ).toBe(true);
    }
  });

  it('ships the Apple App Site Association file as valid JSON', () => {
    // Universal links break silently when this is missing: no build error, no
    // runtime error, links just stop opening the app.
    const aasaPath = path.join(OUT_DIR, '.well-known/apple-app-site-association');
    expect(existsSync(aasaPath), `${aasaPath} was not copied from public/`).toBe(true);

    const aasa = JSON.parse(readFileSync(aasaPath, 'utf-8'));
    expect(aasa.applinks.details[0].appIDs).toContain('D5RZZ55J9R.net.trackrat.TrackRat');
  });

  it('ships no top-level 404.html, which is what enables the SPA fallback', () => {
    // Cloudflare only falls back to the SPA entrypoint for unmatched paths when
    // the deployment has no top-level 404.html. Adding one silently converts
    // every deep link — /trains/TR/NY, shared /train/... links — into a 404
    // page. Nothing else in the repo would flag that.
    expect(
      existsSync(path.join(OUT_DIR, '404.html')),
      'a top-level 404.html disables Cloudflare\'s single-page-application fallback for deep links',
    ).toBe(false);
  });

  it('ships no _redirects file', () => {
    // Cloudflare: "Redirects are always followed, regardless of whether or not
    // an asset matches the incoming request." The tempting SPA catch-all
    // `/* /index.html 200` therefore shadows the hashed assets, the service
    // worker and the AASA file with the HTML shell — a white-screen deploy that
    // looks correct in review. The fallback above needs no redirect at all.
    expect(
      existsSync(path.join(OUT_DIR, '_redirects')),
      'a _redirects catch-all would shadow real assets; Cloudflare follows redirects even when an asset exists',
    ).toBe(false);
  });
});

/**
 * The service worker's one API runtime-cache route is a regex over absolute
 * API URLs, while the URL it has to match is injected at build time from the
 * Cloud Build configs. Nothing connects the two, so #1712's rename of the
 * staging API host left the route matching nothing — no error, just a cache
 * that silently stopped working on staging. These read the real deploy configs.
 */
describe('supported-stations runtime cache: API host tracking (issue #1712)', () => {
  const CLOUDBUILD_CONFIGS = {
    staging: path.resolve(__dirname, '../infra_v2/cloudbuild-webpage-staging.yaml'),
    production: path.resolve(__dirname, '../infra_v2/cloudbuild-webpage.yaml'),
  };

  /** The `_API_BASE_URL` substitution a deploy bakes in as `VITE_API_BASE_URL`. */
  const deployedApiBaseUrl = (configPath: string): string => {
    if (!existsSync(configPath)) {
      throw new Error(
        `${configPath} not found. If the webpage Cloud Build configs moved, update CLOUDBUILD_CONFIGS here — ` +
          `this test is what keeps SUPPORTED_STATIONS_URL_PATTERN pinned to the hosts we actually deploy against.`,
      );
    }
    const match = readFileSync(configPath, 'utf-8').match(/^\s*_API_BASE_URL:\s*'([^']+)'/m);
    if (!match) throw new Error(`No _API_BASE_URL substitution in ${configPath}`);
    return match[1];
  };

  it.each(Object.entries(CLOUDBUILD_CONFIGS))(
    'matches the %s API host that the deploy bakes into the bundle',
    (environment, configPath) => {
      const baseUrl = deployedApiBaseUrl(configPath);
      const requestUrl = `${baseUrl}/predictions/supported-stations`;

      expect(
        SUPPORTED_STATIONS_URL_PATTERN.test(requestUrl),
        `The ${environment} deploy builds against ${baseUrl}, but SUPPORTED_STATIONS_URL_PATTERN ` +
          `(${SUPPORTED_STATIONS_URL_PATTERN}) does not match ${requestUrl}. The service worker would ` +
          `never cache supported-stations there.`,
      ).toBe(true);
    },
  );

  it('does not match unrelated API endpoints', () => {
    // Real-time endpoints must never be served from the service worker cache —
    // a stale departure board is worse than no board. Guards an over-broad
    // pattern as much as an under-broad one.
    for (const endpoint of ['trains/departures', 'trips/search', 'routes/congestion']) {
      const url = `https://apiv2.trackrat.net/api/v2/${endpoint}`;
      expect(SUPPORTED_STATIONS_URL_PATTERN.test(url), `${url} must not be runtime-cached`).toBe(false);
    }
  });
});
