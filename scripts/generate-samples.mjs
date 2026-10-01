import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const outputRoot = join(root, 'samples', 'edm-core');

rmSync(outputRoot, { recursive: true, force: true });
mkdirSync(outputRoot, { recursive: true });

const sampleRate = 44100;

function clamp(value) {
  return Math.max(-1, Math.min(1, value));
}

function writeWav(filePath, samples) {
  const pcm = Buffer.alloc(samples.length * 2);

  for (let i = 0; i < samples.length; i += 1) {
    const int = Math.round(clamp(samples[i]) * 32767);
    pcm.writeInt16LE(int, i * 2);
  }

  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36);
  header.writeUInt32LE(pcm.length, 40);

  writeFileSync(filePath, Buffer.concat([header, pcm]));
}

function envelope(index, length, attack = 0.002, decay = 1) {
  const t = index / sampleRate;
  const total = length / sampleRate;
  const attackValue = Math.min(1, t / attack);
  const decayValue = Math.pow(Math.max(0, 1 - t / total), decay);
  return attackValue * decayValue;
}

function noise() {
  return Math.random() * 2 - 1;
}

function render(durationSeconds, sampleFn) {
  const length = Math.floor(sampleRate * durationSeconds);
  const samples = new Float32Array(length);

  for (let index = 0; index < length; index += 1) {
    samples[index] = sampleFn(index, length);
  }

  return samples;
}

function smooth(samples) {
  const out = new Float32Array(samples.length);
  let previous = 0;
  for (let index = 0; index < samples.length; index += 1) {
    previous = previous * 0.88 + samples[index] * 0.12;
    out[index] = previous;
  }
  return out;
}

function highpassish(samples) {
  const out = new Float32Array(samples.length);
  let previousInput = 0;
  let previousOutput = 0;
  const alpha = 0.92;
  for (let index = 0; index < samples.length; index += 1) {
    const input = samples[index];
    const output = alpha * (previousOutput + input - previousInput);
    out[index] = output;
    previousInput = input;
    previousOutput = output;
  }
  return out;
}

function makeKick(variant) {
  return render(0.82, (index, length) => {
    const t = index / sampleRate;
    const env = envelope(index, length, 0.001, 2.6);
    const freq = 152 * Math.exp(-t * (7.2 + variant * 0.3)) + 36;
    const phase = 2 * Math.PI * freq * t;
    const body = Math.sin(phase) * 0.94;
    const click = Math.sin(2 * Math.PI * (2200 + variant * 140) * t) * Math.exp(-t * 55) * 0.18;
    return (body + click) * env;
  });
}

function makeClap(variant) {
  const raw = render(0.5, (index, length) => {
    const t = index / sampleRate;
    const burst = Math.exp(-t * (18 + variant * 1.5));
    const flutter = (Math.sin(2 * Math.PI * 28 * t) * 0.5 + 0.5) * 0.18 + 0.82;
    return noise() * burst * flutter * envelope(index, length, 0.001, 1.2);
  });
  return highpassish(raw);
}

function makeHatClosed(variant) {
  const raw = render(0.14, (index, length) => {
    const t = index / sampleRate;
    const tone = Math.sin(2 * Math.PI * (7000 + variant * 450) * t) * 0.08;
    return (noise() * 0.9 + tone) * envelope(index, length, 0.0008, 1.7);
  });
  return highpassish(raw);
}

function makeHatOpen(variant) {
  const raw = render(0.42, (index, length) => {
    const t = index / sampleRate;
    const tone = Math.sin(2 * Math.PI * (5400 + variant * 180) * t) * 0.08;
    return (noise() * 0.84 + tone) * envelope(index, length, 0.001, 1.3);
  });
  return highpassish(raw);
}

function makePercTop(variant) {
  return render(0.24, (index, length) => {
    const t = index / sampleRate;
    const env = envelope(index, length, 0.001, 1.5);
    const body = Math.sin(2 * Math.PI * (880 + variant * 120) * t) * 0.5;
    const over = Math.sin(2 * Math.PI * (1760 + variant * 90) * t) * 0.22;
    return (body + over) * env;
  });
}

function makeImpactWide() {
  return smooth(
    render(1.8, (index, length) => {
      const t = index / sampleRate;
      const env = envelope(index, length, 0.002, 1.1);
      const boom = Math.sin(2 * Math.PI * (52 * Math.exp(-t * 1.2) + 24) * t) * 0.7;
      const wash = noise() * Math.exp(-t * 2.1) * 0.34;
      return (boom + wash) * env;
    }),
  );
}

function makeRiser() {
  return smooth(
    render(3.2, (index, length) => {
      const t = index / sampleRate;
      const norm = index / length;
      const env = Math.pow(norm, 1.4);
      const sweep = Math.sin(2 * Math.PI * (180 + norm * 3200) * t) * 0.18;
      const wash = noise() * (0.08 + norm * 0.38);
      return (sweep + wash) * env * 0.7;
    }),
  );
}

function makeShimmer() {
  const raw = render(1.5, (index, length) => {
    const t = index / sampleRate;
    const env = envelope(index, length, 0.002, 1.15);
    const sparkle =
      Math.sin(2 * Math.PI * 2200 * t) * 0.22 +
      Math.sin(2 * Math.PI * 3300 * t) * 0.18 +
      Math.sin(2 * Math.PI * 4400 * t) * 0.12;
    return (sparkle + noise() * 0.06) * env;
  });
  return highpassish(raw);
}

function makeAirTexture() {
  return smooth(
    render(4.4, (index, length) => {
      const t = index / sampleRate;
      const drift = Math.sin(2 * Math.PI * 0.21 * t) * 0.15 + 0.85;
      return noise() * 0.16 * drift * envelope(index, length, 0.4, 0.8);
    }),
  );
}

function makeVocalChop() {
  return render(0.42, (index, length) => {
    const t = index / sampleRate;
    const env = envelope(index, length, 0.004, 1.5);
    const carrier = Math.sin(2 * Math.PI * 310 * t) * 0.42;
    const formantA = Math.sin(2 * Math.PI * 930 * t) * 0.22;
    const formantB = Math.sin(2 * Math.PI * 1560 * t) * 0.18;
    const vibrato = Math.sin(2 * Math.PI * 6.2 * t) * 0.02 + 1;
    return (carrier * vibrato + formantA + formantB) * env;
  });
}

function makeBassTonal(variant) {
  return smooth(
    render(1.1, (index, length) => {
      const t = index / sampleRate;
      const env = envelope(index, length, 0.003, 1.45);
      const base = variant === 0 ? 49 : 55;
      const wobble = Math.sin(2 * Math.PI * 2.2 * t) * 0.5 + 0.5;
      const body = Math.sin(2 * Math.PI * base * t) * 0.82;
      const over = Math.sin(2 * Math.PI * base * 2 * t) * (0.14 + wobble * 0.08);
      return (body + over) * env;
    }),
  );
}

function makeStabTonal(variant) {
  return smooth(
    render(0.72, (index, length) => {
      const t = index / sampleRate;
      const env = envelope(index, length, 0.002, 1.8);
      const freq = variant === 0 ? 261.63 : 329.63;
      const body =
        Math.sin(2 * Math.PI * freq * t) * 0.48 +
        Math.sin(2 * Math.PI * freq * 2 * t) * 0.24 +
        Math.sin(2 * Math.PI * freq * 3 * t) * 0.12;
      return body * env;
    }),
  );
}

function makePluckTonal(variant) {
  return smooth(
    render(0.84, (index, length) => {
      const t = index / sampleRate;
      const env = envelope(index, length, 0.001, 2.2);
      const freq = variant === 0 ? 523.25 : 659.25;
      const body =
        Math.sin(2 * Math.PI * freq * t) * 0.4 +
        Math.sin(2 * Math.PI * freq * 2 * t) * 0.18 +
        Math.sin(2 * Math.PI * freq * 4 * t) * 0.08;
      return body * env;
    }),
  );
}

function noteKeyToFrequency(note) {
  const match = `${note ?? ''}`.match(/^([A-Ga-g])([#b]?)(-?\d+)$/);
  if (!match) {
    throw new Error(`Invalid note key: ${note}`);
  }
  const base = {
    c: 0,
    d: 2,
    e: 4,
    f: 5,
    g: 7,
    a: 9,
    b: 11,
  }[match[1].toLowerCase()];
  const accidental = match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0;
  const octave = Number.parseInt(match[3], 10);
  const midi = (octave + 1) * 12 + base + accidental;
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function makeBassPitched(noteKey, variant = 0) {
  const base = noteKeyToFrequency(noteKey);
  return smooth(
    render(0.92, (index, length) => {
      const t = index / sampleRate;
      const env = envelope(index, length, 0.002, 1.55);
      const wobble = Math.sin(2 * Math.PI * (1.8 + variant * 0.2) * t) * 0.5 + 0.5;
      const body = Math.sin(2 * Math.PI * base * t) * 0.82;
      const over = Math.sin(2 * Math.PI * base * 2 * t) * (0.12 + wobble * 0.08);
      return (body + over) * env;
    }),
  );
}

const families = {
  kick_main: [makeKick(0), makeKick(1)],
  clap_main: [makeClap(0), makeClap(1)],
  hat_closed: [makeHatClosed(0), makeHatClosed(1), makeHatClosed(2), makeHatClosed(3)],
  hat_open: [makeHatOpen(0), makeHatOpen(1)],
  perc_top: [makePercTop(0), makePercTop(1)],
  impact_wide: [makeImpactWide()],
  riser_up: [makeRiser()],
  shimmer_fx: [makeShimmer()],
  air_texture: [makeAirTexture()],
  vocal_chop: [makeVocalChop()],
  bass_tonal: [makeBassTonal(0), makeBassTonal(1)],
  stab_tonal: [makeStabTonal(0), makeStabTonal(1)],
  pluck_tonal: [makePluckTonal(0), makePluckTonal(1)],
  bass_pitched: {
    a1: [makeBassPitched('A1', 0)],
    c2: [makeBassPitched('C2', 1)],
    e2: [makeBassPitched('E2', 0)],
  },
};

for (const [family, renders] of Object.entries(families)) {
  const familyDir = join(outputRoot, family);
  mkdirSync(familyDir, { recursive: true });

  if (Array.isArray(renders)) {
    renders.forEach((samples, index) => {
      writeWav(join(familyDir, `${index}.wav`), samples);
    });
    continue;
  }

  for (const [note, noteRenders] of Object.entries(renders)) {
    noteRenders.forEach((samples, index) => {
      writeWav(join(familyDir, `${note.toLowerCase()}-${index}.wav`), samples);
    });
  }
}
