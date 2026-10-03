import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { parseCommonArgs } from '../lib/command-runtime.mjs';
import { STABLE_SOUND_ROLES } from '../lib/song-contract.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const requiredFamilies = STABLE_SOUND_ROLES;

function manifestIsComplete(manifestPath) {
  if (!existsSync(manifestPath)) {
    return false;
  }

  try {
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    return requiredFamilies.every((family) => Array.isArray(manifest[family]) && manifest[family].length > 0);
  } catch {
    return false;
  }
}

const privateRoot = join(root, 'private-packs', 'runtime', 'edm-core');
const privateManifest = join(privateRoot, 'strudel.json');
const publicRoot = join(root, 'samples', 'edm-core');
const chosenRoot = manifestIsComplete(privateManifest) ? privateRoot : publicRoot;
const { flags } = parseCommonArgs(process.argv.slice(2));

if (flags.json) {
  process.stdout.write(
    `${JSON.stringify(
      {
        phase: 'song:serve',
        status: 'starting',
        root: chosenRoot,
        mode: chosenRoot === privateRoot ? 'private' : 'public',
        url: 'http://127.0.0.1:5432',
      },
      null,
      2,
    )}\n`,
  );
} else if (!flags.quiet) {
  console.log(`Serving active song pack from ${chosenRoot}`);
}

const child = spawn(
  process.execPath,
  [join(root, 'node_modules', '@strudel', 'sampler', 'sample-server.mjs')],
  {
    cwd: chosenRoot,
    stdio: 'inherit',
  },
);

child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (error) => {
  console.error(`Failed to start active song pack server: ${error.message}`);
  process.exit(1);
});
