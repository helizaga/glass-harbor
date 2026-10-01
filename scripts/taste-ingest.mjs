import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { spawn } from 'node:child_process';

import {
  examplePaths,
  parseBrief,
  parseListItems,
  readText,
  resolveSongSlug,
  validateExampleBrief,
} from '../lib/song-contract.mjs';
import { buildCalibrationProfile, buildMetricReliability, buildSignalReliability, inferExampleClipRole, parseNumericRange, round } from '../lib/analysis-helpers.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { resolvePythonExecutable } from '../lib/python-runtime.mjs';

function runPython(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(resolvePythonExecutable(), args, { stdio: 'inherit' });
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Python analysis exited with code ${code}`));
      }
    });
    child.on('error', reject);
  });
}

function parseJson(filePath, label) {
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch (error) {
    throw new CommandError(`Failed to parse ${label} at ${filePath}: ${error.message}`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'example_parse_error',
    });
  }
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function buildExampleProfile({ slug, example, analysis, clipNames }) {
  const inferredTempo = Number(analysis.rhythm?.estimated_tempo ?? 0);
  const bpmRange = parseNumericRange(example['bpm-range'] ?? example.bpm ?? '', inferredTempo) ?? {
    min: 0,
    max: 0,
    source: 'none',
  };
  const clipRoles = clipNames.map((name) => {
    const stem = basename(name, '.wav');
    return {
      clip: stem,
      role: inferExampleClipRole(stem),
    };
  });

  return {
    version: 1,
    slug,
    title: example.title ?? slug,
    tags: unique([
      ...parseListItems(example.tags),
      ...parseListItems(example['target-qualities']).map((entry) => entry.toLowerCase()),
    ]),
    bpm_range: bpmRange,
    why_you_like_it: parseListItems(example['why-you-like-it']),
    preserve_traits: parseListItems(example['target-qualities']),
    avoid_traits: parseListItems(example['anti-goals']),
    section_role_summary: clipRoles,
    section_notes: parseListItems(example['section-notes']),
    groove_notes: parseListItems(example['groove-low-end-transition-observations']),
    clip_coverage: {
      count: clipNames.length,
      clips: clipNames,
    },
    reliability: analysis.signal_reliability,
    rhythm_tendencies: {
      estimated_tempo: round(analysis.rhythm?.estimated_tempo ?? 0),
      groove_continuity: round(analysis.rhythm?.groove_continuity ?? 0),
      syncopation_proxy: round(analysis.rhythm?.syncopation_proxy ?? 0),
      inter_beat_loudness_consistency: round(analysis.rhythm?.inter_beat_loudness_consistency ?? 0),
    },
    timbre_tendencies: {
      spectral_centroid: round(analysis.timbre?.spectral_centroid ?? 0),
      sub_energy_ratio: round(analysis.timbre?.sub_energy_ratio ?? 0),
      bass_energy_ratio: round(analysis.timbre?.bass_energy_ratio ?? 0),
      high_band_energy_ratio: round(analysis.timbre?.high_band_energy_ratio ?? 0),
    },
    calibration_targets: {
      estimated_tempo: round(analysis.rhythm?.estimated_tempo ?? 0),
      groove_continuity: round(analysis.rhythm?.groove_continuity ?? 0),
      syncopation_proxy: round(analysis.rhythm?.syncopation_proxy ?? 0),
      inter_beat_loudness_consistency: round(analysis.rhythm?.inter_beat_loudness_consistency ?? 0),
      harmonic_stability: round(analysis.tonal?.harmonic_stability ?? 0),
      chord_change_proxy: round(analysis.tonal?.chord_change_proxy ?? 0),
      sub_energy_ratio: round(analysis.timbre?.sub_energy_ratio ?? 0),
      bass_energy_ratio: round(analysis.timbre?.bass_energy_ratio ?? 0),
      spectral_centroid: round(analysis.timbre?.spectral_centroid ?? 0),
    },
    example_targets: [],
  };
}

export async function handleTasteIngest({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor taste ingest <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const paths = examplePaths(slug);
  if (!existsSync(paths.markdownPath)) {
    throw new CommandError(`Missing example markdown at ${paths.markdownPath}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'example_missing',
    });
  }
  if (!existsSync(paths.clipsDir)) {
    throw new CommandError(`Missing local clips directory at ${paths.clipsDir}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'example_clips_missing',
    });
  }

  const clipNames = readdirSync(paths.clipsDir)
    .filter((name) => name.endsWith('.wav'))
    .sort((left, right) => left.localeCompare(right));
  if (clipNames.length === 0) {
    throw new CommandError(`No .wav clips found in ${paths.clipsDir}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'example_clips_empty',
    });
  }

  const example = parseBrief(readText(paths.markdownPath));
  const validation = validateExampleBrief(example);
  if (validation.errors.length > 0) {
    throw new CommandError(`Example brief validation failed for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'example_validation_failed',
      details: validation.errors,
    });
  }

  try {
    await runPython([
      'scripts/song-analyze.py',
      '--clips-dir',
      paths.clipsDir,
      '--song',
      slug,
      '--output',
      paths.analysisPath,
    ]);
  } catch (error) {
    throw new CommandError(`Taste ingest failed for ${slug}: ${error.message}`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'taste_ingest_failed',
    });
  }

  const raw = parseJson(paths.analysisPath, 'example analysis');
  const signalReliability = buildSignalReliability({
    analysis: {
      ...raw,
      metrics: raw.mix,
      confidence_notes: raw.confidence_notes ?? [],
    },
    anomalies: [],
  });
  const metricReliability = buildMetricReliability({
    analysis: {
      ...raw,
      metrics: raw.mix,
    },
    signalReliability,
  });
  const enrichedAnalysis = {
    ...raw,
    metrics: raw.mix,
    signal_reliability: signalReliability,
    metric_reliability: metricReliability,
    calibration_profile: buildCalibrationProfile({
      brief: example,
      exampleProfiles: [],
      declaredBpm: raw.rhythm?.estimated_tempo ?? 0,
    }),
  };
  const profile = buildExampleProfile({
    slug,
    example,
    analysis: enrichedAnalysis,
    clipNames,
  });

  writeFileSync(paths.analysisPath, `${JSON.stringify(enrichedAnalysis, null, 2)}\n`);
  writeFileSync(paths.profilePath, `${JSON.stringify(profile, null, 2)}\n`);

  return {
    phase: 'taste:ingest',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    example: slug,
    analysis_path: paths.analysisPath,
    profile_path: paths.profilePath,
    clip_count: clipNames.length,
    reliability: signalReliability,
    message: `Ingested taste example ${slug} from ${clipNames.length} local clip(s).`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleTasteIngest, process.argv.slice(2)));
}
