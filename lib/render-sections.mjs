import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { assertInsideRoot } from './pack-overlay.mjs';

/** Split the renderer's PCM WAV without resetting effects or adding fades at section boundaries. */
export function writeRenderedSections(mixPath, sections, outputDir) {
  const mix = readFileSync(mixPath);
  if (mix.length < 44 || mix.toString('ascii', 0, 4) !== 'RIFF' || mix.toString('ascii', 36, 40) !== 'data') {
    throw new Error('Expected the offline renderer\'s PCM WAV header.');
  }
  const blockAlign = mix.readUInt16LE(32);
  const totalCycles = sections.at(-1)?.end;
  const dataSize = mix.readUInt32LE(40);
  if (!blockAlign || !(totalCycles > 0) || dataSize % blockAlign || mix.length !== 44 + dataSize) {
    throw new Error('Invalid rendered WAV or section timeline.');
  }
  const frameCount = dataSize / blockAlign;
  return sections.map((section) => {
    const start = Math.round(section.begin / totalCycles * frameCount) * blockAlign;
    const end = Math.round(section.end / totalCycles * frameCount) * blockAlign;
    const pcm = mix.subarray(44 + start, 44 + end);
    const header = Buffer.from(mix.subarray(0, 44));
    header.writeUInt32LE(36 + pcm.length, 4);
    header.writeUInt32LE(pcm.length, 40);
    const outputPath = join(outputDir, `${section.name}.wav`);
    assertInsideRoot(outputDir, outputPath, 'Rendered section');
    writeFileSync(outputPath, Buffer.concat([header, pcm]));
    return outputPath;
  });
}
