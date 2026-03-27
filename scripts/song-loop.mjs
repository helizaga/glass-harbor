import { readFileSync } from 'node:fs';

import { findLatestRunDir, resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { appendMemoryHistory, chooseBaselineRun, ensureSongMemory, updateSongMemory } from '../lib/review-gates.mjs';
import { handleSongAnalyze } from './song-analyze.mjs';
import { handleSongCritique } from './song-critique.mjs';
import { handleSongRender } from './song-render.mjs';
import { handleSongRevise } from './song-revise.mjs';

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
  if (!Number.isFinite(maxIters) || maxIters <= 0) {
    throw new CommandError('Usage: --max-iters must be a positive integer.', {
      exitCode: EXIT_CODES.USAGE,
      code: 'invalid_max_iters',
    });
  }

  let iteration = 0;
  let finalExitCode = EXIT_CODES.OK;
  let reviseResult = null;
  let activeRunDir = null;
  let baselineRunDir = null;
  let recommendedNextAction = null;
  let approvalRequired = false;
  let changeSummary = null;
  let regressionFlags = [];
  ensureSongMemory(slug);
  while (iteration < maxIters) {
    iteration += 1;

    const renderResult = await handleSongRender({ argv: ['--song', slug] });
    activeRunDir = renderResult.run_dir ?? activeRunDir;
    finalExitCode = renderResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode === EXIT_CODES.RENDER_BLOCKED || finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    const analyzeResult = await handleSongAnalyze({ argv: ['--song', slug] });
    activeRunDir = analyzeResult.run_dir ?? activeRunDir;
    finalExitCode = analyzeResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode === EXIT_CODES.ANALYSIS_BLOCKED || finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    const critiqueResult = await handleSongCritique({ argv: ['--song', slug] });
    activeRunDir = critiqueResult.run_dir ?? activeRunDir;
    finalExitCode = critiqueResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    reviseResult = await handleSongRevise({ argv: ['--song', slug] });
    activeRunDir = reviseResult.run_dir ?? activeRunDir;
    baselineRunDir = reviseResult.baseline_run_dir ?? baselineRunDir;
    recommendedNextAction = reviseResult.recommended_next_action ?? recommendedNextAction;
    approvalRequired = reviseResult.approval_required ?? approvalRequired;
    finalExitCode = reviseResult.exitCode ?? EXIT_CODES.OK;
    if (finalExitCode !== EXIT_CODES.OK) {
      break;
    }

    if (
      iteration >= maxIters ||
      reviseResult.status === 'noop' ||
      reviseResult.recommended_next_action !== 'revise'
    ) {
      break;
    }
  }

  const runDir = activeRunDir ?? findLatestRunDir(slug);
  let verdict = null;
  if (runDir && reviseResult?.verdict_path) {
    try {
      verdict = JSON.parse(readFileSync(reviseResult.verdict_path, 'utf8'));
    } catch (error) {
      console.warn(`Failed to parse ${reviseResult.verdict_path}: ${error.message}`);
      verdict = null;
    }
  }
  if (verdict) {
    baselineRunDir = verdict.baseline_run_dir ?? baselineRunDir;
    recommendedNextAction = verdict.recommended_next_action ?? recommendedNextAction;
    approvalRequired = verdict.approval_required ?? approvalRequired;
    changeSummary = verdict.change_summary ?? null;
    regressionFlags = verdict.regression_flags ?? [];

    updateSongMemory(slug, (memory) =>
      appendMemoryHistory(
        {
          ...memory,
          last_attempted_run_dir: runDir,
          pending_review_run_dir: verdict.recommended_next_action === 'review_gate' ? runDir : null,
          current_open_issue: verdict.summary ?? memory.current_open_issue ?? null,
        },
        {
          at: new Date().toISOString(),
          run_dir: runDir,
          baseline_run_dir: verdict.baseline_run_dir ?? chooseBaselineRun(slug, { memory, excludeRunDir: runDir }),
          decision: verdict.verdict,
          summary: verdict.summary,
          recommended_next_action: verdict.recommended_next_action,
        },
      ),
    );
  }

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
    baseline_run_dir: baselineRunDir,
    revision_request_path: reviseResult?.request_path ?? null,
    revision_prompt_path: reviseResult?.prompt_path ?? null,
    verdict_path: reviseResult?.verdict_path ?? null,
    verdict_markdown_path: reviseResult?.verdict_markdown_path ?? null,
    summary_path: reviseResult?.summary_path ?? null,
    change_summary: changeSummary,
    regression_flags: regressionFlags,
    recommended_next_action: recommendedNextAction,
    approval_required: approvalRequired,
    message:
      finalExitCode === EXIT_CODES.OK
        ? `Completed ${iteration} review pass${iteration === 1 ? '' : 'es'} for ${slug}.`
        : `Stopped ${slug} review loop after ${iteration} iteration${iteration === 1 ? '' : 's'}.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongLoop, process.argv.slice(2)));
}
