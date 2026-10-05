import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { assertInsideRoot, importPackOverlay } from '../lib/pack-overlay.mjs';
import { resolvePythonExecutable } from '../lib/python-runtime.mjs';
import { repoRoot } from '../lib/song-contract.mjs';

const base = join(repoRoot, 'private-packs', 'vendor-sources', 'goldbaby');
const targetRoot = join(repoRoot, 'private-packs', 'runtime', 'edm-core');
assertInsideRoot(repoRoot, targetRoot, 'Private sample output');
execFileSync(resolvePythonExecutable(), [join(repoRoot, 'scripts', 'prepare-goldbaby-pack.py'), ...process.argv.slice(2)], {
  cwd: repoRoot, stdio: 'inherit', windowsHide: true,
});
importPackOverlay({
  sourceRoot: join(base, 'prepared'),
  mapPath: join(base, 'import-map.json'),
  targetRoot,
  baseUrl: '/private-packs/runtime/edm-core',
  publicFallbackRoot: join(repoRoot, 'samples', 'edm-core'),
  publicFallbackBaseUrl: '/samples/edm-core',
  label: 'Goldbaby free local overlay',
});
