import { existsSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const args = process.argv.slice(2);

function readArg(name, fallback) {
  const index = args.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return args[index + 1] ?? fallback;
}

const sampleRoot = resolve(root, readArg('--root', 'samples/edm-core'));
const baseUrl = readArg('--base-url', '/samples/edm-core');
const compareNatural = (left, right) => left.localeCompare(right, undefined, { numeric: true });

if (!existsSync(sampleRoot)) {
  throw new Error(`Pack root does not exist: ${sampleRoot}`);
}

const familyEntries = readdirSync(sampleRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .sort((left, right) => compareNatural(left.name, right.name));

if (familyEntries.length === 0) {
  throw new Error(`No sample families found under ${sampleRoot}`);
}

const manifest = Object.fromEntries(
  familyEntries.map((entry) => {
    const familyDir = join(sampleRoot, entry.name);
    const files = readdirSync(familyDir, { withFileTypes: true })
      .filter((file) => file.isFile() && /\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(file.name))
      .map((file) => `${baseUrl}/${entry.name}/${file.name}`)
      .sort(compareNatural);

    if (files.length === 0) {
      throw new Error(`Sample family ${entry.name} has no audio files in ${familyDir}`);
    }

    return [entry.name, files];
  }),
);

writeFileSync(join(sampleRoot, 'strudel.json'), `${JSON.stringify(manifest, null, 2)}\n`);
