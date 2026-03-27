import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

import { normalizeRuntimeErrors, readText, resolveRunDir, resolveSongSlug, songPaths, validateSongCode } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';

function runPython(args) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', args, { stdio: 'inherit' });
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

export async function handleSongAnalyze({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song analyze <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const runDir = resolveRunDir(argv, slug) ?? '';

  if (!runDir || !existsSync(join(runDir, 'mix.wav'))) {
    throw new CommandError(`No rendered run found for ${slug}. Run glass-harbor song render ${slug} first.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'run_missing',
    });
  }

  const song = songPaths(slug);
  const validation = validateSongCode(readText(song.songPath));
  const outputPath = join(runDir, 'analysis.json');

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

  const raw = JSON.parse(readFileSync(outputPath, 'utf8'));
  const runInfo = existsSync(join(runDir, 'run.json'))
    ? JSON.parse(readFileSync(join(runDir, 'run.json'), 'utf8'))
    : { runtime_blockers: [], console_errors: [] };

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
    runInfo.runtime_blockers?.length > 0 ? runInfo.runtime_blockers : normalizeRuntimeErrors(runInfo.console_errors);
  if (runtimeBlockers.length > 0) {
    anomalies.push('Render phase reported runtime blockers.');
  }

  const readiness =
    runtimeBlockers.length > 0 ? 'blocked' : anomalies.length > 0 ? 'provisional' : 'ready_for_critique';
  const payload = {
    phase: 'analyze',
    status: readiness === 'ready_for_critique' ? 'ok' : readiness === 'blocked' ? 'blocked' : 'partial',
    song: slug,
    run_dir: runDir,
    readiness,
    metrics: raw.mix,
    sections: raw.sections,
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
    readiness,
    anomalies,
    runtime_blockers: runtimeBlockers,
    message:
      payload.status === 'blocked'
        ? `Analysis completed for ${slug}, but the run is blocked by render/runtime issues.`
        : `Wrote analysis to ${outputPath}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongAnalyze, process.argv.slice(2)));
}
