import { resolveRunDir, resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  appendMemoryHistory,
  buildRejectionRecord,
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  loadRunVerdict,
  updateSongMemory,
} from '../lib/review-gates.mjs';

function parseReason(argv) {
  const index = argv.indexOf('--reason');
  return index !== -1 && argv[index + 1] ? argv[index + 1].trim() : null;
}

export async function handleSongReject({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song reject <slug> [--run <path>] [--reason <text>]', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const memory = ensureSongMemory(slug);
  const requestedRunDir = resolveRunDir(argv, slug);
  const runDir = argv.includes('--run') ? requestedRunDir : memory.pending_review_run_dir ?? requestedRunDir;
  if (!runDir) {
    throw new CommandError(`No run available to reject for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'reject_run_missing',
    });
  }

  const critique = critiqueForRun(runDir);
  if (!critique) {
    throw new CommandError(`No critique found for ${slug} at ${runDir}.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'reject_critique_missing',
    });
  }

  const verdict = loadRunVerdict(runDir);
  const reason = parseReason(argv);
  const baselineRunDir = chooseBaselineRun(slug, { memory });
  const nextMemory = updateSongMemory(slug, (current) =>
    appendMemoryHistory(
      {
        ...current,
        pending_review_run_dir: current.pending_review_run_dir === runDir ? null : current.pending_review_run_dir,
        last_attempted_run_dir: runDir,
        current_open_issue: reason ?? critique.summary ?? current.current_open_issue ?? null,
      },
      buildRejectionRecord({
        slug,
        runDir,
        baselineRunDir,
        reason,
      }),
    ),
  );

  return {
    phase: 'song:reject',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    recommended_next_action: 'revise',
    approval_required: false,
    memory_path: `songs/${slug}/memory.json`,
    verdict: verdict?.verdict ?? null,
    pending_review_run_dir: nextMemory.pending_review_run_dir ?? null,
    message: `Rejected ${slug} run ${runDir}; baseline remains unchanged.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongReject, process.argv.slice(2)));
}
