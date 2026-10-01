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

function seededTechniqueWeaknesses(critique) {
  return critique?.strudel_techniques?.opportunities ?? [];
}

export async function handleSongReject({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song reject <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--preserve-technique <technique>] [--avoid <trait>] [--avoid-technique <technique>] [--tradeoff <note>]', {
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
  const preserve = parseMultiFlag(argv, '--preserve');
  const preserveTechniques = parseMultiFlag(argv, '--preserve-technique');
  const avoid = parseMultiFlag(argv, '--avoid');
  const avoidTechniques = parseMultiFlag(argv, '--avoid-technique');
  const tradeoffs = parseMultiFlag(argv, '--tradeoff');
  const baselineRunDir = chooseBaselineRun(slug, { memory });
  const nextMemory = updateSongMemory(slug, (current) =>
    appendMemoryHistory(
      {
        ...current,
        pending_review_run_dir: current.pending_review_run_dir === runDir ? null : current.pending_review_run_dir,
        last_attempted_run_dir: runDir,
        current_open_issue: reason ?? critique.summary ?? current.current_open_issue ?? null,
        taste_profile: {
          example_targets: critique.taste_memory?.example_targets ?? current.taste_profile?.example_targets ?? [],
          preferred_lanes: [
            ...new Set([
              ...(current.taste_profile?.preferred_lanes ?? []),
              ...(critique.taste_memory?.preferred_lanes ?? []),
            ]),
          ],
          avoid_lanes: [
            ...new Set([
              ...(current.taste_profile?.avoid_lanes ?? []),
              ...(critique.style_profile?.label ? [critique.style_profile.label] : []),
            ]),
          ],
          current_lane: current.taste_profile?.current_lane ?? critique.taste_memory?.current_lane ?? null,
          current_accent: current.taste_profile?.current_accent ?? critique.taste_memory?.current_accent ?? null,
          lane_notes: [
            ...new Set([
              ...(current.taste_profile?.lane_notes ?? []),
              ...(critique.taste_memory?.lane_notes ?? []),
              ...(reason ? [reason] : []),
            ]),
          ],
          preserve_traits: preserve.length > 0 ? preserve : critique.taste_memory?.preserve_traits ?? current.taste_profile?.preserve_traits ?? [],
          preserve_techniques: [
            ...new Set([
              ...(current.taste_profile?.preserve_techniques ?? []),
              ...(preserveTechniques.length > 0
                ? preserveTechniques
                : critique.taste_memory?.preserve_techniques ?? []),
            ]),
          ],
          avoid_traits: [...new Set([...(current.taste_profile?.avoid_traits ?? []), ...(avoid.length > 0 ? avoid : critique.taste_memory?.avoid_traits ?? [])])],
          avoid_techniques: [
            ...new Set([
              ...(current.taste_profile?.avoid_techniques ?? []),
              ...(avoidTechniques.length > 0
                ? avoidTechniques
                : [...(critique.taste_memory?.avoid_techniques ?? []), ...seededTechniqueWeaknesses(critique)]),
            ]),
          ],
          source_material_sources:
            critique.taste_memory?.source_material_sources ?? current.taste_profile?.source_material_sources ?? [],
          sourced_truths: critique.taste_memory?.sourced_truths ?? current.taste_profile?.sourced_truths ?? [],
          musical_inferences:
            critique.taste_memory?.musical_inferences ?? current.taste_profile?.musical_inferences ?? [],
          capability_gaps: critique.taste_memory?.capability_gaps ?? current.taste_profile?.capability_gaps ?? [],
          accepted_tradeoffs: current.taste_profile?.accepted_tradeoffs ?? [],
          rejected_patterns: [
            ...new Set([
              ...(current.taste_profile?.rejected_patterns ?? []),
              ...(tradeoffs.length > 0
                ? tradeoffs.map((entry) => `rejected tradeoff: ${entry}`)
                : critique.top_weakness
                  ? [`rejected weakness: ${critique.top_weakness}`]
                  : []),
              ...(reason ? [reason] : []),
            ]),
          ],
          human_notes: [...new Set([...(current.taste_profile?.human_notes ?? []), ...(reason ? [reason] : [])])],
        },
      },
      buildRejectionRecord({
        slug,
        runDir,
        baselineRunDir,
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
    phase: 'song:reject',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    recommended_next_action: 'revise',
    approval_required: false,
    memory_path: `songs/${slug}/memory.json`,
    taste_profile: nextMemory.taste_profile,
    verdict: verdict?.verdict ?? null,
    pending_review_run_dir: nextMemory.pending_review_run_dir ?? null,
    message: `Rejected ${slug} run ${runDir}; baseline remains unchanged.`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongReject, process.argv.slice(2)));
}
