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
export const OPTIONAL_TONAL_SAMPLE_ROLES = ['bass_tonal', 'stab_tonal', 'pluck_tonal'];
export const OPTIONAL_PITCHED_SAMPLE_ROLES = ['bass_pitched', 'stab_pitched', 'pluck_pitched'];
export const ALL_ALLOWED_SAMPLE_ROLES = [
  ...STABLE_SOUND_ROLES,
  ...OPTIONAL_TONAL_SAMPLE_ROLES,
  ...OPTIONAL_PITCHED_SAMPLE_ROLES,
];
const RAW_BROWSER_SYNTH_VOICES = ['sawtooth', 'triangle', 'square'];

export const SONG_SECTION_ROLES = ['anchor', 'groove', 'lift', 'breath', 'return', 'outro'];
export const REQUIRED_SONG_METADATA = ['title', 'genre', 'bpm', 'details', 'sections', 'section-roles'];
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
export const REQUIRED_EXAMPLE_HEADINGS = [
  'title',
  'why-you-like-it',
  'target-qualities',
  'anti-goals',
  'section-notes',
  'groove-low-end-transition-observations',
];

const here = dirname(fileURLToPath(import.meta.url));
export const repoRoot = resolve(here, '..');
export const songsRoot = join(repoRoot, 'songs');
export const runsRoot = join(repoRoot, 'runs');
export const referencesRoot = join(repoRoot, 'references');
export const examplesRoot = join(repoRoot, 'examples');
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

export function examplePaths(slug) {
  const safeSlug = sanitizeSlug(slug);
  const dir = join(examplesRoot, safeSlug);
  return {
    slug: safeSlug,
    dir,
    markdownPath: join(dir, 'example.md'),
    profilePath: join(dir, 'profile.json'),
    analysisPath: join(dir, 'analysis.json'),
    clipsDir: join(dir, 'clips'),
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
    metadata[key.trim().toLowerCase().replace(/_/g, '-')] = value.trim();
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

export function parseSectionRoles(sectionRoleValue) {
  if (!sectionRoleValue) {
    return [];
  }

  return sectionRoleValue
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const match = entry.match(/^([a-z0-9-]+)\s*:\s*([a-z0-9-]+)$/i);
      if (!match) {
        throw new Error(`Invalid @section_roles entry: ${entry}`);
      }

      const name = sanitizeSlug(match[1]);
      const role = sanitizeSlug(match[2]);
      if (!SONG_SECTION_ROLES.includes(role)) {
        throw new Error(`Unknown @section_roles role "${role}" for section "${name}".`);
      }

      return { name, role };
    });
}

export function buildSectionRoleMap(sectionRoles) {
  return Object.fromEntries(sectionRoles.map((entry) => [entry.name, entry.role]));
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

function countMatches(code, pattern) {
  return [...`${code ?? ''}`.matchAll(pattern)].length;
}

function extractDependencyTokens(raw) {
  return uniqueSorted(
    [...`${raw ?? ''}`.toLowerCase().matchAll(/[a-z_][a-z0-9_-]*/g)].map(([token]) => token),
  );
}

export function extractSampleRoles(code) {
  return uniqueSorted(
    [...`${code ?? ''}`.matchAll(/(^|[^\w])s\s*\(\s*(['"`])([\s\S]*?)\2\s*\)/gm)].flatMap((match) =>
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

export function extractStrudelTechniqueProfile(code) {
  const dependencies = {
    sampleRoles: extractSampleRoles(code),
    synthVoices: extractSynthVoices(code),
  };
  const pitchedSampleRoles = dependencies.sampleRoles.filter((role) => OPTIONAL_PITCHED_SAMPLE_ROLES.includes(role));
  const tonalSampleRoles = dependencies.sampleRoles.filter((role) => OPTIONAL_TONAL_SAMPLE_ROLES.includes(role));
  const rawSynthVoices = dependencies.synthVoices.filter((voice) => RAW_BROWSER_SYNTH_VOICES.includes(voice));
  const hookRoles = dependencies.sampleRoles.filter((role) =>
    ['vocal_chop', 'pluck_tonal', 'pluck_pitched', 'stab_tonal', 'stab_pitched', 'bass_tonal', 'bass_pitched'].includes(
      role,
    ),
  );

  const counts = {
    named_layers: countMatches(code, /^\s*const\s+[a-zA-Z_$][\w$]*\s*=/gm),
    arrange: countMatches(code, /\barrange\s*\(/g),
    stack: countMatches(code, /\bstack\s*\(/g),
    note: countMatches(code, /\bnote\s*\(/g),
    chord: countMatches(code, /\bchord\s*\(/g),
    voicing: countMatches(code, /\.voicing\s*\(/g),
    layer: countMatches(code, /\.layer\s*\(/g),
    superimpose: countMatches(code, /\.superimpose\s*\(/g),
    off: countMatches(code, /\.off\s*\(/g),
    echo_with: countMatches(code, /\.echoWith\s*\(/g),
    early: countMatches(code, /\.early\s*\(/g),
    ply: countMatches(code, /\.ply\s*\(/g),
    euclid: countMatches(code, /\.euclid(?:Rot)?\s*\(/g),
    euclid_rot: countMatches(code, /\.euclidRot\s*\(/g),
    struct: countMatches(code, /\.struct\s*\(/g),
    mask: countMatches(code, /\.mask\s*\(/g),
    degrade: countMatches(code, /\.degradeBy\s*\(/g),
    sometimes: countMatches(code, /\.sometimesBy\s*\(/g),
    choose_cycles: countMatches(code, /\b(?:w?chooseCycles|randcat|wrandcat)\s*\(/g),
    first_of: countMatches(code, /\.firstOf\s*\(/g),
    last_of: countMatches(code, /\.lastOf\s*\(/g),
    chunk: countMatches(code, /\.chunk(?:Into|BackInto|Back)?\s*\(/g),
    compress: countMatches(code, /\.compressSpan\s*\(/g),
    zoom: countMatches(code, /\.zoomArc\s*\(/g),
    late: countMatches(code, /\.late\s*\(/g),
    stepcat: countMatches(code, /\bstepcat\s*\(/g),
    stepalt: countMatches(code, /\bstepalt\s*\(/g),
    swing: countMatches(code, /\.swing(?:By)?\s*\(/g),
    clip: countMatches(code, /\.clip\s*\(/g),
    end: countMatches(code, /\.end\s*\(/g),
    begin: countMatches(code, /\.begin\s*\(/g),
    slice: countMatches(code, /\.slice\s*\(/g),
    splice: countMatches(code, /\.splice\s*\(/g),
    chop: countMatches(code, /\.chop\s*\(/g),
    fit: countMatches(code, /\.fit\s*\(/g),
    seg: countMatches(code, /\.seg\s*\(/g),
    lpenv: countMatches(code, /\.lpenv\s*\(/g),
    lpf_motion: countMatches(code, /\.lpf\s*\(\s*(sine|saw|tri|square|perlin|rand|irand|segment)/g),
    delay: countMatches(code, /\.delay\s*\(/g),
    room: countMatches(code, /\.room\s*\(/g),
    reverb: countMatches(code, /\.reverb\s*\(/g),
    orbit: countMatches(code, /\.orbit\s*\(/g),
    duckorbit: countMatches(code, /\.duckorbit\s*\(/g),
    root_notes: countMatches(code, /\.rootNotes\s*\(/g),
    scale_transpose: countMatches(code, /\.scaleTranspose\s*\(/g),
    vocal_roles: countMatches(code, /const\s+[a-zA-Z_$][\w$]*\s*=\s*s\s*\(\s*(['"`])(?:[\s\S]*?)vocal_chop(?:[\s\S]*?)\1\s*\)/gm),
  };

  const techniques = {
    pitched_sample_melody: pitchedSampleRoles.length > 0,
    tonal_sample_hooks: hookRoles.length > 0,
    voiced_harmony: counts.voicing > 0 || counts.chord > 0,
    phrase_layering: counts.layer > 0 || counts.superimpose > 0 || counts.echo_with > 0,
    rhythmic_displacement: counts.off > 0 || counts.early > 0 || counts.swing > 0,
    conditional_variation: counts.mask > 0 || counts.first_of > 0 || counts.last_of > 0 || counts.chunk > 0,
    random_variation: counts.degrade > 0 || counts.sometimes > 0 || counts.choose_cycles > 0,
    groove_variation:
      counts.euclid > 0 ||
      counts.struct > 0 ||
      counts.mask > 0 ||
      counts.degrade > 0 ||
      counts.sometimes > 0 ||
      counts.choose_cycles > 0 ||
      counts.first_of > 0 ||
      counts.last_of > 0 ||
      counts.chunk > 0 ||
      counts.stepcat > 0 ||
      counts.stepalt > 0,
    time_warping: counts.swing > 0 || counts.late > 0 || counts.compress > 0 || counts.zoom > 0 || counts.euclid_rot > 0,
    sample_shaping: counts.clip > 0 || counts.end > 0 || counts.begin > 0,
    sample_slicing: counts.slice > 0 || counts.splice > 0 || counts.chop > 0 || counts.fit > 0,
    filter_motion: counts.lpenv > 0 || counts.lpf_motion > 0,
    continuous_filter_motion: counts.seg > 0 || counts.lpenv > 0,
    space_fx: counts.delay > 0 || counts.room > 0 || counts.reverb > 0,
    orbit_mix: counts.orbit > 0 || counts.duckorbit > 0,
    harmonic_support_motion: counts.root_notes > 0 || counts.scale_transpose > 0,
    vocal_variety: counts.vocal_roles >= 2,
    browser_synth_identity: rawSynthVoices.length > 0 && hookRoles.length === 0,
  };

  const strengths = [
    techniques.pitched_sample_melody ? 'pitched sample roles carry tonal material' : null,
    techniques.voiced_harmony ? 'harmony uses voicing-aware writing' : null,
    techniques.harmonic_support_motion ? 'harmony uses root or scale-aware motion helpers' : null,
    techniques.rhythmic_displacement ? 'phrases use displacement for groove' : null,
    techniques.conditional_variation ? 'phrase form changes across bars or cycles' : null,
    techniques.random_variation ? 'light randomization is shaping repeated phrases' : null,
    techniques.groove_variation ? 'groove changes are built with Strudel pattern transforms' : null,
    techniques.time_warping ? 'time modifiers are shaping swing or phrase perspective' : null,
    techniques.phrase_layering ? 'motifs are doubled or answered with phrase transforms' : null,
    techniques.sample_shaping ? 'samples are shaped with clip/end/begin' : null,
    techniques.sample_slicing ? 'sample slicing/chopping is in play' : null,
    techniques.filter_motion ? 'filter motion creates movement' : null,
    techniques.continuous_filter_motion ? 'filter motion is sampled continuously enough to read as movement' : null,
    techniques.orbit_mix ? 'orbits are separating or ducking effect spaces' : null,
    techniques.vocal_variety ? 'vocal chops serve multiple roles' : null,
  ].filter(Boolean);

  const opportunities = [
    dependencies.sampleRoles.includes('bass_tonal') &&
    !dependencies.sampleRoles.includes('bass_pitched') &&
    (counts.note > 0 || counts.chord > 0 || pitchedSampleRoles.length > 0)
      ? 'Prefer note(...).s("bass_pitched") for note-driven basslines when the runtime exposes bass_pitched.'
      : null,
    pitchedSampleRoles.length === 0 && tonalSampleRoles.length > 0
      ? 'Prefer bass_pitched, stab_pitched, or pluck_pitched when writing note-driven tonal parts.'
      : null,
    counts.note > 0 && counts.voicing === 0 && hookRoles.some((role) => role.includes('stab'))
      ? 'Use chord(...).voicing() or voiced note stacks for smoother harmonic motion.'
      : null,
    dependencies.sampleRoles.length > 0 && !techniques.sample_shaping
      ? 'Use clip(), end(), or begin() to shape sample attacks and tails.'
      : null,
    hookRoles.length > 0 && !techniques.rhythmic_displacement
      ? 'Use early() or off() on hooks to create more groove without adding layers.'
      : null,
    (dependencies.sampleRoles.includes('vocal_chop') ||
      dependencies.sampleRoles.includes('pluck_tonal') ||
      dependencies.sampleRoles.includes('pluck_pitched') ||
      dependencies.sampleRoles.includes('stab_tonal') ||
      dependencies.sampleRoles.includes('stab_pitched')) &&
    !techniques.sample_slicing
      ? 'Use slice(), splice(), or chop() when one sampled phrase should become rhythmic hook identity.'
      : null,
    (dependencies.sampleRoles.includes('hat_closed') ||
      dependencies.sampleRoles.includes('perc_top') ||
      hookRoles.length > 0) &&
    !techniques.groove_variation
      ? 'Use struct(), euclid(), stepcat(), or degradeBy()/sometimesBy() for groove variation before adding new lanes.'
      : null,
    (dependencies.sampleRoles.includes('hat_closed') ||
      dependencies.sampleRoles.includes('perc_top') ||
      hookRoles.length > 0) &&
    !techniques.time_warping
      ? 'Use swingBy(), late(), compressSpan(), or euclidRot() when the groove needs motion without extra density.'
      : null,
    hookRoles.length > 0 && !techniques.conditional_variation
      ? 'Use firstOf(), lastOf(), chunk(), or mask() so a hook changes shape across phrases instead of only by section.'
      : null,
    (dependencies.sampleRoles.includes('perc_top') || hookRoles.length > 0) && !techniques.random_variation
      ? 'Use degradeBy(), sometimesBy(), or chooseCycles() sparingly to keep repeated phrases from feeling fully static.'
      : null,
    techniques.space_fx && !techniques.orbit_mix && dependencies.sampleRoles.length >= 5
      ? 'Use orbit() or duckorbit() to separate drums, hooks, and atmosphere when effect space starts to smear.'
      : null,
    techniques.filter_motion && !techniques.continuous_filter_motion
      ? 'Use seg() or lpenv() when a filter sweep should feel continuous instead of stepping once per event.'
      : null,
    counts.chord > 0 && counts.voicing > 0 && !techniques.harmonic_support_motion
      ? 'Use rootNotes() or scaleTranspose() to connect harmonic support parts instead of hand-writing every inner motion.'
      : null,
    dependencies.sampleRoles.includes('vocal_chop') && !techniques.vocal_variety
      ? 'Split vocal_chop into at least two contrasting jobs such as bed and accent.'
      : null,
    rawSynthVoices.length > 0 && hookRoles.length === 0
      ? 'Move the song identity into sampled tonal families before leaning on raw browser synths.'
      : null,
  ].filter(Boolean);

  return {
    counts,
    techniques,
    hook_roles: hookRoles,
    pitched_sample_roles: pitchedSampleRoles,
    tonal_sample_roles: tonalSampleRoles,
    raw_synth_voices: rawSynthVoices,
    strengths,
    opportunities,
  };
}

export function validateSongCode(code) {
  const metadata = parseSongMetadata(code);
  const errors = [];
  const warnings = [];
  const dependencies = {
    sampleRoles: extractSampleRoles(code),
    synthVoices: extractSynthVoices(code),
  };
  const strudelTechniques = extractStrudelTechniqueProfile(code);
  const unknownSampleRoles = dependencies.sampleRoles.filter((role) => !ALL_ALLOWED_SAMPLE_ROLES.includes(role));
  const tonalSampleRoles = dependencies.sampleRoles.filter(
    (role) => OPTIONAL_TONAL_SAMPLE_ROLES.includes(role) || OPTIONAL_PITCHED_SAMPLE_ROLES.includes(role),
  );
  const rawBrowserSynthVoices = dependencies.synthVoices.filter((voice) => RAW_BROWSER_SYNTH_VOICES.includes(voice));
  const availableRuntimeFamilies = new Set([
    ...Object.keys(readRuntimeManifest(join(repoRoot, 'private-packs', 'runtime', 'edm-core', 'strudel.json'))),
    ...Object.keys(readRuntimeManifest(join(repoRoot, 'samples', 'edm-core', 'strudel.json'))),
  ]);

  for (const key of REQUIRED_SONG_METADATA) {
    if (!metadata[key]) {
      errors.push(`Missing @${key} metadata comment.`);
    }
  }

  let sections = [];
  let sectionRoles = [];
  try {
    sections = buildSectionTimeline(parseSections(metadata.sections));
  } catch (error) {
    errors.push(error.message);
  }

  try {
    sectionRoles = parseSectionRoles(metadata['section-roles']);
  } catch (error) {
    errors.push(error.message);
  }

  if (sections.length > 0 && sectionRoles.length > 0) {
    const sectionRoleMap = buildSectionRoleMap(sectionRoles);
    const missingRoles = sections.filter((section) => !sectionRoleMap[section.name]).map((section) => section.name);
    const unknownSections = sectionRoles
      .filter((entry) => !sections.some((section) => section.name === entry.name))
      .map((entry) => entry.name);

    if (missingRoles.length > 0) {
      errors.push(`Missing @section_roles coverage for sections: ${missingRoles.join(', ')}`);
    }
    if (unknownSections.length > 0) {
      errors.push(`@section_roles references unknown sections: ${unknownSections.join(', ')}`);
    }
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
  if (unknownSampleRoles.length > 0) {
    warnings.push(`Song file references non-standard sample roles: ${unknownSampleRoles.join(', ')}`);
  }
  if (rawBrowserSynthVoices.length > 0 && tonalSampleRoles.length === 0) {
    warnings.push(
      `Song file leans on raw browser synth voices (${rawBrowserSynthVoices.join(
        ', ',
      )}) without tonal sample roles. Prefer bass_tonal, stab_tonal, pluck_tonal, bass_pitched, stab_pitched, pluck_pitched, or vocal_chop before default synth timbres.`,
    );
  }
  if (
    dependencies.sampleRoles.includes('bass_tonal') &&
    !dependencies.sampleRoles.includes('bass_pitched') &&
    availableRuntimeFamilies.has('bass_pitched') &&
    (strudelTechniques.counts.note > 0 || strudelTechniques.counts.chord > 0 || strudelTechniques.pitched_sample_roles.length > 0)
  ) {
    warnings.push('Runtime pack exposes bass_pitched. Prefer note(...).s("bass_pitched") for note-driven basslines before falling back to bass_tonal.');
  }
  if (strudelTechniques.opportunities.length > 0) {
    warnings.push(...strudelTechniques.opportunities);
  }

  return {
    metadata,
    sections,
    sectionRoles,
    sectionRoleMap: buildSectionRoleMap(sectionRoles),
    dependencies,
    strudelTechniques,
    errors,
    warnings,
  };
}

function readRuntimeManifest(filePath) {
  if (!existsSync(filePath)) {
    return {};
  }
  try {
    return JSON.parse(readText(filePath));
  } catch {
    return {};
  }
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

export function validateExampleBrief(example) {
  const errors = [];
  for (const heading of REQUIRED_EXAMPLE_HEADINGS) {
    if (!example[heading] || !`${example[heading]}`.trim()) {
      errors.push(`Missing example heading content for "${heading}".`);
    }
  }

  return { errors };
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
      let metadata = {};
      if (existsSync(metadataPath)) {
        try {
          metadata = JSON.parse(readText(metadataPath));
        } catch (error) {
          console.warn(`Failed to parse reference metadata at ${metadataPath}: ${error.message}`);
        }
      }
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

function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

export function parseListItems(value) {
  if (!value) {
    return [];
  }

  return `${value}`
    .split(/\r?\n|,/)
    .map((entry) => entry.replace(/^\s*[-*]\s*/, '').trim())
    .filter(Boolean);
}

export function parseExampleTargets(brief) {
  return [...new Set(parseListItems(brief['example-targets']).map((entry) => sanitizeSlug(entry)).filter(Boolean))];
}

function splitPromptTraits(value) {
  return `${value ?? ''}`
    .split(/\r?\n|,|;/)
    .map((entry) => entry.replace(/^(borrow|avoid copying|avoid|keep|prefer):\s*/i, '').trim())
    .filter(Boolean);
}

const PROMPT_REFERENCE_PRESETS = [
  {
    terms: ['odesza', 'a moment apart', 'late night'],
    inferredLanes: ['cinematic electronica', 'organic percussion', 'vocal chop uplift'],
    retrievalTerms: [
      'cinematic',
      'organic percussion',
      'vocal chop',
      'warm',
      'nostalgic',
      'uplift',
      'wide return',
      'human',
      'festival electronic',
    ],
    preserveTraits: [
      'organic percussion motion',
      'vocal-fragment hook energy',
      'warm low mids',
      'patient cinematic uplift',
    ],
    avoidTraits: ['brittle top end', 'generic house hats', 'flat return payoff'],
    bpmPreference: { center: 104, deadband: 7 },
    targetBiases: {
      percussion_focus: 0.95,
      vocal_focus: 0.9,
      cinematic_focus: 0.95,
      warmth_focus: 0.88,
      return_focus: 0.9,
    },
    metricTargets: {
      groove_continuity: 0.75,
      inter_beat_loudness_consistency: 0.56,
      harmonic_stability: 0.9,
      chord_change_proxy: 0.46,
      sub_energy_ratio: 0.14,
      bass_energy_ratio: 0.22,
      spectral_centroid: 1950,
    },
  },
];

const PROMPT_REFERENCE_KEYWORD_RULES = [
  {
    terms: ['cinematic', 'widescreen', 'orchestral', 'airborne'],
    retrievalTerms: ['cinematic', 'wide', 'shimmer', 'air', 'emotional'],
    targetBiases: { cinematic_focus: 0.18, return_focus: 0.08 },
    metricTargets: { harmonic_stability: 0.88, spectral_centroid: 1900 },
  },
  {
    terms: ['percussion', 'organic', 'drumline', 'marching', 'drums'],
    retrievalTerms: ['percussion', 'organic', 'groove', 'drum motion'],
    targetBiases: { percussion_focus: 0.2 },
    metricTargets: { groove_continuity: 0.74, inter_beat_loudness_consistency: 0.54 },
  },
  {
    terms: ['vocal', 'chop', 'falsetto', 'human'],
    retrievalTerms: ['vocal', 'chop', 'hook', 'human'],
    targetBiases: { vocal_focus: 0.2 },
    metricTargets: { spectral_centroid: 2050 },
  },
  {
    terms: ['warm', 'nostalgic', 'glow'],
    retrievalTerms: ['warm', 'nostalgic', 'glow'],
    targetBiases: { warmth_focus: 0.2 },
    metricTargets: { sub_energy_ratio: 0.15, bass_energy_ratio: 0.22, spectral_centroid: 1850 },
  },
  {
    terms: ['return', 'payoff', 'bloom', 'uplift'],
    retrievalTerms: ['return', 'bloom', 'lift', 'impact'],
    targetBiases: { return_focus: 0.2 },
    metricTargets: {},
  },
];

export const STYLE_LANE_PRESETS = [
  {
    key: 'atmospheric-deep-house',
    label: 'Atmospheric Deep House',
    aliases: ['deep house', 'atmospheric deep house', 'late-night deep house', 'melodic deep house'],
    bpmRange: { min: 118, max: 124 },
    arrangementArchetypes: ['patient bloom', 'subtractive breakdown', 'strong return'],
    preferredRoles: ['bass_pitched', 'stab_pitched', 'pluck_pitched', 'air_texture'],
    optionalRoles: ['vocal_chop', 'shimmer_fx'],
    primaryHookRoles: ['pluck_pitched', 'stab_pitched'],
    discourageRoles: ['impact_wide'],
    dominantRoles: ['pluck_pitched', 'bass_pitched'],
    supportRoles: ['stab_pitched', 'air_texture'],
    pruneFirstRoles: ['impact_wide', 'riser_up', 'hat_open'],
    maxHookRoles: 2,
    preferredTechniques: ['voicing', 'rootNotes', 'seg', 'swingBy', 'orbit'],
    avoidTechniques: ['too many vocal slices', 'over-dense perc clutter'],
    antiPatterns: ['festival supersaw lead', 'constant top-end brightness', 'all parts on at once'],
    candidateProfiles: [
      {
        id: 'pocket_forward',
        label: 'pocket-forward',
        guidance: 'Prefer a calmer low end, steadier groove, and more restraint in the harmonic bed.',
      },
      {
        id: 'lift_forward',
        label: 'lift-forward',
        guidance: 'Prefer clearer pluck motion, brighter section contrast, and a more emotional return.',
      },
    ],
  },
  {
    key: 'uk-garage-pop',
    label: 'UK Garage Pop',
    aliases: ['uk garage', 'garage-pop', '2-step', 'two-step', 'speed garage', 'club crossover'],
    bpmRange: { min: 126, max: 136 },
    arrangementArchetypes: ['percussion reveal', 'strong return'],
    preferredRoles: ['vocal_chop', 'bass_pitched', 'pluck_pitched', 'hat_closed'],
    optionalRoles: ['perc_top', 'stab_pitched'],
    primaryHookRoles: ['vocal_chop', 'pluck_pitched'],
    discourageRoles: ['air_texture', 'shimmer_fx'],
    dominantRoles: ['vocal_chop', 'bass_pitched'],
    supportRoles: ['pluck_pitched', 'hat_closed'],
    pruneFirstRoles: ['air_texture', 'shimmer_fx', 'impact_wide'],
    maxHookRoles: 2,
    preferredTechniques: ['swingBy', 'late', 'chooseCycles', 'slice', 'lastOf', 'off'],
    avoidTechniques: ['long washed pads', 'straight four-on-the-floor hats'],
    antiPatterns: ['deep-house wash', 'continuous sub sustain', 'too many simultaneous hooks'],
    candidateProfiles: [
      {
        id: 'vocal_forward',
        label: 'vocal-forward',
        guidance: 'Let the chopped vocal be the main identity and keep the bass answering it.',
      },
      {
        id: 'bass_forward',
        label: 'bass-forward',
        guidance: 'Let the low-end hook carry the groove and keep the vocal more punctuational.',
      },
    ],
  },
  {
    key: 'french-house',
    label: 'French House',
    aliases: ['french house', 'filter house', 'disco house'],
    bpmRange: { min: 120, max: 128 },
    arrangementArchetypes: ['filter-house loop climb', 'strong return'],
    preferredRoles: ['stab_pitched', 'bass_pitched', 'vocal_chop'],
    optionalRoles: ['shimmer_fx', 'impact_wide'],
    primaryHookRoles: ['stab_pitched', 'vocal_chop'],
    discourageRoles: ['air_texture', 'hat_open'],
    dominantRoles: ['stab_pitched', 'bass_pitched'],
    supportRoles: ['vocal_chop', 'clap_main'],
    pruneFirstRoles: ['air_texture', 'hat_open', 'shimmer_fx'],
    maxHookRoles: 2,
    preferredTechniques: ['clip', 'end', 'filter motion', 'struct', 'chunk'],
    avoidTechniques: ['too much harmonic drift', 'overwritten melodies'],
    antiPatterns: ['melodic-house pad bloom', 'muddy bass sustain', 'generic EDM riser dependency'],
    candidateProfiles: [
      {
        id: 'loop_forward',
        label: 'loop-forward',
        guidance: 'Keep the harmonic loop tighter and let timbral change do the work.',
      },
      {
        id: 'hook_forward',
        label: 'hook-forward',
        guidance: 'Use a more obvious disco-adjacent hook fragment without increasing harmonic churn.',
      },
    ],
  },
  {
    key: 'moombahton-club',
    label: 'Moombahton Club',
    aliases: ['moombahton', 'latin club', 'reggaeton club', 'dj snake lane'],
    bpmRange: { min: 96, max: 110 },
    arrangementArchetypes: ['percussion reveal', 'subtractive breakdown', 'strong return'],
    preferredRoles: ['vocal_chop', 'bass_pitched', 'perc_top', 'impact_wide'],
    optionalRoles: ['stab_pitched', 'riser_up'],
    primaryHookRoles: ['vocal_chop', 'bass_pitched'],
    discourageRoles: ['air_texture', 'shimmer_fx'],
    dominantRoles: ['vocal_chop', 'perc_top'],
    supportRoles: ['bass_pitched', 'impact_wide'],
    pruneFirstRoles: ['air_texture', 'shimmer_fx', 'hat_open'],
    maxHookRoles: 2,
    preferredTechniques: ['struct', 'degradeBy', 'chooseCycles', 'slice', 'orbit'],
    avoidTechniques: ['busy harmonic beds', 'airy house pads'],
    antiPatterns: ['soft deep-house groove', 'constant melodic top-line', 'stacked ambient layers'],
    candidateProfiles: [
      {
        id: 'drum_forward',
        label: 'drum-forward',
        guidance: 'Lead with chest-forward percussion and a simpler vocal punctuation pattern.',
      },
      {
        id: 'hook_forward',
        label: 'hook-forward',
        guidance: 'Keep the drums sparse and let the vocal fragment or stab become the main attitude hook.',
      },
    ],
  },
  {
    key: 'downtempo-pop',
    label: 'Downtempo Pop',
    aliases: ['downtempo', 'pinkpantheress-adjacent', 'bedroom club', 'soft club pop'],
    bpmRange: { min: 96, max: 116 },
    arrangementArchetypes: ['patient bloom', 'percussion reveal'],
    preferredRoles: ['vocal_chop', 'pluck_pitched', 'bass_pitched', 'air_texture'],
    optionalRoles: ['stab_pitched', 'shimmer_fx'],
    primaryHookRoles: ['vocal_chop', 'pluck_pitched'],
    discourageRoles: ['impact_wide'],
    dominantRoles: ['vocal_chop', 'pluck_pitched'],
    supportRoles: ['bass_pitched', 'air_texture'],
    pruneFirstRoles: ['impact_wide', 'riser_up', 'hat_open'],
    maxHookRoles: 2,
    preferredTechniques: ['slice', 'clip', 'early', 'chooseCycles', 'seg'],
    avoidTechniques: ['big-room impact stacking', 'heavy supersaw feel'],
    antiPatterns: ['loud default synths', 'overbuilt breakdowns', 'too much sub weight'],
    candidateProfiles: [
      {
        id: 'intimate_forward',
        label: 'intimate-forward',
        guidance: 'Keep the vocal fragment very close and let the groove stay light and bouncy.',
      },
      {
        id: 'club_forward',
        label: 'club-forward',
        guidance: 'Push the bass and clap harder while keeping the topline fragment small and sticky.',
      },
    ],
  },
];

function normalizeLaneName(value) {
  return sanitizeSlug(`${value ?? ''}`.replace(/adjacent/g, '').replace(/style/g, '').trim());
}

function mergeUnique(...groups) {
  return [...new Set(groups.flat().filter(Boolean))];
}

function matchStylePreset(text) {
  const haystack = normalizeLaneName(text);
  if (!haystack) {
    return null;
  }

  let bestPreset = null;
  let bestScore = 0;
  for (const preset of STYLE_LANE_PRESETS) {
    const terms = [preset.key, ...(preset.aliases ?? [])].map(normalizeLaneName);
    const score = terms.reduce((sum, term) => {
      if (!term) {
        return sum;
      }
      if (haystack.includes(term)) {
        return sum + Math.max(3, term.split('-').length);
      }
      const parts = term.split('-').filter(Boolean);
      const partials = parts.filter((part) => haystack.includes(part)).length;
      return sum + partials;
    }, 0);
    if (score > bestScore) {
      bestPreset = preset;
      bestScore = score;
    }
  }

  return bestScore > 0 ? bestPreset : null;
}

export function resolveStyleProfile(brief = {}, { tasteProfile = null, styleLens = null, exampleProfiles = [] } = {}) {
  const explicitLane = `${brief['style-lane'] ?? ''}`.trim();
  const explicitAccent = `${brief.accent ?? ''}`.trim();
  const memoryPreferredLanes = tasteProfile?.preferred_lanes ?? [];
  const memoryCurrentLane = tasteProfile?.current_lane ?? '';
  const sourceText = [
    explicitLane,
    memoryCurrentLane,
    ...memoryPreferredLanes,
    brief.genre,
    brief.mood,
    brief['sonic-goals'],
    brief['notes-for-agent'],
    ...(styleLens?.inferredLanes ?? []),
    ...exampleProfiles.flatMap((entry) => entry?.profile?.tags ?? []),
  ]
    .filter(Boolean)
    .join(' ');

  const preset = matchStylePreset(sourceText);
  if (!preset && !explicitLane && !memoryCurrentLane && memoryPreferredLanes.length === 0) {
    return null;
  }

  const laneLabel = explicitLane || preset?.label || memoryCurrentLane || memoryPreferredLanes[0] || `${brief.genre ?? ''}`.trim();
  return {
    key: preset?.key ?? normalizeLaneName(laneLabel),
    label: laneLabel || preset?.label || 'Custom Lane',
    accent: explicitAccent || tasteProfile?.current_accent || null,
    source:
      explicitLane
        ? 'brief-style-lane'
        : preset
          ? 'inferred-from-brief'
          : memoryCurrentLane || memoryPreferredLanes.length > 0
            ? 'taste-memory'
            : 'brief-genre',
    bpm_range: preset?.bpmRange ?? null,
    arrangement_archetypes: preset?.arrangementArchetypes ?? [],
    preferred_roles: mergeUnique(preset?.preferredRoles ?? []),
    optional_roles: mergeUnique(preset?.optionalRoles ?? []),
    primary_hook_roles: mergeUnique(preset?.primaryHookRoles ?? []),
    discourage_roles: mergeUnique(preset?.discourageRoles ?? []),
    dominant_roles: mergeUnique(preset?.dominantRoles ?? [], preset?.primaryHookRoles?.slice(0, 1) ?? []),
    support_roles: mergeUnique(preset?.supportRoles ?? [], preset?.optionalRoles ?? []),
    prune_first_roles: mergeUnique(preset?.pruneFirstRoles ?? [], preset?.discourageRoles ?? []),
    max_hook_roles: Math.max(1, Number(preset?.maxHookRoles ?? 2)),
    preferred_techniques: mergeUnique(preset?.preferredTechniques ?? []),
    avoid_techniques: mergeUnique(preset?.avoidTechniques ?? [], tasteProfile?.avoid_techniques ?? []),
    anti_patterns: mergeUnique(preset?.antiPatterns ?? [], tasteProfile?.avoid_traits ?? []),
    candidate_profiles: preset?.candidateProfiles ?? [],
    memory_preferred_lanes: memoryPreferredLanes,
    memory_avoid_lanes: tasteProfile?.avoid_lanes ?? [],
  };
}

export function evaluateStyleProfileUsage({ dependencies = {}, strudelTechniques = null, styleProfile = null }) {
  if (!styleProfile) {
    return null;
  }

  const usedRoles = dependencies.sampleRoles ?? [];
  const hookRoles = strudelTechniques?.hook_roles ?? [];
  const preferredRoleHits = usedRoles.filter((role) => styleProfile.preferred_roles?.includes(role));
  const primaryHookHits = hookRoles.filter((role) => styleProfile.primary_hook_roles?.includes(role));
  const discouragedRoleHits = usedRoles.filter((role) => styleProfile.discourage_roles?.includes(role));
  const hookRoleCount = hookRoles.length;
  const hookSpread = hookRoleCount <= 2 ? 'focused' : hookRoleCount <= 3 ? 'busy' : 'diffuse';

  const warnings = [
    primaryHookHits.length === 0 && (styleProfile.primary_hook_roles?.length ?? 0) > 0
      ? `Style lane "${styleProfile.label}" usually wants the hook to come from ${styleProfile.primary_hook_roles.join(', ')}, but none of those roles carry the current hook.`
      : null,
    hookRoleCount > 3
      ? `Hook identity is spread across ${hookRoleCount} roles. Prefer one primary hook and one answer before adding more carriers.`
      : null,
    discouragedRoleHits.length > 0
      ? `Roles ${discouragedRoleHits.join(', ')} tend to pull "${styleProfile.label}" toward the wrong accent here.`
      : null,
    preferredRoleHits.length === 0 && (styleProfile.preferred_roles?.length ?? 0) > 0
      ? `The song is not using the core role subset that usually defines "${styleProfile.label}".`
      : null,
  ].filter(Boolean);

  const score = round(
    clamp(
      (preferredRoleHits.length > 0 ? preferredRoleHits.length / Math.max(1, styleProfile.preferred_roles.length) : 0) * 0.45 +
        (primaryHookHits.length > 0 ? 0.3 : 0) +
        (hookSpread === 'focused' ? 0.15 : hookSpread === 'busy' ? 0.08 : 0) +
        (discouragedRoleHits.length === 0 ? 0.1 : 0),
    ),
  );

  return {
    lane: styleProfile.label,
    preferred_role_hits: preferredRoleHits,
    primary_hook_hits: primaryHookHits,
    discouraged_role_hits: discouragedRoleHits,
    hook_role_count: hookRoleCount,
    hook_spread: hookSpread,
    score,
    warnings,
  };
}

export function buildStyleRolePlan({ styleProfile = null, dependencies = {}, strudelTechniques = null } = {}) {
  if (!styleProfile) {
    return null;
  }

  const usedRoles = dependencies.sampleRoles ?? [];
  const hookRoles = strudelTechniques?.hook_roles ?? [];
  const maxHookRoles = Math.max(1, Number(styleProfile.max_hook_roles ?? 2));
  const dominantRoles =
    styleProfile.dominant_roles?.length > 0
      ? styleProfile.dominant_roles
      : mergeUnique(styleProfile.primary_hook_roles?.slice(0, 1) ?? [], styleProfile.preferred_roles?.slice(0, 1) ?? []);
  const supportRoles = mergeUnique(styleProfile.support_roles ?? [], styleProfile.optional_roles ?? []);
  const pruneFirstRoles = mergeUnique(styleProfile.prune_first_roles ?? [], styleProfile.discourage_roles ?? []);
  const protectedHookRoles = mergeUnique(styleProfile.primary_hook_roles ?? [], dominantRoles);

  const missingDominantRoles = dominantRoles.filter((role) => !usedRoles.includes(role));
  const activeDiscouragedRoles = usedRoles.filter((role) => pruneFirstRoles.includes(role));
  const hookRolesToDemote = hookRoles.filter((role) => !protectedHookRoles.includes(role));
  const excessHookRoleCount = Math.max(0, hookRoles.length - maxHookRoles);
  const suggestedPrunedRoles = mergeUnique(
    activeDiscouragedRoles,
    hookRolesToDemote.slice(0, excessHookRoleCount),
  );

  const warnings = [
    missingDominantRoles.length > 0
      ? `Lane "${styleProfile.label}" wants the song to lean on ${missingDominantRoles.join(', ')} more clearly.`
      : null,
    suggestedPrunedRoles.length > 0
      ? `Prune or demote ${suggestedPrunedRoles.join(', ')} first if the arrangement still feels lane-confused.`
      : null,
    hookRoles.length > maxHookRoles
      ? `Limit hook-carrying roles to ${maxHookRoles}; current hook spread is ${hookRoles.length}.`
      : null,
  ].filter(Boolean);

  return {
    lane: styleProfile.label,
    accent: styleProfile.accent ?? null,
    dominant_roles: dominantRoles,
    support_roles: supportRoles,
    optional_roles: styleProfile.optional_roles ?? [],
    primary_hook_roles: styleProfile.primary_hook_roles ?? [],
    discourage_roles: styleProfile.discourage_roles ?? [],
    prune_first_roles: pruneFirstRoles,
    max_hook_roles: maxHookRoles,
    used_roles: usedRoles,
    missing_dominant_roles: missingDominantRoles,
    active_discouraged_roles: activeDiscouragedRoles,
    suggested_pruned_roles: suggestedPrunedRoles,
    guidance: [
      dominantRoles.length > 0
        ? `Build the identity around ${dominantRoles.join(', ')} before reaching for extra accent roles.`
        : null,
      supportRoles.length > 0
        ? `Use ${supportRoles.join(', ')} as support or answer roles, not as competing co-leads.`
        : null,
      pruneFirstRoles.length > 0
        ? `If the lane starts collapsing, remove or demote ${pruneFirstRoles.join(', ')} first.`
        : null,
    ].filter(Boolean),
    warnings,
  };
}

export function parsePromptReferences(brief) {
  const raw = `${brief['prompt-references'] ?? ''}`.trim();
  if (!raw || /^(?:[-*]\s*)?none\.?$/i.test(raw)) {
    return [];
  }

  const references = [];
  let current = null;

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    const songMatch = trimmed.match(/^[-*]\s*song or artist:\s*(.+)$/i);
    if (songMatch) {
      if (current) {
        references.push(current);
      }
      current = {
        label: songMatch[1].trim(),
        borrow: '',
        avoidCopying: '',
      };
      continue;
    }

    if (!current) {
      current = {
        label: trimmed.replace(/^[-*]\s*/, ''),
        borrow: '',
        avoidCopying: '',
      };
      continue;
    }

    const borrowMatch = trimmed.match(/^borrow:\s*(.+)$/i);
    if (borrowMatch) {
      current.borrow = borrowMatch[1].trim();
      continue;
    }

    const avoidMatch = trimmed.match(/^avoid copying:\s*(.+)$/i);
    if (avoidMatch) {
      current.avoidCopying = avoidMatch[1].trim();
      continue;
    }

    current.borrow = [current.borrow, trimmed].filter(Boolean).join(' ');
  }

  if (current) {
    references.push(current);
  }

  return references.filter((entry) => entry.label);
}

export function buildPromptStyleLens(brief) {
  const references = parsePromptReferences(brief);
  if (references.length === 0) {
    return null;
  }

  const sourceText = references.map((entry) => `${entry.label} ${entry.borrow} ${entry.avoidCopying}`).join(' ').toLowerCase();
  const lens = {
    source: 'prompt-references',
    references,
    terms: tokenize(sourceText),
    retrievalTerms: [],
    preserveTraits: [...new Set(references.flatMap((entry) => splitPromptTraits(entry.borrow)))],
    avoidTraits: [...new Set(references.flatMap((entry) => splitPromptTraits(entry.avoidCopying)))],
    inferredLanes: [],
    bpmPreference: null,
    targetBiases: {
      percussion_focus: 0,
      vocal_focus: 0,
      cinematic_focus: 0,
      warmth_focus: 0,
      return_focus: 0,
    },
    metricTargets: {},
  };

  for (const preset of PROMPT_REFERENCE_PRESETS) {
    const matched = preset.terms.some((term) => sourceText.includes(term.toLowerCase()));
    if (!matched) {
      continue;
    }

    lens.retrievalTerms.push(...preset.retrievalTerms);
    lens.inferredLanes.push(...preset.inferredLanes);
    lens.preserveTraits.push(...preset.preserveTraits);
    lens.avoidTraits.push(...preset.avoidTraits);
    if (!lens.bpmPreference && preset.bpmPreference) {
      lens.bpmPreference = preset.bpmPreference;
    }
    Object.entries(preset.targetBiases ?? {}).forEach(([key, value]) => {
      lens.targetBiases[key] = Math.max(lens.targetBiases[key] ?? 0, Number(value ?? 0));
    });
    Object.entries(preset.metricTargets ?? {}).forEach(([key, value]) => {
      if (lens.metricTargets[key] === undefined) {
        lens.metricTargets[key] = Number(value);
      }
    });
  }

  for (const rule of PROMPT_REFERENCE_KEYWORD_RULES) {
    const matched = rule.terms.some((term) => sourceText.includes(term));
    if (!matched) {
      continue;
    }

    lens.retrievalTerms.push(...(rule.retrievalTerms ?? []));
    Object.entries(rule.targetBiases ?? {}).forEach(([key, value]) => {
      lens.targetBiases[key] = round((lens.targetBiases[key] ?? 0) + Number(value ?? 0));
    });
    Object.entries(rule.metricTargets ?? {}).forEach(([key, value]) => {
      if (lens.metricTargets[key] === undefined) {
        lens.metricTargets[key] = Number(value);
      } else {
        lens.metricTargets[key] = round((Number(lens.metricTargets[key]) + Number(value)) / 2);
      }
    });
  }

  lens.retrievalTerms = [...new Set([...lens.terms, ...tokenize(lens.retrievalTerms.join(' '))])];
  lens.preserveTraits = [...new Set(lens.preserveTraits)];
  lens.avoidTraits = [...new Set(lens.avoidTraits)];
  lens.inferredLanes = [...new Set(lens.inferredLanes)];

  return lens;
}

function readJsonIfPresent(filePath, fallback = null) {
  if (!existsSync(filePath)) {
    return fallback;
  }

  try {
    return JSON.parse(readText(filePath));
  } catch (error) {
    console.warn(`Failed to parse JSON at ${filePath}: ${error.message}`);
    return fallback;
  }
}

export function loadExampleProfile(slug) {
  const paths = examplePaths(slug);
  if (!existsSync(paths.profilePath)) {
    return null;
  }

  return {
    slug: paths.slug,
    paths,
    profile: readJsonIfPresent(paths.profilePath, null),
    markdown: existsSync(paths.markdownPath) ? readText(paths.markdownPath) : '',
  };
}

export function selectExampleProfiles(brief) {
  return parseExampleTargets(brief)
    .map((slug) => loadExampleProfile(slug))
    .filter((entry) => entry?.profile);
}

function exampleProfileTerms(exampleProfiles = []) {
  return exampleProfiles.flatMap((entry) => {
    const profile = entry?.profile ?? {};
    return [
      profile.title,
      ...(profile.tags ?? []),
      ...(profile.preserve_traits ?? []),
      ...(profile.avoid_traits ?? []),
      ...(profile.section_role_summary ?? []),
      ...(profile.rhythm_tendencies ?? []),
      ...(profile.timbre_tendencies ?? []),
    ];
  });
}

export function deriveGenerationStrategy(brief, { exampleProfiles = [], styleLens = null, styleProfile = null } = {}) {
  const promptStyleLens = styleLens ?? buildPromptStyleLens(brief);
  const resolvedStyleProfile = styleProfile ?? resolveStyleProfile(brief, { styleLens: promptStyleLens, exampleProfiles });
  const promptReferences = parsePromptReferences(brief);
  const vibeText = [
    brief.genre,
    brief.mood,
    brief['notes-for-agent'],
    brief['sonic-goals'],
    brief['prompt-references'],
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  const ambiguousVibe =
    /\b(like|in the lane of|adjacent|inspired by|cinematic|emotional|anthemic|widescreen|organic|dreamy|nostalgic|festival|uplift)\b/i.test(
      vibeText,
    );
  const styleHeavy =
    promptReferences.length > 0 ||
    exampleProfiles.length > 0 ||
    Boolean(resolvedStyleProfile?.key) ||
    (promptStyleLens?.inferredLanes?.length ?? 0) > 0 ||
    ambiguousVibe;

  return {
    mode: styleHeavy ? 'two_candidate_hidden' : 'single_draft',
    example_first: exampleProfiles.length > 0,
    style_heavy: styleHeavy,
    role_plan: buildStyleRolePlan({ styleProfile: resolvedStyleProfile }),
    reason:
      exampleProfiles.length > 0
        ? 'Attached example targets make this a taste-calibrated prompt; branch two drafts and keep the better one.'
        : resolvedStyleProfile?.key
          ? `The brief resolves to the ${resolvedStyleProfile.label} lane, so branch two drafts and keep the better one.`
        : promptReferences.length > 0
          ? 'Prompt references indicate a style-heavy request; branch two drafts and keep the better one.'
          : ambiguousVibe
            ? 'The prompt is vibe-heavy enough that a hidden two-draft comparison is safer than a single shot.'
            : 'The prompt is concrete enough for a single draft.',
    candidate_profiles:
      styleHeavy
        ? resolvedStyleProfile?.candidate_profiles?.length > 0
          ? resolvedStyleProfile.candidate_profiles
          : [
              {
                id: 'rhythm_forward',
                label: 'rhythm/percussion-forward',
                guidance: 'Prefer clearer percussion motion, firmer pocket, and more subtractive arrangement contrast.',
              },
              {
                id: 'melody_forward',
                label: 'harmony/melody-forward',
                guidance: 'Prefer a stronger hook, warmer harmony, and a more lyrical top-line identity.',
              },
            ]
        : [],
  };
}

export function selectReferenceCards(brief, limit = 3, { styleLens = null, exampleProfiles = [] } = {}) {
  const promptStyleLens = styleLens ?? buildPromptStyleLens(brief);
  const corpusTerms = tokenize(
    [
      brief.title,
      brief.genre,
      brief.mood,
      brief.structure,
      brief['prompt-references'],
      brief['sonic-goals'],
      brief['review-goals'],
      brief['notes-for-agent'],
      ...exampleProfileTerms(exampleProfiles),
      ...(promptStyleLens?.retrievalTerms ?? []),
      ...(promptStyleLens?.inferredLanes ?? []),
      ...(promptStyleLens?.preserveTraits ?? []),
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
