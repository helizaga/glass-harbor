import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
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

const sourceRoot = resolve(root, readArg('--source', 'private-packs/vendor-sources/kshmr-vol-4/raw'));
const mapPath = resolve(root, readArg('--map', 'private-packs/vendor-sources/kshmr-vol-4/import-map.json'));
const targetRoot = resolve(root, readArg('--target', 'private-packs/runtime/edm-core'));
const baseUrl = readArg('--base-url', '/private-packs/runtime/edm-core');
const allowedFamilies = new Set([
  'kick_main',
  'clap_main',
  'hat_closed',
  'hat_open',
  'perc_top',
  'impact_wide',
  'riser_up',
  'shimmer_fx',
  'air_texture',
  'vocal_chop',
]);

if (!existsSync(mapPath)) {
  throw new Error(`Missing local import map at ${mapPath}. Run npm run vendor:init first.`);
}

if (!existsSync(sourceRoot)) {
  throw new Error(`Missing source root at ${sourceRoot}. Copy your private vendor files there first.`);
}

const mapping = JSON.parse(readFileSync(mapPath, 'utf8'));
const families = mapping.families ?? {};
const unknownFamilies = Object.keys(families).filter((family) => !allowedFamilies.has(family));

if (unknownFamilies.length > 0) {
  throw new Error(`Unknown runtime families in import map: ${unknownFamilies.join(', ')}`);
}

rmSync(targetRoot, { recursive: true, force: true });
mkdirSync(targetRoot, { recursive: true });

for (const family of allowedFamilies) {
  const entries = families[family] ?? [];
  if (!Array.isArray(entries)) {
    throw new Error(`Family ${family} must be an array of relative source paths.`);
  }

  if (entries.length === 0) {
    continue;
  }

  const familyDir = resolve(targetRoot, family);
  mkdirSync(familyDir, { recursive: true });

  entries.forEach((relativePath, index) => {
    if (typeof relativePath !== 'string' || relativePath.trim() === '') {
      throw new Error(`Family ${family} has an invalid source entry at index ${index}.`);
    }

    const sourcePath = resolve(sourceRoot, relativePath);
    if (!existsSync(sourcePath)) {
      throw new Error(`Missing source file for ${family}: ${relativePath}`);
    }

    const extMatch = sourcePath.match(/\.[^.]+$/);
    const extension = extMatch ? extMatch[0].toLowerCase() : '.wav';
    const targetPath = resolve(familyDir, `${index}${extension}`);
    cpSync(sourcePath, targetPath);
  });
}

const manifestFamilies = readdirSync(targetRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .sort((left, right) => left.name.localeCompare(right.name));

const manifest = Object.fromEntries(
  manifestFamilies.map((entry) => {
    const files = readdirSync(resolve(targetRoot, entry.name), { withFileTypes: true })
      .filter((file) => file.isFile() && /\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(file.name))
      .map((file) => `${baseUrl}/${entry.name}/${file.name}`)
      .sort((left, right) => left.localeCompare(right));
    return [entry.name, files];
  }),
);

writeFileSync(resolve(targetRoot, 'strudel.json'), `${JSON.stringify(manifest, null, 2)}\n`);

console.log('Imported private pack overlay:');
console.log(`- vendor source: ${sourceRoot}`);
console.log(`- local map: ${mapPath}`);
console.log(`- runtime pack: ${targetRoot}`);
