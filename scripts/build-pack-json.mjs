import { existsSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildManifestFromRoot } from '../lib/pack-overlay.mjs';

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

const sampleRoot = resolve(root, readArg('--root', 'samples/edm-core'));
const baseUrl = readArg('--base-url', '/samples/edm-core');
if (!existsSync(sampleRoot)) {
  throw new Error(`Pack root does not exist: ${sampleRoot}`);
}

const manifest = buildManifestFromRoot(sampleRoot, baseUrl);
if (Object.keys(manifest).length === 0) {
  throw new Error(`No sample families found under ${sampleRoot}`);
}

writeFileSync(join(sampleRoot, 'strudel.json'), `${JSON.stringify(manifest, null, 2)}\n`);
