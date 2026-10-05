import { resolveRunDir, resolveSongSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  appendMemoryHistory,
  buildApprovalRecord,
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  isReviewReadyGate,
  loadRunVerdict,
  updateSongMemory,
  weightedScore,
} from '../lib/review-gates.mjs';

function parseReason(argv) {
  const index = argv.indexOf('--reason');
  return index !== -1 && argv[index + 1] ? argv[index + 1].trim() : null;
}

function parseMultiFlag(argv, flag) {
  const values = [];
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === flag && argv[index + 1]) {
      values.push(
        ...argv[index + 1]
          .split(',')
          .map((entry) => entry.trim())
          .filter(Boolean),
      );
      index += 1;
    }
  }
  return [...new Set(values)];
}

function seededTechniqueStrengths(critique) {
  return critique?.strudel_techniques?.strengths ?? [];
}

export async function handleSongApprove({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song approve <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--preserve-technique <technique>] [--avoid <trait>] [--avoid-technique <technique>] [--tradeoff <note>]', {
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
  const preserve = parseMultiFlag(argv, '--preserve');
  const preserveTechniques = parseMultiFlag(argv, '--preserve-technique');
  const avoid = parseMultiFlag(argv, '--avoid');
  const avoidTechniques = parseMultiFlag(argv, '--avoid-technique');
  const tradeoffs = parseMultiFlag(argv, '--tradeoff');
  const previousBaseline = chooseBaselineRun(slug, { memory, excludeRunDir: null });
  const nextMemory = updateSongMemory(slug, (current) =>
    appendMemoryHistory(
      {
        ...current,
        approved_baseline_run_dir: runDir,
        pending_review_run_dir: current.pending_review_run_dir === runDir ? null : current.pending_review_run_dir,
        last_attempted_run_dir: runDir,
        current_best_comparison_score: weightedScore(critique.scores ?? {}),
        current_open_issue: isReviewReadyGate(critique.gate) ? null : critique.summary ?? null,
        taste_profile: {
          example_targets: critique.taste_memory?.example_targets ?? current.taste_profile?.example_targets ?? [],
          preferred_lanes: [
            ...new Set([
              ...(current.taste_profile?.preferred_lanes ?? []),
              ...(critique.taste_memory?.preferred_lanes ?? []),
              ...(critique.style_profile?.label ? [critique.style_profile.label] : []),
            ]),
          ],
          avoid_lanes: current.taste_profile?.avoid_lanes ?? [],
          current_lane: critique.style_profile?.label ?? critique.taste_memory?.current_lane ?? current.taste_profile?.current_lane ?? null,
          current_accent:
            critique.style_profile?.accent ?? critique.taste_memory?.current_accent ?? current.taste_profile?.current_accent ?? null,
          lane_notes: [
            ...new Set([
              ...(current.taste_profile?.lane_notes ?? []),
              ...(critique.taste_memory?.lane_notes ?? []),
            ]),
          ],
          preserve_traits: preserve.length > 0 ? preserve : critique.taste_memory?.preserve_traits ?? current.taste_profile?.preserve_traits ?? [],
          preserve_techniques:
            preserveTechniques.length > 0
              ? preserveTechniques
              : [
                  ...new Set([
                    ...(critique.taste_memory?.preserve_techniques ?? current.taste_profile?.preserve_techniques ?? []),
                    ...seededTechniqueStrengths(critique),
                  ]),
                ],
          avoid_traits: avoid.length > 0 ? avoid : critique.taste_memory?.avoid_traits ?? current.taste_profile?.avoid_traits ?? [],
          avoid_techniques:
            avoidTechniques.length > 0
              ? avoidTechniques
              : critique.taste_memory?.avoid_techniques ?? current.taste_profile?.avoid_techniques ?? [],
          source_material_sources:
            critique.taste_memory?.source_material_sources ?? current.taste_profile?.source_material_sources ?? [],
          sourced_truths: critique.taste_memory?.sourced_truths ?? current.taste_profile?.sourced_truths ?? [],
          musical_inferences:
            critique.taste_memory?.musical_inferences ?? current.taste_profile?.musical_inferences ?? [],
          capability_gaps: critique.taste_memory?.capability_gaps ?? current.taste_profile?.capability_gaps ?? [],
          accepted_tradeoffs: [
            ...new Set([
              ...(current.taste_profile?.accepted_tradeoffs ?? []),
              ...(tradeoffs.length > 0
                ? tradeoffs
                : critique.top_weakness
                  ? [`accepted tradeoff: ${critique.top_weakness}`]
                  : []),
            ]),
          ],
          rejected_patterns: current.taste_profile?.rejected_patterns ?? [],
          human_notes: [...new Set([...(current.taste_profile?.human_notes ?? []), ...(reason ? [reason] : [])])],
        },
      },
      buildApprovalRecord({
        slug,
        runDir,
        baselineRunDir: previousBaseline,
        reason,
        preserve,
        preserveTechniques,
        avoid,
        avoidTechniques,
        tradeoffs,
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
    recommended_next_action: isReviewReadyGate(critique.gate) ? 'keep' : 'revise',
    approval_required: false,
    memory_path: `songs/${slug}/memory.json`,
    taste_profile: nextMemory.taste_profile,
    verdict: verdict?.verdict ?? null,
    message: `Approved ${slug} run ${runDir} as the new baseline.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongApprove, process.argv.slice(2)));
}
