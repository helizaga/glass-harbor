import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { join } from 'node:path';
import { repoRoot } from '../lib/song-contract.mjs';
import { resolvePythonExecutable } from '../lib/python-runtime.mjs';

test('validates the public-pack song through the portable CLI from another directory', () => {
  const result = spawnSync(process.execPath, [join(repoRoot, 'bin', 'glass-harbor.mjs'), 'song', 'validate', 'daybreak-ferry', '--json'],
    { cwd: process.env.TEMP ?? '/tmp', encoding: 'utf8', windowsHide: true });
  assert.equal(result.status, 0, result.stderr);
  const validation = JSON.parse(result.stdout);
  assert.equal(validation.status, 'ok');
  assert.match(validation.metadata['section-roles'], /return:return/);
  assert.equal(validation.sections.length, 6);
  assert.deepEqual(validation.errors, []);
});

test('honors the explicit Python interpreter override', () => {
  const previous = process.env.GLASS_HARBOR_PYTHON;
  process.env.GLASS_HARBOR_PYTHON = 'custom-python';
  try { assert.equal(resolvePythonExecutable(), 'custom-python'); }
  finally {
    if (previous === undefined) delete process.env.GLASS_HARBOR_PYTHON;
    else process.env.GLASS_HARBOR_PYTHON = previous;
  }
});
