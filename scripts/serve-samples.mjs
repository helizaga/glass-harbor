import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const sampleRoot = join(root, 'samples', 'edm-core');

const child = spawn(
  process.platform === 'win32' ? 'npx.cmd' : 'npx',
  ['@strudel/sampler'],
  {
    cwd: sampleRoot,
    stdio: 'inherit',
  },
);

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
