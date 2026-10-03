import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { basename, isAbsolute, relative, resolve, sep } from 'node:path';

import { ALL_ALLOWED_SAMPLE_ROLES, STABLE_SOUND_ROLES } from './song-contract.mjs';

export const DEFAULT_LOCAL_PACK_SUBDIRS = [
  'kicks',
  'claps',
  'hats',
  'perc',
  'bass',
  'stabs',
  'leads',
  'textures',
  'vocals',
  'risers',
  'impacts',
  'shimmer',
];

export function compareNatural(left, right) {
  return left.localeCompare(right, undefined, { numeric: true });
}

export function assertInsideRoot(rootPath, candidatePath, label) {
  const rel = relative(rootPath, candidatePath);
  const escapesRoot = isAbsolute(rel) || rel === '..' || rel.startsWith(`..${sep}`);
  if (escapesRoot) {
    throw new Error(`${label} must stay inside ${rootPath}`);
  }
}

export function buildManifestFromRoot(rootPath, baseUrl) {
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
        .map((file) => file.name)
        .sort(compareNatural);

      const noteMatches = files.map((fileName) => fileName.match(/^([a-g](?:#|b)?\d+)-\d+\.[^.]+$/i));
      if (files.length > 0 && noteMatches.every(Boolean)) {
        const grouped = {};
        files.forEach((fileName, index) => {
          const note = noteMatches[index][1];
          grouped[note] ??= [];
          grouped[note].push(`${baseUrl}/${entry.name}/${fileName}`);
        });
        return [
          entry.name,
          Object.fromEntries(
            Object.entries(grouped).map(([note, urls]) => [note, urls.length === 1 ? urls[0] : urls]),
          ),
        ];
      }

      return [entry.name, files.map((fileName) => `${baseUrl}/${entry.name}/${fileName}`)];
    }),
  );
}

function sanitizeFileToken(value) {
  return `${value ?? ''}`
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function manifestEntryHasSamples(entry) {
  if (Array.isArray(entry)) {
    return entry.length > 0;
  }

  if (entry && typeof entry === 'object') {
    return Object.values(entry).some((value) => normalizeFamilyEntryList('manifest', value).length > 0);
  }

  return false;
}

function normalizeFamilyEntryList(family, value) {
  if (typeof value === 'string') {
    return [value];
  }
  if (Array.isArray(value)) {
    return value;
  }
  throw new Error(`Family ${family} must be an array of relative source paths or a note-keyed object.`);
}

function copyMappedEntry({ family, sourceRoot, familyDir, relativePath, targetStem }) {
  if (typeof relativePath !== 'string' || relativePath.trim() === '') {
    throw new Error(`Family ${family} has an invalid source entry.`);
  }

  const sourcePath = resolve(sourceRoot, relativePath);
  assertInsideRoot(sourceRoot, sourcePath, `Source file for ${family}`);
  if (!existsSync(sourcePath)) {
    throw new Error(`Missing source file for ${family}: ${relativePath}`);
  }

  const extMatch = sourcePath.match(/\.[^.]+$/);
  const extension = extMatch ? extMatch[0].toLowerCase() : '.wav';
  const targetPath = resolve(familyDir, `${targetStem}${extension}`);
  cpSync(sourcePath, targetPath);
  return { targetPath, extension };
}

function importFamilyEntries({ family, entries, sourceRoot, familyDir, baseUrl }) {
  if (Array.isArray(entries)) {
    const urls = [];
    entries.forEach((relativePath, index) => {
      copyMappedEntry({
        family,
        sourceRoot,
        familyDir,
        relativePath,
        targetStem: `${index}`,
      });
      const sourcePath = resolve(sourceRoot, relativePath);
      const extMatch = sourcePath.match(/\.[^.]+$/);
      const extension = extMatch ? extMatch[0].toLowerCase() : '.wav';
      urls.push(`${baseUrl}/${family}/${index}${extension}`);
    });
    return {
      manifestEntry: urls,
      importedFileCount: urls.length,
    };
  }

  if (!entries || typeof entries !== 'object') {
    throw new Error(`Family ${family} must be an array of relative source paths or a note-keyed object.`);
  }

  const manifestEntry = {};
  let importedFileCount = 0;
  for (const [note, rawPaths] of Object.entries(entries)) {
    const noteKey = `${note ?? ''}`.trim();
    if (!noteKey) {
      throw new Error(`Family ${family} has an empty note key.`);
    }

    const sourceList = normalizeFamilyEntryList(family, rawPaths);
    const noteUrls = sourceList.map((relativePath, index) => {
      const noteStem = `${sanitizeFileToken(noteKey)}-${index}`;
      const copied = copyMappedEntry({
        family,
        sourceRoot,
        familyDir,
        relativePath,
        targetStem: noteStem,
      });
      importedFileCount += 1;
      return `${baseUrl}/${family}/${basename(copied.targetPath)}`;
    });
    manifestEntry[noteKey] = noteUrls.length === 1 ? noteUrls[0] : noteUrls;
  }

  return {
    manifestEntry,
    importedFileCount,
  };
}

export function initPackOverlayWorkspace({
  rawRoot,
  runtimeRoot,
  mapTarget,
  mapTemplate,
  prepPlanTarget = null,
  prepPlanTemplate = null,
  rawSubdirs = [],
  label = 'pack overlay',
}) {
  for (const subdir of rawSubdirs) {
    mkdirSync(resolve(rawRoot, subdir), { recursive: true });
  }
  mkdirSync(runtimeRoot, { recursive: true });

  if (!existsSync(mapTemplate)) {
    throw new Error(`Missing import map template at ${mapTemplate}`);
  }
  if (!existsSync(mapTarget)) {
    cpSync(mapTemplate, mapTarget);
  }

  if (prepPlanTarget && prepPlanTemplate) {
    if (!existsSync(prepPlanTemplate)) {
      throw new Error(`Missing prep plan template at ${prepPlanTemplate}`);
    }
    if (!existsSync(prepPlanTarget)) {
      cpSync(prepPlanTemplate, prepPlanTarget);
    }
  }

  console.log(`Initialized ${label} workspace:`);
  console.log(`- raw source: ${rawRoot}`);
  console.log(`- local import map: ${mapTarget}`);
  if (prepPlanTarget) {
    console.log(`- local prep plan: ${prepPlanTarget}`);
  }
  console.log(`- runtime output: ${runtimeRoot}`);
}

export function importPackOverlay({
  sourceRoot,
  mapPath,
  targetRoot,
  baseUrl,
  publicFallbackRoot,
  publicFallbackBaseUrl,
  label = 'pack overlay',
}) {
  if (!existsSync(mapPath)) {
    throw new Error(`Missing import map at ${mapPath}. Initialize the workspace first.`);
  }
  if (!existsSync(sourceRoot)) {
    throw new Error(`Missing source root at ${sourceRoot}. Copy or prep your source audio first.`);
  }
  if (!existsSync(publicFallbackRoot)) {
    throw new Error(`Missing public fallback pack root at ${publicFallbackRoot}`);
  }

  const mapping = JSON.parse(readFileSync(mapPath, 'utf8'));
  const families = mapping.families ?? {};
  const allowedFamilies = new Set(ALL_ALLOWED_SAMPLE_ROLES);
  const unknownFamilies = Object.keys(families).filter((family) => !allowedFamilies.has(family));
  if (unknownFamilies.length > 0) {
    throw new Error(`Unknown runtime families in import map: ${unknownFamilies.join(', ')}`);
  }

  mkdirSync(targetRoot, { recursive: true });

  let importedFileCount = 0;
  let importedFamilyCount = 0;
  for (const family of allowedFamilies) {
    const entries = families[family] ?? [];
    if (!Array.isArray(entries) && (!entries || typeof entries !== 'object')) {
      throw new Error(`Family ${family} must be an array of relative source paths or a note-keyed object.`);
    }

    const familyDir = resolve(targetRoot, family);
    rmSync(familyDir, { recursive: true, force: true });
    const hasEntries = Array.isArray(entries) ? entries.length > 0 : Object.keys(entries).length > 0;
    if (!hasEntries) {
      continue;
    }

    mkdirSync(familyDir, { recursive: true });
    importedFamilyCount += 1;
    const imported = importFamilyEntries({
      family,
      entries,
      sourceRoot,
      familyDir,
      baseUrl,
    });
    importedFileCount += imported.importedFileCount;
  }

  const privateManifest = buildManifestFromRoot(targetRoot, baseUrl);
  const publicManifest = buildManifestFromRoot(publicFallbackRoot, publicFallbackBaseUrl);
  const allFamilies = new Set([...Object.keys(publicManifest), ...Object.keys(privateManifest)]);
  const manifest = Object.fromEntries(
    [...allFamilies]
      .sort(compareNatural)
      .map((family) => [
        family,
        manifestEntryHasSamples(privateManifest[family]) ? privateManifest[family] : publicManifest[family] ?? [],
      ]),
  );

  const missingFamilies = STABLE_SOUND_ROLES.filter((family) => !manifest[family] || manifest[family].length === 0);
  if (missingFamilies.length > 0) {
    throw new Error(`Merged runtime pack is missing required families: ${missingFamilies.join(', ')}`);
  }

  writeFileSync(resolve(targetRoot, 'strudel.json'), `${JSON.stringify(manifest, null, 2)}\n`);

  console.log(`Imported ${label}:`);
  console.log(`- source root: ${sourceRoot}`);
  console.log(`- import map: ${mapPath}`);
  console.log(`- runtime pack: ${targetRoot}`);
  console.log(`- imported families: ${importedFamilyCount}`);
  console.log(`- imported files: ${importedFileCount}`);

  return {
    manifestPath: resolve(targetRoot, 'strudel.json'),
    importedFamilyCount,
    importedFileCount,
  };
}

export function summarizeOverlayMap(mapPath) {
  if (!existsSync(mapPath)) {
    return null;
  }

  const mapping = JSON.parse(readFileSync(mapPath, 'utf8'));
  const families = mapping.families ?? {};
  const enabledFamilies = Object.fromEntries(
    Object.entries(families)
      .filter(([, entries]) => {
        if (Array.isArray(entries)) {
          return entries.length > 0;
        }
        return entries && typeof entries === 'object' && Object.keys(entries).length > 0;
      })
      .sort(([left], [right]) => compareNatural(left, right))
      .map(([family, entries]) => [
        family,
        Array.isArray(entries)
          ? entries.map((entry) => ({
              path: entry,
              file: basename(entry),
            }))
          : Object.entries(entries).flatMap(([note, value]) =>
              normalizeFamilyEntryList(family, value).map((entry) => ({
                note,
                path: entry,
                file: basename(entry),
              })),
            ),
      ]),
  );

  return {
    map_path: mapPath,
    enabled_families: enabledFamilies,
  };
}
