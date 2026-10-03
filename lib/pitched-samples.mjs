export const SAMPLE_RATE = 44100;

export function noteFrequency(note) {
  const match = note.match(/^([a-g])([#b]?)(-?\d+)$/i);
  if (!match) throw new Error(`Invalid note key: ${note}`);
  const semitone = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[match[1].toLowerCase()];
  const accidental = match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0;
  return 440 * 2 ** (((Number(match[3]) + 1) * 12 + semitone + accidental - 69) / 12);
}

/** Original, root-labelled tones. Detuned partials add movement without baking in a chord. */
export function renderPitchedTone(note, kind) {
  const pad = kind === 'pad';
  const duration = pad ? 4 : 1.6;
  const length = Math.round(SAMPLE_RATE * duration);
  const frequency = noteFrequency(note);
  const samples = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const t = index / SAMPLE_RATE;
    const attack = Math.min(1, t / (pad ? 0.12 : 0.006));
    const release = Math.min(1, (length - 1 - index) / (SAMPLE_RATE * (pad ? 0.45 : 0.08)));
    const envelope = attack * release * Math.exp(-t * (pad ? 0.18 : 3.2));
    let tone = 0;
    for (let harmonic = 1; harmonic <= 10; harmonic += 1) {
      if (frequency * harmonic > SAMPLE_RATE / 2) break;
      const brightness = Math.exp(-t * harmonic * (pad ? 0.05 : 0.7));
      const amplitude = brightness / harmonic ** 1.6;
      const phase = 2 * Math.PI * frequency * harmonic * t;
      tone += amplitude * (Math.sin(phase) * 0.7 +
        Math.sin(phase * 2 ** (4 / 1200) + 0.3) * 0.15 +
        Math.sin(phase * 2 ** (-4 / 1200) - 0.3) * 0.15);
    }
    samples[index] = Math.tanh(tone * 1.1) * envelope * 0.72;
  }
  return samples;
}
