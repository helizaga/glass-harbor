export const SAMPLE_RATE = 44100;

export function noteFrequency(note) {
  const match = note.match(/^([a-g])([#b]?)(-?\d+)$/i);
  if (!match) throw new Error(`Invalid note key: ${note}`);
  const semitone = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[match[1].toLowerCase()];
  const accidental = match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0;
  return 440 * 2 ** (((Number(match[3]) + 1) * 12 + semitone + accidental - 69) / 12);
}

/** Original fallback instruments: a filtered detuned pad, FM pluck and rounded sub bass. */
export function renderPitchedTone(note, kind) {
  if (!['pad', 'pluck', 'bass'].includes(kind)) throw new Error(`Unknown pitched instrument: ${kind}`);
  const duration = { pad: 4, pluck: 1.8, bass: 1.2 }[kind];
  const length = Math.round(SAMPLE_RATE * duration);
  const frequency = noteFrequency(note);
  const samples = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const t = index / SAMPLE_RATE;
    const attack = Math.min(1, t / { pad: 0.08, pluck: 0.003, bass: 0.005 }[kind]);
    const release = Math.min(1, (length - 1 - index) / (SAMPLE_RATE * { pad: 0.4, pluck: 0.08, bass: 0.16 }[kind]));
    const envelope = attack * release * Math.exp(-t * { pad: 0.08, pluck: 3.8, bass: 1.1 }[kind]);
    const phase = 2 * Math.PI * frequency * t;
    let tone = 0;
    if (kind === 'pad') {
      // Band-limited saw partials with slow filter motion; no baked chord or FX tail.
      const cutoff = 1300 + 450 * Math.sin(2 * Math.PI * 0.18 * t);
      for (let harmonic = 1; harmonic <= 24; harmonic += 1) {
        if (frequency * harmonic * 1.003 > SAMPLE_RATE / 2) break;
        const amplitude = Math.exp(-((frequency * harmonic / cutoff) ** 2)) / harmonic;
        tone += amplitude * (Math.sin(phase * harmonic) * 0.5 +
          Math.sin(phase * harmonic * 2 ** (3.5 / 1200) + 0.2) * 0.25 +
          Math.sin(phase * harmonic * 2 ** (-3.5 / 1200) - 0.2) * 0.25);
      }
    } else if (kind === 'pluck') {
      // A bright, percussive FM transient settles into a clean fundamental.
      const modulation = (2.4 * Math.exp(-t * 14) + 0.12) * Math.sin(phase * 2);
      tone = Math.sin(phase) * 0.64 + Math.sin(phase + modulation) * 0.3 +
        Math.sin(phase * 3) * 0.06 * Math.exp(-t * 9);
    } else {
      // Stable fundamental with a little short-lived upper-body attack.
      tone = Math.sin(phase) * 0.8 + Math.sin(phase * 2) * 0.12 * Math.exp(-t * 8) -
        Math.sin(phase * 3) * 0.05;
    }
    samples[index] = Math.tanh(tone * (kind === 'bass' ? 1.6 : 1.1)) * envelope * 0.72;
  }
  return samples;
}
