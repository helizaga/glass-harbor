import { readFileSync, statSync } from 'node:fs';

function readAscii(buffer, start, end) {
  return buffer.toString('ascii', start, end);
}

export function inspectRenderedWav(filePath) {
  const stat = statSync(filePath);
  const buffer = readFileSync(filePath);
  if (buffer.length < 44 || readAscii(buffer, 0, 4) !== 'RIFF' || readAscii(buffer, 8, 12) !== 'WAVE') {
    return {
      file_path: filePath,
      bytes: stat.size,
      valid: false,
      reason: 'invalid_wav_header',
      duration_seconds: 0,
      sample_rate: 0,
      channels: 0,
      bits_per_sample: 0,
      peak: 0,
      rms: 0,
      silent: true,
    };
  }

  const channels = buffer.readUInt16LE(22);
  const sampleRate = buffer.readUInt32LE(24);
  const bitsPerSample = buffer.readUInt16LE(34);
  const dataSize = buffer.readUInt32LE(40);
  const dataStart = 44;
  const bytesPerSample = bitsPerSample / 8;
  const frameCount = channels > 0 && bytesPerSample > 0 ? Math.floor(dataSize / (channels * bytesPerSample)) : 0;

  if (bitsPerSample !== 16) {
    return {
      file_path: filePath,
      bytes: stat.size,
      valid: true,
      reason: 'unsupported_bit_depth',
      duration_seconds: sampleRate > 0 ? frameCount / sampleRate : 0,
      sample_rate: sampleRate,
      channels,
      bits_per_sample: bitsPerSample,
      peak: null,
      rms: null,
      silent: false,
    };
  }

  let peak = 0;
  let sumSquares = 0;
  let samples = 0;
  for (let offset = dataStart; offset + 1 < Math.min(buffer.length, dataStart + dataSize); offset += 2) {
    const sample = buffer.readInt16LE(offset);
    const magnitude = Math.abs(sample);
    if (magnitude > peak) {
      peak = magnitude;
    }
    sumSquares += sample * sample;
    samples += 1;
  }

  const rms = samples > 0 ? Math.sqrt(sumSquares / samples) : 0;
  return {
    file_path: filePath,
    bytes: stat.size,
    valid: true,
    reason: null,
    duration_seconds: sampleRate > 0 ? frameCount / sampleRate : 0,
    sample_rate: sampleRate,
    channels,
    bits_per_sample: bitsPerSample,
    peak,
    rms,
    silent: peak === 0 || rms === 0,
  };
}
