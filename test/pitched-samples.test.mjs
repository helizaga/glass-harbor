import assert from 'node:assert/strict';
import { test } from 'node:test';
import { noteFrequency, renderPitchedTone, SAMPLE_RATE } from '../lib/pitched-samples.mjs';

test('pitched families contain tuned, audible, unclipped tones with click-free endpoints', () => {
  for (const kind of ['pad', 'pluck']) {
    const samples = renderPitchedTone('a4', kind);
    assert.equal(Math.abs(samples[0]), 0);
    assert.equal(Math.abs(samples.at(-1)), 0);
    let peak = 0;
    const crossings = [];
    for (let index = 1; index < samples.length; index += 1) {
      peak = Math.max(peak, Math.abs(samples[index]));
      if (index > SAMPLE_RATE * 0.15 && index < SAMPLE_RATE * 0.35 && samples[index - 1] < 0 && samples[index] >= 0) crossings.push(index);
    }
    assert.ok(peak > 0.1 && peak < 0.95, `${kind} peak ${peak}`);
    const measured = SAMPLE_RATE * (crossings.length - 1) / (crossings.at(-1) - crossings[0]);
    assert.ok(Math.abs(measured - 440) < 3, `${kind} root estimate ${measured}`);
  }
  assert.equal(noteFrequency('a4'), 440);
  assert.throws(() => noteFrequency('unknown'), /Invalid note/);
});
