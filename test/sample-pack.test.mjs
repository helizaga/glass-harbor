import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { repoRoot } from '../lib/song-contract.mjs';
import { assertInsideRoot, buildManifestFromRoot } from '../lib/pack-overlay.mjs';

test('sample regeneration is reproducible, preserves headroom and covers the song pitches', () => {
  assert.throws(() => assertInsideRoot(repoRoot, join(repoRoot, '..', 'outside-pack'), 'Sample output'), /must stay inside/);
  if (process.platform === 'win32') {
    const otherDrive = repoRoot[0].toUpperCase() === 'C' ? 'D' : 'C';
    assert.throws(() => assertInsideRoot(repoRoot, `${otherDrive}:\\outside-pack`, 'Sample output'), /must stay inside/);
  }
  const root = mkdtempSync(join(repoRoot, 'test-sample-pack-'));
  const generate = () => execFileSync(process.execPath, [join(repoRoot, 'scripts/generate-samples.mjs'),
    '--output', root, '--families', 'hat_closed,clap_main,stab_pitched,pluck_pitched,bass_pitched'], { cwd: repoRoot });
  const hashes = () => Object.fromEntries(readdirSync(root).flatMap(family =>
    readdirSync(join(root, family)).map(file => {
      const data = readFileSync(join(root, family, file));
      assert.equal(data.readInt16LE(44), 0, `Attack endpoint: ${family}/${file}`);
      assert.equal(data.readInt16LE(data.length - 2), 0, `Release endpoint: ${family}/${file}`);
      for (let offset = 44; offset < data.length; offset += 2) {
        assert.ok(Math.abs(data.readInt16LE(offset)) <= 27853, `Headroom: ${family}/${file}`);
      }
      return [`${family}/${file}`, createHash('sha256').update(data).digest('hex')];
    })));
  try {
    generate();
    const first = hashes();
    generate();
    assert.deepEqual(hashes(), first);
    const manifest = buildManifestFromRoot(root, '/samples');
    const song = readFileSync(join(repoRoot, 'songs/daybreak-ferry/daybreak-ferry.strudel.js'), 'utf8');
    const parts = [...song.matchAll(/const (?:bass|chords|arp|melody) = note\("([^"]+)"\)([\s\S]*?)(?=\n\n)/g)];
    assert.equal(parts.length, 4);
    for (const match of parts) {
      const family = match[2].match(/\.s\("([^"]+)"\)/)[1];
      for (const note of new Set(match[1].match(/[a-g][#b]?\d+/g))) {
        assert.ok(manifest[family][note], `Missing native ${family} root ${note}`);
      }
    }
  } finally {
    assertInsideRoot(repoRoot, root, 'Sample test cleanup');
    rmSync(root, { recursive: true, force: true });
  }
});
