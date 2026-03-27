import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { parseCommonArgs } from '../lib/command-runtime.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const requiredFamilies = [
  'kick_main',
  'clap_main',
  'hat_closed',
  'hat_open',
  'perc_top',
  'impact_wide',
  'riser_up',
  'shimmer_fx',
  'air_texture',
  'vocal_chop',
];

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
  process.platform === 'win32' ? 'npx.cmd' : 'npx',
  ['@strudel/sampler'],
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
