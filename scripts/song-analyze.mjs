import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

import {
  normalizeRuntimeErrors,
  parseBrief,
  readText,
  resolveRunDir,
  resolveSongSlug,
  selectReferenceCards,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { resolvePythonExecutable } from '../lib/python-runtime.mjs';
import { computeEmbeddingAlignment } from './song-embedding-provider.mjs';

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

function parseJsonFile(filePath, { exitCode, code, label }) {
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch (error) {
    throw new CommandError(`Failed to parse ${label} at ${filePath}: ${error.message}`, {
      exitCode,
      code,
    });
  }
}

function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function computeSectionTransitions(sectionNames, sections = {}) {
  const transitions = [];
  for (let index = 0; index < sectionNames.length - 1; index += 1) {
    const from = sectionNames[index];
    const to = sectionNames[index + 1];
    const left = sections[from];
    const right = sections[to];
    if (!left || !right) {
      continue;
    }

    transitions.push({
      from,
      to,
      loudness_delta: round((right.rms ?? 0) - (left.rms ?? 0)),
      onset_delta: round((right.onset_density ?? 0) - (left.onset_density ?? 0)),
      brightness_delta: round(
        ((right.timbre?.spectral_centroid ?? 0) - (left.timbre?.spectral_centroid ?? 0)) / 4000,
      ),
      low_end_delta: round(
        ((right.timbre?.sub_energy_ratio ?? 0) + (right.timbre?.bass_energy_ratio ?? 0)) -
          ((left.timbre?.sub_energy_ratio ?? 0) + (left.timbre?.bass_energy_ratio ?? 0)),
      ),
      boundary_strength: round(
        clamp(
          Math.abs((right.rms ?? 0) - (left.rms ?? 0)) * 5 +
            Math.abs((right.onset_density ?? 0) - (left.onset_density ?? 0)) / 3 +
            Math.abs((right.timbre?.spectral_centroid ?? 0) - (left.timbre?.spectral_centroid ?? 0)) / 6000,
        ),
      ),
    });
  }
  return transitions;
}

export async function handleSongAnalyze({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song analyze <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const runDir = resolveRunDir(argv, slug) ?? '';
  const runPath = runDir ? join(runDir, 'run.json') : '';

  if (!runDir || !existsSync(runPath)) {
    throw new CommandError(`No rendered run found for ${slug}. Run glass-harbor song render ${slug} first.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'run_missing',
    });
  }

  const runInfo = parseJsonFile(runPath, {
    exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
    code: 'run_parse_error',
    label: 'run.json',
  });
  if (runInfo.status === 'blocked') {
    const outputPath = join(runDir, 'analysis.json');
    const blockedPayload = {
      phase: 'analyze',
      status: 'blocked',
      song: slug,
      run_dir: runDir,
      readiness: 'blocked',
      metrics: null,
      sections: {},
      anomalies: ['Render phase is blocked; analysis was skipped.'],
      runtime_blockers: runInfo.runtime_blockers ?? [],
    };
    writeFileSync(outputPath, `${JSON.stringify(blockedPayload, null, 2)}\n`);
    return {
      phase: 'song:analyze',
      status: 'blocked',
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      song: slug,
      run_dir: runDir,
      baseline_run_dir: null,
      readiness: 'blocked',
      anomalies: blockedPayload.anomalies,
      runtime_blockers: blockedPayload.runtime_blockers,
      recommended_next_action: 'revise',
      approval_required: false,
      message: `Analysis skipped for ${slug} because the render phase is blocked.`,
    };
  }

  if (!existsSync(join(runDir, 'mix.wav'))) {
    throw new CommandError(`Rendered run for ${slug} is missing mix.wav.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'mix_missing',
    });
  }

  const song = songPaths(slug);
  const code = readText(song.songPath);
  const brief = parseBrief(readText(song.briefPath));
  const validation = validateSongCode(code);
  const outputPath = join(runDir, 'analysis.json');

  try {
    await runPython([
      'scripts/song-analyze.py',
      '--run-dir',
      runDir,
      '--song',
      slug,
      '--bpm',
      validation.metadata.bpm ?? '0',
      '--output',
      outputPath,
    ]);
  } catch (error) {
    const blockedPayload = {
      phase: 'analyze',
      status: 'blocked',
      song: slug,
      run_dir: runDir,
      readiness: 'blocked',
      metrics: null,
      sections: {},
      anomalies: [`Audio analysis failed for ${slug}.`],
      runtime_blockers: [{ code: 'analysis_failed', message: error.message }],
    };
    writeFileSync(outputPath, `${JSON.stringify(blockedPayload, null, 2)}\n`);
    throw new CommandError(`Analysis failed for ${slug}: ${error.message}`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'analysis_failed',
    });
  }

  const raw = parseJsonFile(outputPath, {
    exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
    code: 'analysis_parse_error',
    label: 'analysis output',
  });
  const anomalies = [];
  if ((raw.mix?.rms ?? 0) === 0 && (raw.mix?.peak ?? 0) === 0) {
    anomalies.push('Rendered mix is silent.');
  }
  const silentSections = Object.entries(raw.sections ?? {})
    .filter(([, metrics]) => (metrics.rms ?? 0) === 0 && (metrics.peak ?? 0) === 0)
    .map(([name]) => name);
  if (silentSections.length > 0) {
    anomalies.push(`Silent sections: ${silentSections.join(', ')}`);
  }
  const runtimeBlockers =
    runInfo.runtime_blockers?.length > 0
      ? runInfo.runtime_blockers
      : normalizeRuntimeErrors(runInfo.console_errors, runInfo.dependencies ?? validation.dependencies);
  if (runtimeBlockers.length > 0) {
    anomalies.push('Render phase reported runtime blockers.');
  }

  const readiness =
    runtimeBlockers.length > 0 ? 'blocked' : anomalies.length > 0 ? 'provisional' : 'ready_for_critique';
  const referenceCards = selectReferenceCards(brief, 3);
  const embeddingAlignment = await computeEmbeddingAlignment({
    analysis: raw,
    brief,
    references: referenceCards,
    runDir,
  });
  const sectionNames = validation.sections.map((section) => section.name).filter((name) => raw.sections?.[name]);
  const confidenceNotes = [...new Set([...(raw.confidence_notes ?? []), ...(embeddingAlignment.confidence_notes ?? [])])];
  const payload = {
    phase: 'analyze',
    status: readiness === 'ready_for_critique' ? 'ok' : readiness === 'blocked' ? 'blocked' : 'partial',
    song: slug,
    run_dir: runDir,
    readiness,
    metrics: raw.mix,
    rhythm: raw.rhythm ?? raw.mix?.rhythm ?? {},
    structure: raw.structure ?? raw.mix?.structure ?? {},
    tonal: raw.tonal ?? raw.mix?.tonal ?? {},
    timbre: raw.timbre ?? raw.mix?.timbre ?? {},
    sections: raw.sections,
    section_transitions: computeSectionTransitions(sectionNames, raw.sections ?? {}),
    embedding_alignment: embeddingAlignment,
    confidence_notes: confidenceNotes,
    anomalies,
    runtime_blockers: runtimeBlockers,
  };

  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`);

  return {
    phase: 'song:analyze',
    status: payload.status,
    exitCode: payload.status === 'blocked' ? EXIT_CODES.ANALYSIS_BLOCKED : EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: null,
    readiness,
    anomalies,
    runtime_blockers: runtimeBlockers,
    recommended_next_action: payload.status === 'blocked' ? 'revise' : null,
    approval_required: false,
    message:
      payload.status === 'blocked'
        ? `Analysis completed for ${slug}, but the run is blocked by render/runtime issues.`
        : `Wrote analysis to ${outputPath}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongAnalyze, process.argv.slice(2)));
}
