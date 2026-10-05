import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { assertInsideRoot } from '../lib/pack-overlay.mjs';
import { songPaths, songsRoot, runsRoot } from '../lib/song-contract.mjs';
import { handleSongRender } from '../scripts/song-render.mjs';

test('a continuous offline render preserves steady volume and exact section audio', async () => {
  const slug = `render-volume-test-${randomUUID()}`;
  const song = songPaths(slug);
  mkdirSync(song.dir, { recursive: true });
  writeFileSync(song.songPath, `// @title Offline volume fixture
// @genre house
// @bpm 120
// @details Repeated beats must keep their level throughout the offline render.
// @sections early:16, late:16
// @section_roles early:anchor, late:return
samples('http://localhost:5432')
setcpm(120 / 4)
s("kick_main*4").gain(0.4)
`);
  try {
    const result = await handleSongRender({ argv: [slug] });
    assert.equal(result.status, 'ok', JSON.stringify(result));
    const mix = readFileSync(join(result.run_dir, 'mix.wav'));
    const framesPerSecond = mix.readUInt32LE(24);
    const blockAlign = mix.readUInt16LE(32);
    const rms = (startSeconds) => {
      let sum = 0;
      let count = 0;
      const begin = 44 + startSeconds * framesPerSecond * blockAlign;
      const end = begin + 4 * framesPerSecond * blockAlign;
      for (let offset = begin; offset < end; offset += 2) {
        sum += mix.readInt16LE(offset) ** 2;
        count += 1;
      }
      return Math.sqrt(sum / count);
    };
    const levels = [rms(4), rms(28), rms(56)];
    assert.ok(Math.min(...levels) > 100, `Silent beats: ${levels}`);
    assert.ok(Math.max(...levels) / Math.min(...levels) < 1.05, `Unexpected volume drift: ${levels}`);
    const sections = ['early', 'late'].map((name) => readFileSync(join(result.run_dir, 'sections', `${name}.wav`)));
    assert.deepEqual(Buffer.concat(sections.map((wav) => wav.subarray(44))), mix.subarray(44));
  } finally {
    const runDir = join(runsRoot, slug);
    assertInsideRoot(songsRoot, song.dir, 'Test song');
    assertInsideRoot(runsRoot, runDir, 'Test runs');
    rmSync(song.dir, { recursive: true, force: true });
    rmSync(runDir, { recursive: true, force: true });
  }
});
