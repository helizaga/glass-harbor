import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { assertInsideRoot } from '../lib/pack-overlay.mjs';
import { chooseBaselineRun, ensureSongMemory, loadSongMemory } from '../lib/review-gates.mjs';
import { songPaths, songsRoot } from '../lib/song-contract.mjs';
import { handleSongRevise } from '../scripts/song-revise.mjs';
import { handleSongApprove } from '../scripts/song-approve.mjs';
import { handleSongReject } from '../scripts/song-reject.mjs';

test('the first reviewed run reaches the listener gate without becoming an approved baseline', async () => {
  const slug = `review-gate-test-${randomUUID()}`;
  const songDir = songPaths(slug).dir;
  const runDir = mkdtempSync(join(tmpdir(), 'glass-harbor-review-'));
  mkdirSync(songDir, { recursive: true });
  try {
    writeFileSync(join(runDir, 'critique.json'), JSON.stringify({ gate: 'review_gate', scores: { groove_strength: 0.8 },
      style_profile: { label: 'Atmospheric Deep House' }, strudel_techniques: { opportunities: ['Use a smoother filter sweep.'] } }));
    const memory = ensureSongMemory(slug, { seedRunDir: runDir });
    assert.equal(memory.approved_baseline_run_dir, null);
    assert.equal(memory.pending_review_run_dir, runDir);
    assert.equal(memory.current_best_comparison_score, null);
    assert.equal(chooseBaselineRun(slug, { memory }), null);
    const source = songPaths('daybreak-ferry');
    writeFileSync(songPaths(slug).briefPath, readFileSync(source.briefPath));
    writeFileSync(songPaths(slug).songPath, readFileSync(source.songPath));
    const revision = await handleSongRevise({ argv: [slug, '--run', runDir] });
    assert.equal(revision.baseline_run_dir, null);
    assert.equal(revision.recommended_next_action, 'review_gate');
    assert.equal(revision.approval_required, true);
    // Exercise actual decision commands on the disposable fixture, never a listener's song.
    await handleSongApprove({ argv: [slug, '--run', runDir, '--reason', 'Test listener accepted'] });
    assert.equal(loadSongMemory(slug).approved_baseline_run_dir, runDir);
    await handleSongReject({ argv: [slug, '--run', runDir, '--reason', 'Test listener withdrew approval'] });
    assert.equal(loadSongMemory(slug).approved_baseline_run_dir, null);
    assert.deepEqual(loadSongMemory(slug).taste_profile.avoid_lanes, []);
    assert.deepEqual(loadSongMemory(slug).taste_profile.avoid_techniques, []);
    assert.equal(chooseBaselineRun(slug), null);
  } finally {
    assertInsideRoot(songsRoot, songDir, 'Test song');
    assertInsideRoot(tmpdir(), runDir, 'Test run');
    rmSync(songDir, { recursive: true, force: true });
    rmSync(runDir, { recursive: true, force: true });
  }
});

test('automated verdicts and legacy seeded baselines do not imply approval', () => {
  const memory = {
    approved_baseline_run_dir: 'seeded',
    history: [
      { run_dir: 'seeded', decision: 'seed_baseline' },
      { run_dir: 'candidate', decision: 'baseline' },
      { run_dir: 'candidate', decision: 'improved' },
      { run_dir: 'candidate', decision: 'rejected' },
    ],
  };
  assert.equal(chooseBaselineRun('daybreak-ferry', { memory }), null);
});

test('a rejected candidate does not replace a previous approved run', () => {
  const memory = {
    approved_baseline_run_dir: 'approved',
    history: [{ run_dir: 'approved', decision: 'approved' }, { run_dir: 'candidate', decision: 'rejected' }],
  };
  assert.equal(chooseBaselineRun('daybreak-ferry', { memory }), 'approved');
  assert.equal(chooseBaselineRun('daybreak-ferry', { memory, excludeRunDir: 'approved' }), null);
});

test('rejecting an approved run falls back only to another listener-approved run', () => {
  const memory = {
    approved_baseline_run_dir: 'new',
    history: [
      { run_dir: 'old', decision: 'approved' },
      { run_dir: 'bad', decision: 'approved' },
      { run_dir: 'bad', decision: 'rejected' },
      { run_dir: 'new', decision: 'approved' },
      { run_dir: 'new', decision: 'rejected' },
    ],
  };
  assert.equal(chooseBaselineRun('daybreak-ferry', { memory }), 'old');
  assert.equal(chooseBaselineRun('daybreak-ferry', { memory, excludeRunDir: 'old' }), null);
});
