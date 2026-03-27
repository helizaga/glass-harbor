import { statSync } from 'node:fs';

import { findLatestRunDir, resolveSongSlug, songPaths } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { handleSongAnalyze } from './song-analyze.mjs';
import { handleSongCritique } from './song-critique.mjs';
import { handleSongRender } from './song-render.mjs';

export async function handleSongLoop({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song loop <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const maxIndex = argv.indexOf('--max-iters');
  const maxIters = maxIndex !== -1 && argv[maxIndex + 1] ? Number.parseInt(argv[maxIndex + 1], 10) : 1;
  const songPath = songPaths(slug).songPath;

  let iteration = 0;
  let finalExitCode = EXIT_CODES.OK;
  while (iteration < maxIters) {
    iteration += 1;
    const beforeStat = statSync(songPath).mtimeMs;

    const renderResult = await handleSongRender({ argv: ['--song', slug] });
    finalExitCode = renderResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode === EXIT_CODES.RENDER_BLOCKED || finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    const analyzeResult = await handleSongAnalyze({ argv: ['--song', slug] });
    finalExitCode = analyzeResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode === EXIT_CODES.ANALYSIS_BLOCKED || finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    const critiqueResult = await handleSongCritique({ argv: ['--song', slug] });
    finalExitCode = critiqueResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    const afterStat = statSync(songPath).mtimeMs;
    if (afterStat === beforeStat) {
      break;
    }
  }

  const runDir = findLatestRunDir(slug);
  return {
    phase: 'song:loop',
    status:
      finalExitCode === EXIT_CODES.OK
        ? 'ok'
        : finalExitCode === EXIT_CODES.RENDER_BLOCKED
          ? 'render_blocked'
          : finalExitCode === EXIT_CODES.ANALYSIS_BLOCKED
            ? 'analysis_blocked'
            : 'failed',
    exitCode: finalExitCode,
    song: slug,
    iterations: iteration,
    run_dir: runDir,
    message:
      finalExitCode === EXIT_CODES.OK
        ? `Completed ${iteration} review pass${iteration === 1 ? '' : 'es'} for ${slug}.`
        : `Stopped ${slug} review loop after ${iteration} iteration${iteration === 1 ? '' : 's'}.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongLoop, process.argv.slice(2)));
}
