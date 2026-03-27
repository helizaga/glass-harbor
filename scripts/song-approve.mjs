import { resolveRunDir, resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  appendMemoryHistory,
  buildApprovalRecord,
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  loadRunVerdict,
  updateSongMemory,
  weightedScore,
} from '../lib/review-gates.mjs';

function parseReason(argv) {
  const index = argv.indexOf('--reason');
  return index !== -1 && argv[index + 1] ? argv[index + 1].trim() : null;
}

export async function handleSongApprove({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song approve <slug> [--run <path>] [--reason <text>]', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const memory = ensureSongMemory(slug);
  const requestedRunDir = resolveRunDir(argv, slug);
  const runDir = argv.includes('--run') ? requestedRunDir : memory.pending_review_run_dir ?? requestedRunDir;
  if (!runDir) {
    throw new CommandError(`No run available to approve for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'approve_run_missing',
    });
  }

  const verdict = loadRunVerdict(runDir);
  const critique = critiqueForRun(runDir);
  if (!critique) {
    throw new CommandError(`No critique found for ${slug} at ${runDir}.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'approve_critique_missing',
    });
  }

  const reason = parseReason(argv);
  const previousBaseline = chooseBaselineRun(slug, { memory, excludeRunDir: null });
  const nextMemory = updateSongMemory(slug, (current) =>
    appendMemoryHistory(
      {
        ...current,
        approved_baseline_run_dir: runDir,
        pending_review_run_dir: current.pending_review_run_dir === runDir ? null : current.pending_review_run_dir,
        last_attempted_run_dir: runDir,
        current_best_comparison_score: weightedScore(critique.scores ?? {}),
        current_open_issue: critique.gate === 'pass' ? null : critique.summary ?? null,
      },
      buildApprovalRecord({
        slug,
        runDir,
        baselineRunDir: previousBaseline,
        reason,
      }),
    ),
  );

  return {
    phase: 'song:approve',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: nextMemory.approved_baseline_run_dir,
    previous_baseline_run_dir: previousBaseline,
    recommended_next_action: critique.gate === 'pass' ? 'keep' : 'revise',
    approval_required: false,
    memory_path: `songs/${slug}/memory.json`,
    verdict: verdict?.verdict ?? null,
    message: `Approved ${slug} run ${runDir} as the new baseline.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongApprove, process.argv.slice(2)));
}
