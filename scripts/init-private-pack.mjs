import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { initPackOverlayWorkspace } from '../lib/pack-overlay.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

const rawRoot = join(root, 'private-packs', 'vendor-sources', 'kshmr-vol-4', 'raw');
const runtimeRoot = join(root, 'private-packs', 'runtime', 'edm-core');
const mapTarget = join(root, 'private-packs', 'vendor-sources', 'kshmr-vol-4', 'import-map.json');
const mapTemplate = join(root, 'packs', 'kshmr-vol-4.import-map.template.json');
initPackOverlayWorkspace({
  rawRoot,
  runtimeRoot,
  mapTarget,
  mapTemplate,
  rawSubdirs: [],
  label: 'private pack',
});
