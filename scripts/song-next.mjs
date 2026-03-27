import { resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { handleSongStatus } from './song-status.mjs';

function buildApproveCommand(slug, runDir) {
  return runDir ? `glass-harbor song approve ${slug} --run ${runDir}` : `glass-harbor song approve ${slug}`;
}

function buildRejectCommand(slug, runDir) {
  return runDir ? `glass-harbor song reject ${slug} --run ${runDir}` : `glass-harbor song reject ${slug}`;
}

function buildReviseCommand(slug, runDir) {
  return runDir ? `glass-harbor song revise ${slug} --run ${runDir}` : `glass-harbor song revise ${slug}`;
}

function buildLoopCommand(slug) {
  return `glass-harbor song loop ${slug} --max-iters 1 --json`;
}

function buildNextAction(statusPayload) {
  const slug = statusPayload.song;
  const pending = statusPayload.pending_review;
  const baseline = statusPayload.baseline;

  if (pending?.run_dir) {
    return {
      type: 'review_gate',
      reason: pending.summary ?? 'A pending review run is waiting for approval.',
      approval_required: true,
      target_slug: slug,
      target_run_dir: pending.run_dir,
      commands: {
        approve: buildApproveCommand(slug, pending.run_dir),
        reject: buildRejectCommand(slug, pending.run_dir),
      },
      summary_path: pending.summary_path ?? null,
    };
  }

  if (!baseline?.run_dir) {
    return {
      type: 'run_loop',
      reason: 'No approved baseline exists yet, so the next step is to generate a reviewed run.',
      approval_required: false,
      target_slug: slug,
      target_run_dir: null,
      commands: {
        run: buildLoopCommand(slug),
      },
      summary_path: null,
    };
  }

  if (
    (statusPayload.recommended_next_action === 'keep' || baseline.gate === 'pass' || baseline.gate === 'review_gate') &&
    !statusPayload.current_open_issue
  ) {
    return {
      type: 'stop',
      reason: baseline.summary ?? 'The approved baseline already clears the current review gate.',
      approval_required: false,
      target_slug: slug,
      target_run_dir: baseline.run_dir,
      commands: {},
      summary_path: baseline.summary_path ?? null,
    };
  }

  const revisionRunDir = statusPayload.last_attempted_run_dir ?? baseline.run_dir;
  return {
    type: 'revise_song',
    reason: statusPayload.current_open_issue ?? baseline.summary ?? 'The song still needs revision work.',
    approval_required: false,
    target_slug: slug,
    target_run_dir: revisionRunDir,
    commands: {
      revise: buildReviseCommand(slug, revisionRunDir),
      loop: buildLoopCommand(slug),
    },
    summary_path: baseline.summary_path ?? null,
  };
}

export async function handleSongNext({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song next <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const statusPayload = await handleSongStatus({ argv: ['--song', slug] });
  const nextAction = buildNextAction(statusPayload);

  return {
    phase: 'song:next',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: nextAction.target_run_dir,
    baseline_run_dir: statusPayload.baseline_run_dir,
    recommended_next_action: nextAction.type,
    approval_required: nextAction.approval_required,
    next_action: nextAction,
    status_snapshot: {
      pending_review_run_dir: statusPayload.pending_review_run_dir,
      last_attempted_run_dir: statusPayload.last_attempted_run_dir,
      current_open_issue: statusPayload.current_open_issue,
      baseline_run_dir: statusPayload.baseline_run_dir,
    },
    message:
      nextAction.type === 'review_gate'
        ? `Song ${slug} is waiting at a review gate.`
        : nextAction.type === 'stop'
          ? `Song ${slug} does not need an immediate follow-up action.`
          : `Next action for ${slug}: ${nextAction.type}.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongNext, process.argv.slice(2)));
}
