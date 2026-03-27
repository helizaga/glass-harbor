import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

const rawRoot = join(root, 'private-packs', 'vendor-sources', 'kshmr-vol-4', 'raw');
const runtimeRoot = join(root, 'private-packs', 'runtime', 'edm-core');
const mapTarget = join(root, 'private-packs', 'vendor-sources', 'kshmr-vol-4', 'import-map.json');
const mapTemplate = join(root, 'packs', 'kshmr-vol-4.import-map.template.json');

mkdirSync(rawRoot, { recursive: true });
mkdirSync(runtimeRoot, { recursive: true });

if (!existsSync(mapTemplate)) {
  throw new Error(`Missing import map template at ${mapTemplate}`);
}

if (!existsSync(mapTarget)) {
  cpSync(mapTemplate, mapTarget);
}

console.log('Initialized private pack workspace:');
console.log(`- raw source: ${rawRoot}`);
console.log(`- local import map: ${mapTarget}`);
console.log(`- runtime output: ${runtimeRoot}`);
