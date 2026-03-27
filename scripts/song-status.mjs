import { resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  loadRunVerdict,
  loadSongMemory,
  songMemoryPath,
  summaryPath,
} from '../lib/review-gates.mjs';

function latestHistory(history = [], limit = 3) {
  return [...history].slice(-limit).reverse();
}

export async function handleSongStatus({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song status <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const memory = ensureSongMemory(slug);
  const baselineRunDir = chooseBaselineRun(slug, { memory });
  const pendingRunDir = memory.pending_review_run_dir ?? null;
  const baselineVerdict = loadRunVerdict(baselineRunDir);
  const pendingVerdict = loadRunVerdict(pendingRunDir);
  const baselineCritique = critiqueForRun(baselineRunDir);
  const pendingCritique = critiqueForRun(pendingRunDir);

  const payload = {
    phase: 'song:status',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    memory_path: songMemoryPath(slug),
    baseline_run_dir: baselineRunDir,
    pending_review_run_dir: pendingRunDir,
    last_attempted_run_dir: memory.last_attempted_run_dir ?? null,
    current_open_issue: memory.current_open_issue ?? null,
    current_best_comparison_score: memory.current_best_comparison_score ?? null,
    recommended_next_action:
      pendingVerdict?.recommended_next_action ??
      (pendingRunDir
        ? 'review_gate'
        : memory.current_open_issue || !baselineRunDir || baselineCritique?.gate !== 'pass'
          ? 'revise'
          : 'keep'),
    approval_required: Boolean(pendingRunDir),
    baseline: {
      run_dir: baselineRunDir,
      verdict: baselineVerdict?.verdict ?? null,
      summary: baselineVerdict?.summary ?? baselineCritique?.summary ?? null,
      gate: baselineCritique?.gate ?? null,
      summary_path: summaryPath(baselineRunDir),
    },
    pending_review: pendingRunDir
      ? {
          run_dir: pendingRunDir,
          verdict: pendingVerdict?.verdict ?? null,
          summary: pendingVerdict?.summary ?? pendingCritique?.summary ?? null,
          gate: pendingCritique?.gate ?? null,
          recommended_next_action: pendingVerdict?.recommended_next_action ?? 'review_gate',
          approval_required: Boolean(pendingVerdict?.approval_required ?? true),
          summary_path: summaryPath(pendingRunDir),
        }
      : null,
    history: latestHistory(memory.history),
    message: pendingRunDir
      ? `Song ${slug} has a pending review run waiting for approval.`
      : !baselineRunDir
        ? `Song ${slug} does not have an approved baseline yet.`
        : memory.current_open_issue
          ? `Song ${slug} still has feedback to address.`
          : `Song ${slug} is currently anchored to its approved baseline run.`,
  };

  return payload;
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongStatus, process.argv.slice(2)));
}
