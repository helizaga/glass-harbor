import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
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
const publicFallbackRoot = resolve(root, readArg('--fallback-root', 'samples/edm-core'));
const publicFallbackBaseUrl = readArg('--fallback-base-url', '/samples/edm-core');
const compareNatural = (left, right) => left.localeCompare(right, undefined, { numeric: true });

function assertInsideRoot(rootPath, candidatePath, label) {
  const rel = relative(rootPath, candidatePath);
  const escapesRoot = rel.startsWith('..') || rel.includes(`${sep}..${sep}`) || rel === '..';
  if (escapesRoot || rel === '') {
    if (rel === '') {
      return;
    }
    throw new Error(`${label} must stay inside ${rootPath}`);
  }
}

function buildManifestFromRoot(rootPath, baseUrl) {
  if (!existsSync(rootPath)) {
    return {};
  }

  const families = readdirSync(rootPath, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .sort((left, right) => compareNatural(left.name, right.name));

  return Object.fromEntries(
    families.map((entry) => {
      const files = readdirSync(resolve(rootPath, entry.name), { withFileTypes: true })
        .filter((file) => file.isFile() && /\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(file.name))
        .map((file) => `${baseUrl}/${entry.name}/${file.name}`)
        .sort(compareNatural);
      return [entry.name, files];
    }),
  );
}

if (!existsSync(mapPath)) {
  throw new Error(`Missing local import map at ${mapPath}. Run npm run vendor:init first.`);
}

if (!existsSync(sourceRoot)) {
  throw new Error(`Missing source root at ${sourceRoot}. Copy your private vendor files there first.`);
}

if (!existsSync(publicFallbackRoot)) {
  throw new Error(`Missing public fallback pack root at ${publicFallbackRoot}`);
}

const mapping = JSON.parse(readFileSync(mapPath, 'utf8'));
const families = mapping.families ?? {};
const unknownFamilies = Object.keys(families).filter((family) => !allowedFamilies.has(family));

if (unknownFamilies.length > 0) {
  throw new Error(`Unknown runtime families in import map: ${unknownFamilies.join(', ')}`);
}

rmSync(targetRoot, { recursive: true, force: true });
mkdirSync(targetRoot, { recursive: true });

let importedFamilyCount = 0;

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
  importedFamilyCount += 1;

  entries.forEach((relativePath, index) => {
    if (typeof relativePath !== 'string' || relativePath.trim() === '') {
      throw new Error(`Family ${family} has an invalid source entry at index ${index}.`);
    }

    const sourcePath = resolve(sourceRoot, relativePath);
    assertInsideRoot(sourceRoot, sourcePath, `Source file for ${family}`);
    if (!existsSync(sourcePath)) {
      throw new Error(`Missing source file for ${family}: ${relativePath}`);
    }

    const extMatch = sourcePath.match(/\.[^.]+$/);
    const extension = extMatch ? extMatch[0].toLowerCase() : '.wav';
    const targetPath = resolve(familyDir, `${index}${extension}`);
    cpSync(sourcePath, targetPath);
  });
}

if (importedFamilyCount === 0) {
  throw new Error('Import map does not enable any private runtime families.');
}

const privateManifest = buildManifestFromRoot(targetRoot, baseUrl);
const publicManifest = buildManifestFromRoot(publicFallbackRoot, publicFallbackBaseUrl);
const manifest = Object.fromEntries(
  [...allowedFamilies]
    .sort(compareNatural)
    .map((family) => [family, privateManifest[family] && privateManifest[family].length > 0
      ? privateManifest[family]
      : publicManifest[family] ?? []]),
);

const missingFamilies = [...allowedFamilies].filter((family) => !manifest[family] || manifest[family].length === 0);
if (missingFamilies.length > 0) {
  throw new Error(`Merged runtime pack is missing required families: ${missingFamilies.join(', ')}`);
}

writeFileSync(resolve(targetRoot, 'strudel.json'), `${JSON.stringify(manifest, null, 2)}\n`);

console.log('Imported private pack overlay:');
console.log(`- vendor source: ${sourceRoot}`);
console.log(`- local map: ${mapPath}`);
console.log(`- runtime pack: ${targetRoot}`);
console.log(`- imported families: ${importedFamilyCount}`);
