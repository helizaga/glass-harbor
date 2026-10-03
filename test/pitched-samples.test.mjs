import assert from 'node:assert/strict';
import { test } from 'node:test';
import { noteFrequency, renderPitchedTone, SAMPLE_RATE } from '../lib/pitched-samples.mjs';

test('pitched families contain tuned, audible, unclipped tones with click-free endpoints', () => {
  for (const kind of ['pad', 'pluck', 'bass']) {
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
  assert.throws(() => renderPitchedTone('a4', 'unknown'), /Unknown pitched instrument/);
});

test('pad sustains while the hook decays, with distinct harmonic shapes', () => {
  const pad = renderPitchedTone('a4', 'pad');
  const pluck = renderPitchedTone('a4', 'pluck');
  const rms = (samples, start, end) => {
    const clip = samples.subarray(SAMPLE_RATE * start, SAMPLE_RATE * end);
    return Math.sqrt(clip.reduce((sum, value) => sum + value * value, 0) / clip.length);
  };
  assert.ok(rms(pad, 0.8, 1) / rms(pad, 0.2, 0.4) > 0.7);
  assert.ok(rms(pluck, 0.8, 1) / rms(pluck, 0.2, 0.4) < 0.2);
  // The pad has even harmonics; the FM hook has a different transient spectrum.
  const partial = (samples, harmonic) => {
    let real = 0, imaginary = 0;
    for (let i = SAMPLE_RATE * 0.02; i < SAMPLE_RATE * 0.12; i += 1) {
      const phase = 2 * Math.PI * 440 * harmonic * i / SAMPLE_RATE;
      real += samples[i] * Math.cos(phase);
      imaginary += samples[i] * Math.sin(phase);
    }
    return Math.hypot(real, imaginary);
  };
  assert.ok(partial(pad, 2) / partial(pad, 1) > 0.15);
  assert.ok(partial(pluck, 2) / partial(pluck, 1) < 0.05);
});
