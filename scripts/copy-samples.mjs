import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const targets = [
  ['samples', 'samples'],
  ['songs', 'songs'],
  ['tracks', 'tracks'],
];
const includePrivateRuntime = process.env.GLASS_HARBOR_INCLUDE_PRIVATE_RUNTIME === '1';
if (includePrivateRuntime && existsSync(join(root, 'private-packs', 'runtime'))) {
  targets.push(['private-packs/runtime', 'private-packs/runtime']);
}

for (const [sourceDir, targetDir] of targets) {
  const source = join(root, sourceDir);
  const target = join(root, 'dist', targetDir);
  rmSync(target, { recursive: true, force: true });
  mkdirSync(target, { recursive: true });
  cpSync(source, target, { recursive: true });
}
