import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { importPackOverlay } from '../lib/pack-overlay.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const args = process.argv.slice(2);

function readArg(name, fallback) {
  const index = args.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return args[index + 1] ?? fallback;
}

const sourceRoot = resolve(root, readArg('--source', 'private-packs/vendor-sources/kshmr-vol-4/raw'));
const mapPath = resolve(root, readArg('--map', 'private-packs/vendor-sources/kshmr-vol-4/import-map.json'));
const targetRoot = resolve(root, readArg('--target', 'private-packs/runtime/edm-core'));
const baseUrl = readArg('--base-url', '/private-packs/runtime/edm-core');
const publicFallbackRoot = resolve(root, readArg('--fallback-root', 'samples/edm-core'));
const publicFallbackBaseUrl = readArg('--fallback-base-url', '/samples/edm-core');
importPackOverlay({
  sourceRoot,
  mapPath,
  targetRoot,
  baseUrl,
  publicFallbackRoot,
  publicFallbackBaseUrl,
  label: 'private pack overlay',
});
