import { existsSync, mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const STABLE_SOUND_ROLES = [
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
];

export const REQUIRED_SONG_METADATA = ['title', 'genre', 'bpm', 'details', 'sections'];
export const REQUIRED_BRIEF_HEADINGS = [
  'title',
  'genre',
  'mood',
  'bpm',
  'structure',
  'sonic-goals',
  'stable-sound-roles',
  'notes-for-agent',
];

const here = dirname(fileURLToPath(import.meta.url));
export const repoRoot = resolve(here, '..');
export const songsRoot = join(repoRoot, 'songs');
export const runsRoot = join(repoRoot, 'runs');
export const referencesRoot = join(repoRoot, 'references');
export const RUN_ID_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z$/;

export function sanitizeSlug(value) {
  return `${value ?? ''}`
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function titleFromSlug(slug) {
  return sanitizeSlug(slug)
    .split('-')
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

export function resolveSongSlug(argv) {
  const args = [...argv];
  for (let index = 0; index < args.length; index += 1) {
    if ((args[index] === '--song' || args[index] === '-s') && args[index + 1]) {
      return sanitizeSlug(args[index + 1]);
    }
  }

  const positional = args.find((arg) => !arg.startsWith('-'));
  return sanitizeSlug(positional);
}

export function songPaths(slug) {
  const safeSlug = sanitizeSlug(slug);
  const dir = join(songsRoot, safeSlug);
  return {
    slug: safeSlug,
    dir,
    briefPath: join(dir, `${safeSlug}.brief.md`),
    songPath: join(dir, `${safeSlug}.strudel.js`),
  };
}

export function readText(filePath) {
  return readFileSync(filePath, 'utf8');
}

export function ensureDir(dirPath) {
  mkdirSync(dirPath, { recursive: true });
  return dirPath;
}

export function formatRunId(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

export function createRunDir(slug, runId = formatRunId()) {
  const dir = join(runsRoot, sanitizeSlug(slug), runId);
  ensureDir(dir);
  ensureDir(join(dir, 'sections'));
  return dir;
}

export function isCanonicalRunDirName(value) {
  return RUN_ID_PATTERN.test(`${value ?? ''}`);
}

export function listSongRunDirs(slug, { requireRunJson = true, requiredFiles = [] } = {}) {
  const songRunRoot = join(runsRoot, sanitizeSlug(slug));
  if (!existsSync(songRunRoot)) {
    return [];
  }

  return readdirSync(songRunRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && isCanonicalRunDirName(entry.name))
    .map((entry) => join(songRunRoot, entry.name))
    .filter((dirPath) => !requireRunJson || existsSync(join(dirPath, 'run.json')))
    .filter((dirPath) => requiredFiles.every((fileName) => existsSync(join(dirPath, fileName))))
    .sort((left, right) => right.localeCompare(left));
}

export function findLatestRunDir(slug, options = {}) {
  const runs = listSongRunDirs(slug, { requireRunJson: true, ...options });
  return runs[0] ?? null;
}

export function resolveRunDir(argv, slug) {
  const runIndex = argv.indexOf('--run');
  if (runIndex !== -1 && argv[runIndex + 1]) {
    const runArg = argv[runIndex + 1];
    return isAbsolute(runArg) ? runArg : resolve(repoRoot, runArg);
  }
  return findLatestRunDir(slug);
}

export function parseSongMetadata(code) {
  const metadata = {};
  const matches = code.matchAll(/^\/\/\s*@([\w-]+)\s+(.+)$/gm);
  for (const [, key, value] of matches) {
    metadata[key.trim().toLowerCase()] = value.trim();
  }
  return metadata;
}

export function parseSections(sectionValue) {
  if (!sectionValue) {
    return [];
  }

  return sectionValue
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const match = entry.match(/^([a-z0-9-]+)\s*:\s*(\d+)$/i);
      if (!match) {
        throw new Error(`Invalid @sections entry: ${entry}`);
      }

      return {
        name: sanitizeSlug(match[1]),
        cycles: Number.parseInt(match[2], 10),
      };
    });
}

export function buildSectionTimeline(sectionDefs) {
  let begin = 0;
  return sectionDefs.map((section) => {
    const timelineEntry = {
      ...section,
      begin,
      end: begin + section.cycles,
    };
    begin = timelineEntry.end;
    return timelineEntry;
  });
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right));
}

function extractDependencyTokens(raw) {
  return uniqueSorted(
    [...`${raw ?? ''}`.toLowerCase().matchAll(/[a-z_][a-z0-9_-]*/g)].map(([token]) => token),
  );
}

export function extractSampleRoles(code) {
  return uniqueSorted(
    [...`${code ?? ''}`.matchAll(/(^|[^\w.])s\s*\(\s*(['"`])([\s\S]*?)\2\s*\)/gm)].flatMap((match) =>
      extractDependencyTokens(match[3]),
    ),
  );
}

export function extractSynthVoices(code) {
  return uniqueSorted(
    [...`${code ?? ''}`.matchAll(/\.sound\s*\(\s*(['"`])([\s\S]*?)\1\s*\)/gm)].flatMap((match) =>
      extractDependencyTokens(match[2]),
    ),
  );
}

export function validateSongCode(code) {
  const metadata = parseSongMetadata(code);
  const errors = [];
  const warnings = [];
  const dependencies = {
    sampleRoles: extractSampleRoles(code),
    synthVoices: extractSynthVoices(code),
  };

  for (const key of REQUIRED_SONG_METADATA) {
    if (!metadata[key]) {
      errors.push(`Missing @${key} metadata comment.`);
    }
  }

  let sections = [];
  try {
    sections = buildSectionTimeline(parseSections(metadata.sections));
  } catch (error) {
    errors.push(error.message);
  }

  if (!code.includes("samples('http://localhost:5432')") && !code.includes('samples("http://localhost:5432")')) {
    errors.push('Song file must target http://localhost:5432 for Strudel web paste mode.');
  }

  if (code.includes('private-packs/') || code.includes('/samples/edm-core/')) {
    errors.push('Song file must not hardcode scaffold or private-pack paths.');
  }

  if (code.includes('samples(') && !code.includes('http://localhost:5432')) {
    warnings.push('Song file uses samples(), but not the canonical localhost sample server URL.');
  }

  return {
    metadata,
    sections,
    dependencies,
    errors,
    warnings,
  };
}

export function parseBrief(markdown) {
  const lines = markdown.split(/\r?\n/);
  const brief = {};
  let currentHeading = 'title';
  brief[currentHeading] = '';

  for (const line of lines) {
    if (line.startsWith('# ')) {
      brief.title = line.slice(2).trim();
      currentHeading = 'title';
      continue;
    }

    const headingMatch = line.match(/^##\s+(.+)$/);
    if (headingMatch) {
      currentHeading = sanitizeSlug(headingMatch[1]);
      brief[currentHeading] = '';
      continue;
    }

    if (!brief[currentHeading]) {
      brief[currentHeading] = line.trim();
    } else if (line.trim()) {
      brief[currentHeading] += `\n${line.trim()}`;
    }
  }

  return brief;
}

export function validateBrief(brief) {
  const errors = [];
  for (const heading of REQUIRED_BRIEF_HEADINGS) {
    if (!brief[heading] || !`${brief[heading]}`.trim()) {
      errors.push(`Missing brief heading content for "${heading}".`);
    }
  }

  return {
    errors,
  };
}

export function listReferenceCards() {
  if (!existsSync(referencesRoot)) {
    return [];
  }

  return readdirSync(referencesRoot, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.md') && entry.name !== 'README.md')
    .map((entry) => {
      const path = join(referencesRoot, entry.name);
      const content = readText(path);
      const metadataPath = path.replace(/\.md$/, '.json');
      const metadata = existsSync(metadataPath) ? JSON.parse(readText(metadataPath)) : {};
      return {
        name: entry.name.replace(/\.md$/, ''),
        path,
        content,
        metadataPath: existsSync(metadataPath) ? metadataPath : null,
        metadata,
      };
    });
}

function tokenize(text) {
  return `${text ?? ''}`
    .toLowerCase()
    .split(/[^a-z0-9]+/g)
    .filter((token) => token.length >= 4);
}

export function selectReferenceCards(brief, limit = 3) {
  const corpusTerms = tokenize(
    [
      brief.title,
      brief.genre,
      brief.mood,
      brief.structure,
      brief['sonic-goals'],
      brief['review-goals'],
      brief['notes-for-agent'],
    ].join(' '),
  );

  const uniqueTerms = [...new Set(corpusTerms)];
  if (uniqueTerms.length === 0) {
    return listReferenceCards().slice(0, limit);
  }

  return listReferenceCards()
    .map((card) => {
      const haystack = `${card.content}\n${JSON.stringify(card.metadata)}`.toLowerCase();
      const matchedTerms = uniqueTerms.filter((term) => haystack.includes(term));
      return { ...card, score: matchedTerms.length, matchedTerms };
    })
    .filter((card) => card.score > 0)
    .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name))
    .slice(0, limit);
}

export function extractNamedLayers(code) {
  return [...code.matchAll(/^const\s+([a-zA-Z0-9_]+)\s*=/gm)].map((match) => match[1]);
}

export function summarizeRuntimeErrors(consoleErrors = []) {
  return [...new Set(consoleErrors.filter(Boolean).map((error) => `${error}`.split('\n')[0]))];
}

export function normalizeRuntimeErrors(consoleErrors = [], dependencies = {}) {
  const sampleRoleSet = new Set((dependencies.sampleRoles ?? []).map((value) => value.toLowerCase()));
  const synthVoiceSet = new Set((dependencies.synthVoices ?? []).map((value) => value.toLowerCase()));
  const grouped = new Map();

  summarizeRuntimeErrors(consoleErrors).forEach((message) => {
    const missingSound = message.match(/^Error:\s+sound\s+(.+?)\s+not found!/i)?.[1]?.toLowerCase();
    let payload;
    if (missingSound && sampleRoleSet.has(missingSound)) {
      payload = {
        key: `missing_sample_role:${missingSound}`,
        code: 'missing_sample_role',
        surface: 'sample_pack',
        message: `Sample role "${missingSound}" is not loaded in the render runtime.`,
        name: missingSound,
      };
    } else if (missingSound && synthVoiceSet.has(missingSound)) {
      payload = {
        key: `missing_synth_voice:${missingSound}`,
        code: 'missing_synth_voice',
        surface: 'synth_registry',
        message: `Synth voice "${missingSound}" is not loaded in the render runtime.`,
        name: missingSound,
      };
    } else if (
      message.includes('EncodingError: Unable to decode audio data') ||
      message.includes("InvalidAccessError: Failed to execute 'connect' on 'AudioNode'") ||
      message.includes('Failed to load resource:')
    ) {
      payload = {
        key: `render_runtime_not_ready:${message}`,
        code: 'render_runtime_not_ready',
        surface: 'render_harness',
        message,
        name: null,
      };
    } else {
      payload = {
        key: `runtime_error:${message}`,
        code: 'runtime_error',
        surface: 'strudel_runtime',
        message,
        name: null,
      };
    }

    const existing = grouped.get(payload.key);
    if (existing) {
      existing.count += 1;
      if (existing.examples.length < 3) {
        existing.examples.push(message);
      }
      return;
    }

    grouped.set(payload.key, {
      code: payload.code,
      surface: payload.surface,
      message: payload.message,
      name: payload.name,
      count: 1,
      examples: [message],
    });
  });

  return [...grouped.values()];
}
