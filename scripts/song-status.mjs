import {
  buildStyleRolePlan,
  evaluateStyleProfileUsage,
  parseBrief,
  readText,
  resolveSongSlug,
  resolveStyleProfile,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  isReviewReadyGate,
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
  const approvedBaselineRunDir = memory.approved_baseline_run_dir ?? null;
  const comparisonBaselineRunDir = chooseBaselineRun(slug, { memory });
  // chooseBaselineRun only returns listener-approved runs, so a seeded or
  // rejected approved_baseline_run_dir is never reported as the baseline.
  const baselineRunDir = comparisonBaselineRunDir;
  const pendingRunDir = memory.pending_review_run_dir ?? null;
  const songValidation = validateSongCode(readText(songPaths(slug).songPath));
  const baselineVerdict = loadRunVerdict(baselineRunDir);
  const pendingVerdict = loadRunVerdict(pendingRunDir);
  const baselineCritique = critiqueForRun(baselineRunDir);
  const pendingCritique = critiqueForRun(pendingRunDir);
  const brief = parseBrief(readText(songPaths(slug).briefPath));
  const effectiveTasteProfile = {
    example_targets: [
      ...new Set([
        ...(memory.taste_profile?.example_targets ?? []),
        ...(pendingCritique?.taste_memory?.example_targets ?? []),
        ...(baselineCritique?.taste_memory?.example_targets ?? []),
      ]),
    ],
    preferred_lanes: [
      ...new Set([
        ...(memory.taste_profile?.preferred_lanes ?? []),
        ...(pendingCritique?.taste_memory?.preferred_lanes ?? []),
        ...(baselineCritique?.taste_memory?.preferred_lanes ?? []),
      ]),
    ],
    avoid_lanes: [
      ...new Set([
        ...(memory.taste_profile?.avoid_lanes ?? []),
        ...(pendingCritique?.taste_memory?.avoid_lanes ?? []),
        ...(baselineCritique?.taste_memory?.avoid_lanes ?? []),
      ]),
    ],
    current_lane:
      pendingCritique?.taste_memory?.current_lane ??
      baselineCritique?.taste_memory?.current_lane ??
      memory.taste_profile?.current_lane ??
      null,
    current_accent:
      pendingCritique?.taste_memory?.current_accent ??
      baselineCritique?.taste_memory?.current_accent ??
      memory.taste_profile?.current_accent ??
      null,
    lane_notes: [
      ...new Set([
        ...(memory.taste_profile?.lane_notes ?? []),
        ...(pendingCritique?.taste_memory?.lane_notes ?? []),
        ...(baselineCritique?.taste_memory?.lane_notes ?? []),
      ]),
    ],
    preserve_traits: [
      ...new Set([
        ...(memory.taste_profile?.preserve_traits ?? []),
        ...(pendingCritique?.taste_memory?.preserve_traits ?? []),
        ...(baselineCritique?.taste_memory?.preserve_traits ?? []),
      ]),
    ],
    preserve_techniques: [
      ...new Set([
        ...(memory.taste_profile?.preserve_techniques ?? []),
        ...(pendingCritique?.taste_memory?.preserve_techniques ?? []),
        ...(baselineCritique?.taste_memory?.preserve_techniques ?? []),
      ]),
    ],
    avoid_traits: [
      ...new Set([
        ...(memory.taste_profile?.avoid_traits ?? []),
        ...(pendingCritique?.taste_memory?.avoid_traits ?? []),
        ...(baselineCritique?.taste_memory?.avoid_traits ?? []),
      ]),
    ],
    avoid_techniques: [
      ...new Set([
        ...(memory.taste_profile?.avoid_techniques ?? []),
        ...(pendingCritique?.taste_memory?.avoid_techniques ?? []),
        ...(baselineCritique?.taste_memory?.avoid_techniques ?? []),
      ]),
    ],
    source_material_sources: [
      ...new Set([
        ...(memory.taste_profile?.source_material_sources ?? []),
        ...(pendingCritique?.taste_memory?.source_material_sources ?? []),
        ...(baselineCritique?.taste_memory?.source_material_sources ?? []),
      ]),
    ],
    sourced_truths: [
      ...new Set([
        ...(memory.taste_profile?.sourced_truths ?? []),
        ...(pendingCritique?.taste_memory?.sourced_truths ?? []),
        ...(baselineCritique?.taste_memory?.sourced_truths ?? []),
      ]),
    ],
    musical_inferences: [
      ...new Set([
        ...(memory.taste_profile?.musical_inferences ?? []),
        ...(pendingCritique?.taste_memory?.musical_inferences ?? []),
        ...(baselineCritique?.taste_memory?.musical_inferences ?? []),
      ]),
    ],
    capability_gaps: [
      ...new Set([
        ...(memory.taste_profile?.capability_gaps ?? []),
        ...(pendingCritique?.taste_memory?.capability_gaps ?? []),
        ...(baselineCritique?.taste_memory?.capability_gaps ?? []),
      ]),
    ],
    accepted_tradeoffs: [
      ...new Set([
        ...(memory.taste_profile?.accepted_tradeoffs ?? []),
        ...(pendingCritique?.taste_memory?.accepted_tradeoffs ?? []),
        ...(baselineCritique?.taste_memory?.accepted_tradeoffs ?? []),
      ]),
    ],
    rejected_patterns: [...new Set(memory.taste_profile?.rejected_patterns ?? [])],
    human_notes: memory.taste_profile?.human_notes ?? [],
  };
  const styleProfile = resolveStyleProfile(brief, { tasteProfile: effectiveTasteProfile });
  const styleProfileUsage = evaluateStyleProfileUsage({
    dependencies: songValidation.dependencies,
    strudelTechniques: songValidation.strudelTechniques,
    styleProfile,
  });
  const styleRolePlan = buildStyleRolePlan({
    styleProfile,
    dependencies: songValidation.dependencies,
    strudelTechniques: songValidation.strudelTechniques,
  });
  const laneNeedsPrune =
    (styleRolePlan?.suggested_pruned_roles?.length ?? 0) > 0 || (styleProfileUsage?.hook_spread ?? 'focused') === 'diffuse';

  const payload = {
    phase: 'song:status',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    memory_path: songMemoryPath(slug),
    baseline_run_dir: baselineRunDir,
    approved_baseline_run_dir: approvedBaselineRunDir,
    comparison_baseline_run_dir: comparisonBaselineRunDir,
    pending_review_run_dir: pendingRunDir,
    last_attempted_run_dir: memory.last_attempted_run_dir ?? null,
    current_open_issue: memory.current_open_issue ?? null,
    current_best_comparison_score: memory.current_best_comparison_score ?? null,
    taste_profile: effectiveTasteProfile,
    style_profile: styleProfile,
    style_profile_usage: styleProfileUsage,
    style_role_plan: styleRolePlan,
    strudel_techniques: songValidation.strudelTechniques,
    recommended_next_action:
      pendingVerdict?.recommended_next_action ??
      (pendingRunDir
        ? 'review_gate'
        : memory.current_open_issue || !baselineRunDir || !isReviewReadyGate(baselineCritique?.gate) || laneNeedsPrune
          ? 'revise'
          : 'keep'),
    approval_required: Boolean(pendingRunDir),
    baseline: {
      run_dir: baselineRunDir,
      approved: Boolean(baselineRunDir),
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
          : memory.current_open_issue || laneNeedsPrune
            ? `Song ${slug} still has feedback to address.`
            : `Song ${slug} is currently anchored to its approved baseline run.`,
  };

  return payload;
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongStatus, process.argv.slice(2)));
}
