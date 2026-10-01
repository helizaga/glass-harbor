import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEFAULT_LOCAL_PACK_SUBDIRS, initPackOverlayWorkspace } from '../lib/pack-overlay.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

const rawRoot = join(root, 'private-packs', 'vendor-sources', 'local-drums', 'raw');
const runtimeRoot = join(root, 'private-packs', 'runtime', 'edm-core');
const mapTarget = join(root, 'private-packs', 'vendor-sources', 'local-drums', 'import-map.json');
const mapTemplate = join(root, 'packs', 'local-drums.import-map.template.json');
const prepPlanTarget = join(root, 'private-packs', 'vendor-sources', 'local-drums', 'prep-plan.json');
const prepPlanTemplate = join(root, 'packs', 'local-drums.prep-plan.template.json');

initPackOverlayWorkspace({
  rawRoot,
  runtimeRoot,
  mapTarget,
  mapTemplate,
  prepPlanTarget,
  prepPlanTemplate,
  rawSubdirs: DEFAULT_LOCAL_PACK_SUBDIRS,
  label: 'local pack upgrade',
});
