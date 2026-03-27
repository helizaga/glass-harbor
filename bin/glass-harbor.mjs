#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

function usage() {
  return `Glass Harbor CLI

Usage:
  glass-harbor song new <slug> [--json] [--quiet] [--verbose]
  glass-harbor song variants <slug> [--count <n>] [--json] [--quiet] [--verbose]
  glass-harbor song validate <slug> [--json] [--quiet] [--verbose]
  glass-harbor song serve [--json] [--quiet]
  glass-harbor song render <slug> [--run <path>] [--json] [--quiet] [--verbose]
  glass-harbor song analyze <slug> [--run <path>] [--json] [--quiet] [--verbose]
  glass-harbor song critique <slug> [--run <path>] [--json] [--quiet] [--verbose]
  glass-harbor song revise <slug> [--run <path>] [--json] [--quiet] [--verbose]
  glass-harbor song status <slug> [--json] [--quiet] [--verbose]
  glass-harbor song next <slug> [--json] [--quiet] [--verbose]
  glass-harbor song approve <slug> [--run <path>] [--reason <text>] [--json] [--quiet] [--verbose]
  glass-harbor song reject <slug> [--run <path>] [--reason <text>] [--json] [--quiet] [--verbose]
  glass-harbor song loop <slug> [--max-iters <n>] [--json] [--quiet] [--verbose]
  glass-harbor song compare <slug> [<other-slug> ...] [--json] [--quiet] [--verbose]
  glass-harbor song explore <slug> [--count <n>] [--max-iters <n>] [--json] [--quiet] [--verbose]
  glass-harbor debug ui
  glass-harbor debug osc [--debug]

Compatibility:
  npm run song:* remains available as thin wrappers around this CLI.
`;
}

function fail(message, exitCode = 1) {
  process.stderr.write(`${message}\n`);
  process.exit(exitCode);
}

function spawnCommand(command, args) {
  const child = spawn(command, args, {
    cwd: root,
    stdio: 'inherit',
  });

  child.on('exit', (code) => {
    process.exit(code ?? 1);
  });

  child.on('error', (error) => {
    fail(error.message);
  });
}

function scriptPath(name) {
  return resolve(root, 'scripts', name);
}

function parseSongArgs(args, { requireSlug = false } = {}) {
  const hasSongFlag = args.includes('--song') || args.includes('-s');
  const flagsWithValues = new Set(['--song', '-s', '--run', '--count', '--max-iters', '--reason']);
  const rest = [];
  let slug = null;

  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];
    if (!hasSongFlag && !slug && !value.startsWith('-')) {
      slug = value;
      continue;
    }

    rest.push(value);
    if (flagsWithValues.has(value) && args[index + 1] !== undefined) {
      rest.push(args[index + 1]);
      index += 1;
    }
  }

  if (requireSlug && !hasSongFlag && !slug) {
    fail(usage());
  }

  return hasSongFlag || !slug ? rest : ['--song', slug, ...rest];
}

const argv = process.argv.slice(2);
if (argv.length === 0 || argv[0] === 'help' || argv[0] === '--help' || argv[0] === '-h') {
  process.stdout.write(`${usage()}\n`);
  process.exit(0);
}

const [namespace, command, ...rest] = argv;

if (namespace === 'song') {
  if (command === 'new') {
    spawnCommand(process.execPath, [scriptPath('song-new.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'variants') {
    spawnCommand(process.execPath, [scriptPath('song-variants.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'validate') {
    spawnCommand(process.execPath, [scriptPath('song-validate.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'serve') {
    spawnCommand(process.execPath, [scriptPath('serve-active-pack.mjs'), ...rest]);
  } else if (command === 'render') {
    spawnCommand(process.execPath, [scriptPath('song-render.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'analyze') {
    spawnCommand(process.execPath, [scriptPath('song-analyze.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'critique') {
    spawnCommand(process.execPath, [scriptPath('song-critique.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'revise') {
    spawnCommand(process.execPath, [scriptPath('song-revise.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'status') {
    spawnCommand(process.execPath, [scriptPath('song-status.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'next') {
    spawnCommand(process.execPath, [scriptPath('song-next.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'approve') {
    spawnCommand(process.execPath, [scriptPath('song-approve.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'reject') {
    spawnCommand(process.execPath, [scriptPath('song-reject.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'loop') {
    spawnCommand(process.execPath, [scriptPath('song-loop.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else if (command === 'compare') {
    spawnCommand(process.execPath, [scriptPath('song-compare.mjs'), ...rest]);
  } else if (command === 'explore') {
    spawnCommand(process.execPath, [scriptPath('song-explore.mjs'), ...parseSongArgs(rest, { requireSlug: true })]);
  } else {
    fail(usage());
  }
} else if (namespace === 'debug') {
  if (command === 'ui') {
    spawnCommand(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['vite', ...rest]);
  } else if (command === 'osc') {
    spawnCommand(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['@strudel/osc', ...rest]);
  } else {
    fail(usage());
  }
} else {
  fail(usage());
}
