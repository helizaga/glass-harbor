import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  findLatestRunDir,
  formatRunId,
  listSongRunDirs,
  sanitizeSlug,
  songPaths,
} from './song-contract.mjs';

export const REVIEW_GATE_VERSION = '2026-03-27-v2';

export const SCORE_WEIGHTS = {
  groove_strength: 0.22,
  section_contrast: 0.18,
  low_end_cleanliness: 0.16,
  style_fit: 0.14,
  transition_impact: 0.12,
  melodic_memorability: 0.1,
  top_end_harshness: 0.05,
  structure_clarity: 0.03,
};

const PRESERVE_AXIS_DELTA_LIMIT = -0.05;
const TARGET_AXIS_IMPROVEMENT_MIN = 0.03;
const TARGET_AXIS_REGRESSION_LIMIT = -0.001;
const WEIGHTED_IMPROVEMENT_MIN = 0.03;
const WEIGHTED_REGRESSION_LIMIT = -0.03;
const FLAT_DELTA_LIMIT = 0.02;
const HISTORY_LIMIT = 12;

export function isReviewReadyGate(gate) {
  return gate === 'pass' || gate === 'review_gate';
}

function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

function readJson(filePath) {
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch (error) {
    throw new Error(`Failed to parse JSON at ${filePath}: ${error.message}`);
  }
}

function topAxes(scores = {}, { count = 2, descending = true } = {}) {
  const entries = Object.entries(scores)
    .map(([key, value]) => [key, Number(value ?? 0)])
    .sort((left, right) => (descending ? right[1] - left[1] : left[1] - right[1]));
  return entries.slice(0, count).map(([key, value]) => ({ key, value: round(value) }));
}

function deltaForAxis(axis, baselineScores = {}, candidateScores = {}) {
  return round(Number(candidateScores[axis] ?? 0) - Number(baselineScores[axis] ?? 0));
}

function formatDelta(delta) {
  return `${delta >= 0 ? '+' : ''}${round(delta)}`;
}

export function weightedScore(scores = {}) {
  return round(
    Object.entries(SCORE_WEIGHTS).reduce((sum, [key, weight]) => sum + Number(scores[key] ?? 0) * weight, 0),
  );
}

export function strongestAxis(scores = {}) {
  return topAxes(scores, { count: 1, descending: true })[0] ?? null;
}

export function weakestAxis(scores = {}) {
  return topAxes(scores, { count: 1, descending: false })[0] ?? null;
}

export function derivePreserveAxes(scores = {}, count = 2) {
  return topAxes(scores, { count, descending: true }).map((axis) => ({
    ...axis,
    protected_delta_limit: PRESERVE_AXIS_DELTA_LIMIT,
  }));
}

export function deriveTargetAxes(scores = {}, count = 2) {
  return topAxes(scores, { count, descending: false }).map((axis) => ({
    ...axis,
    desired_delta_min: TARGET_AXIS_IMPROVEMENT_MIN,
  }));
}

export function diffScores(baselineScores = {}, candidateScores = {}) {
  const keys = [...new Set([...Object.keys(baselineScores), ...Object.keys(candidateScores)])].sort((left, right) =>
    left.localeCompare(right),
  );

  const deltas = Object.fromEntries(
    keys.map((key) => [key, round(Number(candidateScores[key] ?? 0) - Number(baselineScores[key] ?? 0))]),
  );

  const ranked = keys
    .map((key) => ({
      key,
      baseline: round(Number(baselineScores[key] ?? 0)),
      current: round(Number(candidateScores[key] ?? 0)),
      delta: deltas[key],
    }))
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta) || left.key.localeCompare(right.key));

  return {
    deltas,
    ranked,
  };
}

export function songMemoryPath(slug) {
  return join(songPaths(slug).dir, 'memory.json');
}

function normalizeTasteProfile(tasteProfile = {}) {
  return {
    example_targets: tasteProfile.example_targets ?? [],
    preferred_lanes: tasteProfile.preferred_lanes ?? [],
    avoid_lanes: tasteProfile.avoid_lanes ?? [],
    current_lane: tasteProfile.current_lane ?? null,
    current_accent: tasteProfile.current_accent ?? null,
    lane_notes: tasteProfile.lane_notes ?? [],
    preserve_traits: tasteProfile.preserve_traits ?? [],
    preserve_techniques: tasteProfile.preserve_techniques ?? [],
    avoid_traits: tasteProfile.avoid_traits ?? [],
    avoid_techniques: tasteProfile.avoid_techniques ?? [],
    source_material_sources: tasteProfile.source_material_sources ?? [],
    sourced_truths: tasteProfile.sourced_truths ?? [],
    musical_inferences: tasteProfile.musical_inferences ?? [],
    capability_gaps: tasteProfile.capability_gaps ?? [],
    accepted_tradeoffs: tasteProfile.accepted_tradeoffs ?? [],
    rejected_patterns: tasteProfile.rejected_patterns ?? [],
    human_notes: tasteProfile.human_notes ?? [],
  };
}

function normalizeSongMemory(memory) {
  if (!memory) {
    return null;
  }

  return {
    ...memory,
    taste_profile: normalizeTasteProfile(memory.taste_profile),
    history: memory.history ?? [],
  };
}

export function loadSongMemory(slug) {
  const filePath = songMemoryPath(slug);
  if (!existsSync(filePath)) {
    return null;
  }
  return normalizeSongMemory(readJson(filePath));
}

function readCritiqueFromRun(runDir) {
  const critiquePath = runDir ? join(runDir, 'critique.json') : '';
  return critiquePath && existsSync(critiquePath) ? readJson(critiquePath) : null;
}

function seedBaselineRun(slug, excludeRunDir = null) {
  const runs = listSongRunDirs(slug, { requiredFiles: ['critique.json', 'run.json'] });
  const fallback = runs.find((runDir) => runDir !== excludeRunDir) ?? runs[0] ?? null;
  return fallback;
}

function fallbackBaselineFromHistory(memory, excludeRunDir = null) {
  const preferredDecisions = ['approved', 'improved', 'baseline'];
  const history = [...(memory?.history ?? [])].reverse();

  for (const decision of preferredDecisions) {
    const match = history.find((entry) => entry?.decision === decision && entry.run_dir && entry.run_dir !== excludeRunDir);
    if (match?.run_dir) {
      return match.run_dir;
    }
  }

  return null;
}

export function ensureSongMemory(slug, options = {}) {
  const safeSlug = sanitizeSlug(slug);
  const existing = loadSongMemory(safeSlug);
  if (existing) {
    return existing;
  }

  const approvedBaselineRunDir =
    options.seedRunDir ?? seedBaselineRun(safeSlug, options.excludeRunDir ?? null) ?? null;
  const approvedCritique = readCritiqueFromRun(approvedBaselineRunDir);
  const seededScore = approvedCritique ? weightedScore(approvedCritique.scores) : null;

  const seeded = {
    version: 1,
    song: safeSlug,
    approved_baseline_run_dir: approvedBaselineRunDir,
    pending_review_run_dir: null,
    last_attempted_run_dir: approvedBaselineRunDir,
    current_best_comparison_score: seededScore,
    current_open_issue: isReviewReadyGate(approvedCritique?.gate) ? null : approvedCritique?.summary ?? null,
    taste_profile: {
      example_targets: [],
      preferred_lanes: [],
      avoid_lanes: [],
      current_lane: null,
      current_accent: null,
      lane_notes: [],
      preserve_traits: [],
      preserve_techniques: [],
      avoid_traits: [],
      avoid_techniques: [],
      source_material_sources: [],
      sourced_truths: [],
      musical_inferences: [],
      capability_gaps: [],
      accepted_tradeoffs: [],
      rejected_patterns: [],
      human_notes: [],
    },
    history:
      approvedBaselineRunDir && approvedCritique
        ? [
            {
              at: new Date().toISOString(),
              run_dir: approvedBaselineRunDir,
              decision: 'seed_baseline',
              summary: approvedCritique.summary ?? 'Seeded approved baseline from existing reviewed run.',
              recommended_next_action: 'revise',
            },
          ]
        : [],
  };

  const normalized = normalizeSongMemory(seeded);
  writeFileSync(songMemoryPath(safeSlug), `${JSON.stringify(normalized, null, 2)}\n`);
  return normalized;
}

export function chooseBaselineRun(slug, options = {}) {
  const safeSlug = sanitizeSlug(slug);
  const memory = options.memory ?? ensureSongMemory(safeSlug, options);
  const approved = memory.approved_baseline_run_dir;
  if (approved && approved !== options.excludeRunDir) {
    return approved;
  }

  const historical = fallbackBaselineFromHistory(memory, options.excludeRunDir ?? null);
  if (historical) {
    return historical;
  }

  const fallback = seedBaselineRun(safeSlug, options.excludeRunDir ?? null);
  return fallback ?? approved ?? findLatestRunDir(safeSlug, { requiredFiles: ['critique.json', 'run.json'] });
}

export function updateSongMemory(slug, updater) {
  const safeSlug = sanitizeSlug(slug);
  const current = ensureSongMemory(safeSlug);
  const next = normalizeSongMemory(updater(structuredClone(current)) ?? current);
  writeFileSync(songMemoryPath(safeSlug), `${JSON.stringify(next, null, 2)}\n`);
  return next;
}

export function verdictPath(runDir) {
  return runDir ? join(runDir, 'verdict.json') : '';
}

export function summaryPath(runDir) {
  return runDir ? join(runDir, 'summary.md') : '';
}

function firstAction(actions = []) {
  for (const action of actions) {
    if (!action) {
      continue;
    }
    if (typeof action === 'string' && action.trim()) {
      return action.trim();
    }
    if (typeof action.action === 'string' && action.action.trim()) {
      return action.action.trim();
    }
  }
  return null;
}

function formatAxisLabel(axis = {}) {
  if (!axis?.key) {
    return null;
  }
  return `${axis.key} (${axis.value})`;
}

export function loadRunVerdict(runDir) {
  const filePath = verdictPath(runDir);
  if (!filePath || !existsSync(filePath)) {
    return null;
  }
  return readJson(filePath);
}

function verdictMarkdown(payload) {
  return [
    `# Verdict: ${payload.song}`,
    '',
    `Decision: ${payload.recommended_next_action}`,
    `Approval required: ${payload.approval_required ? 'yes' : 'no'}`,
    `Verdict: ${payload.verdict}`,
    '',
    `What happened: ${payload.summary}`,
    '',
    '## Keep',
    `- ${payload.strongest_trait ?? 'No preserved strength identified yet.'}`,
    ...(payload.taste_memory?.preserve_traits?.length > 0
      ? payload.taste_memory.preserve_traits.map((entry) => `- preserve: ${entry}`)
      : []),
    ...(payload.taste_memory?.preserve_techniques?.length > 0
      ? payload.taste_memory.preserve_techniques.map((entry) => `- keep technique: ${entry}`)
      : []),
    '',
    '## Fix',
    `- ${payload.top_weakness ?? 'No single top weakness identified.'}`,
    `- ${payload.single_next_move ?? 'No concrete next move recorded.'}`,
    ...(payload.regression_flags?.length > 0
      ? payload.regression_flags.slice(0, 2).map((flag) => `- regression: ${flag.axis} (${flag.reason})`)
      : []),
    '',
    '## Taste Memory',
    ...(payload.taste_memory?.preserve_traits?.length > 0
      ? []
      : ['- preserve: none']),
    ...(payload.taste_memory?.avoid_traits?.length > 0
      ? payload.taste_memory.avoid_traits.map((entry) => `- avoid: ${entry}`)
      : ['- avoid: none']),
    ...(payload.taste_memory?.avoid_techniques?.length > 0
      ? payload.taste_memory.avoid_techniques.map((entry) => `- avoid technique: ${entry}`)
      : ['- avoid technique: none']),
    ...(payload.taste_memory?.sourced_truths?.length > 0
      ? payload.taste_memory.sourced_truths.slice(0, 3).map((entry) => `- sourced truth: ${entry}`)
      : ['- sourced truth: none']),
    ...(payload.taste_memory?.capability_gaps?.length > 0
      ? payload.taste_memory.capability_gaps.slice(0, 3).map((entry) => `- capability gap: ${entry}`)
      : ['- capability gap: none']),
    ...(payload.taste_memory?.accepted_tradeoffs?.length > 0
      ? payload.taste_memory.accepted_tradeoffs.map((entry) => `- tradeoff: ${entry}`)
      : ['- tradeoff: none']),
    '',
    '## Strudel Technique Snapshot',
    ...(payload.strudel_techniques?.strengths?.length > 0
      ? payload.strudel_techniques.strengths.slice(0, 4).map((entry) => `- strength: ${entry}`)
      : ['- strength: no strong technique pattern recorded']),
    ...(payload.strudel_techniques?.opportunities?.length > 0
      ? payload.strudel_techniques.opportunities.slice(0, 4).map((entry) => `- improve: ${entry}`)
      : ['- improve: no immediate technique opportunity recorded']),
    '',
    `Baseline run: ${payload.baseline_run_dir ?? 'none'}`,
    `Current run: ${payload.run_dir ?? 'none'}`,
  ].join('\n');
}

function summaryMarkdown(payload) {
  return [
    `# Agent Summary: ${payload.song}`,
    '',
    `What happened: ${payload.summary}`,
    `Decision: ${payload.recommended_next_action}`,
    `Approval required: ${payload.approval_required ? 'yes' : 'no'}`,
    '',
    '## Keep',
    `- ${payload.strongest_trait ?? 'No preserved strength identified yet.'}`,
    ...(payload.taste_memory?.preserve_traits?.length > 0
      ? payload.taste_memory.preserve_traits.slice(0, 3).map((entry) => `- preserve: ${entry}`)
      : []),
    ...(payload.taste_memory?.preserve_techniques?.length > 0
      ? payload.taste_memory.preserve_techniques.slice(0, 3).map((entry) => `- keep technique: ${entry}`)
      : []),
    '',
    '## Fix',
    `- ${payload.top_weakness ?? 'No single top weakness identified.'}`,
    `- ${payload.single_next_move ?? 'No concrete next move recorded.'}`,
    ...(payload.change_summary?.top_metric_changes?.length > 0
      ? payload.change_summary.top_metric_changes.slice(0, 3).map(
          (change) => `- delta: ${change.key} ${change.baseline} -> ${change.current} (${formatDelta(change.delta)})`,
        )
      : ['- delta: no comparable baseline metrics']),
    ...(payload.regression_flags?.length > 0
      ? payload.regression_flags.slice(0, 2).map((flag) => `- regression: ${flag.axis} (${flag.reason})`)
      : []),
    '',
    '## Example Targets',
    ...(payload.taste_memory?.example_targets?.length > 0
      ? payload.taste_memory.example_targets.map((entry) => `- ${entry}`)
      : ['- none attached']),
    '',
    '## Where It Matched',
    ...(payload.example_alignment?.matched_examples?.length > 0
      ? payload.example_alignment.matched_examples.slice(0, 3).map((entry) => `- ${entry}`)
      : ['- no strong example matches yet']),
    '',
    '## Where It Missed',
    ...(payload.example_alignment?.missed_examples?.length > 0
      ? payload.example_alignment.missed_examples.slice(0, 3).map((entry) => `- ${entry}`)
      : ['- no major example misses flagged']),
    '',
    '## Taste Guidance',
    ...(payload.taste_memory?.preserve_traits?.length > 0 ? [] : ['- keep: none recorded']),
    ...(payload.taste_memory?.avoid_traits?.length > 0
      ? payload.taste_memory.avoid_traits.slice(0, 3).map((entry) => `- avoid: ${entry}`)
      : ['- avoid: none recorded']),
    ...(payload.taste_memory?.avoid_techniques?.length > 0
      ? payload.taste_memory.avoid_techniques.slice(0, 3).map((entry) => `- avoid technique: ${entry}`)
      : ['- avoid technique: none recorded']),
    ...(payload.taste_memory?.sourced_truths?.length > 0
      ? payload.taste_memory.sourced_truths.slice(0, 3).map((entry) => `- sourced truth: ${entry}`)
      : ['- sourced truth: none recorded']),
    ...(payload.taste_memory?.capability_gaps?.length > 0
      ? payload.taste_memory.capability_gaps.slice(0, 3).map((entry) => `- capability gap: ${entry}`)
      : ['- capability gap: none recorded']),
    ...(payload.taste_memory?.accepted_tradeoffs?.length > 0
      ? payload.taste_memory.accepted_tradeoffs.slice(0, 2).map((entry) => `- tradeoff: ${entry}`)
      : ['- tradeoff: none recorded']),
    '',
    '## Strudel Technique Snapshot',
    ...(payload.strudel_techniques?.strengths?.length > 0
      ? payload.strudel_techniques.strengths.slice(0, 4).map((entry) => `- strength: ${entry}`)
      : ['- strength: no strong technique pattern recorded']),
    ...(payload.strudel_techniques?.opportunities?.length > 0
      ? payload.strudel_techniques.opportunities.slice(0, 4).map((entry) => `- improve: ${entry}`)
      : ['- improve: no immediate technique opportunity recorded']),
    '',
    `Baseline run: ${payload.baseline_run_dir ?? 'none'}`,
    `Current run: ${payload.run_dir ?? 'none'}`,
  ].join('\n');
}

export function writeVerdictArtifacts(targetDir, payload, options = {}) {
  const verdictPath = join(targetDir, options.verdictFileName ?? 'verdict.json');
  const verdictMarkdownPath = join(targetDir, options.verdictMarkdownFileName ?? 'verdict.md');
  writeFileSync(verdictPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeFileSync(verdictMarkdownPath, `${verdictMarkdown(payload)}\n`);

  let summaryPath = null;
  if (options.writeSummary !== false) {
    summaryPath = join(targetDir, options.summaryFileName ?? 'summary.md');
    writeFileSync(summaryPath, `${summaryMarkdown(payload)}\n`);
  }

  return {
    verdict_path: verdictPath,
    verdict_markdown_path: verdictMarkdownPath,
    summary_path: summaryPath,
  };
}

function buildRegressionFlags(preserveAxes, targetAxes, deltas) {
  const flags = [];

  preserveAxes.forEach((axis) => {
    const delta = deltas[axis.key] ?? 0;
    if (delta <= PRESERVE_AXIS_DELTA_LIMIT) {
      flags.push({
        axis: axis.key,
        type: 'preserve_axis_regression',
        delta,
        reason: `protected axis dropped by ${formatDelta(delta)}`,
      });
    }
  });

  targetAxes.forEach((axis) => {
    const delta = deltas[axis.key] ?? 0;
    if (delta <= TARGET_AXIS_REGRESSION_LIMIT) {
      flags.push({
        axis: axis.key,
        type: 'target_axis_regression',
        delta,
        reason: `target axis moved in the wrong direction by ${formatDelta(delta)}`,
      });
    }
  });

  return flags;
}

export function buildRunVerdict({ slug, runDir, critique, baselineRunDir, baselineCritique }) {
  const safeSlug = sanitizeSlug(slug);
  const currentScores = critique?.scores ?? {};
  const baselineScores = baselineCritique?.scores ?? {};
  const preserveAxes = derivePreserveAxes(baselineScores);
  const targetAxes = deriveTargetAxes(baselineScores);
  const { deltas, ranked } = diffScores(baselineScores, currentScores);
  const weightedBaseline = weightedScore(baselineScores);
  const weightedCurrent = weightedScore(currentScores);
  const weightedDelta = round(weightedCurrent - weightedBaseline);
  const regressionFlags = buildRegressionFlags(preserveAxes, targetAxes, deltas);
  const targetImproved = targetAxes.some((axis) => (deltas[axis.key] ?? 0) >= TARGET_AXIS_IMPROVEMENT_MIN);
  const targetRegressed = targetAxes.some((axis) => (deltas[axis.key] ?? 0) <= TARGET_AXIS_REGRESSION_LIMIT);
  const preserveRegressed = regressionFlags.some((flag) => flag.type === 'preserve_axis_regression');
  const noBaseline = !baselineRunDir || !baselineCritique || baselineRunDir === runDir;

  let verdict = 'flat';
  let recommendedNextAction = 'revise';
  let approvalRequired = false;
  let summary = 'Current run needs another revision pass against the approved baseline.';

  if (critique?.gate === 'blocked') {
    verdict = 'blocked';
    recommendedNextAction = 'escalate_to_human';
    approvalRequired = true;
    summary = critique.summary ?? 'Current run is blocked and needs human review.';
  } else if (noBaseline) {
    verdict = 'baseline';
    recommendedNextAction = isReviewReadyGate(critique?.gate) ? 'review_gate' : 'revise';
    approvalRequired = isReviewReadyGate(critique?.gate);
    summary =
      isReviewReadyGate(critique?.gate)
        ? 'Current run seeded the baseline and is ready for human approval.'
        : 'Current run seeded the baseline but still needs revision before approval.';
  } else if (targetRegressed || preserveRegressed || weightedDelta <= WEIGHTED_REGRESSION_LIMIT) {
    verdict = 'regressed';
    recommendedNextAction = 'escalate_to_human';
    approvalRequired = true;
    summary = 'Current run regressed against the approved baseline and should not replace it automatically.';
  } else if (targetImproved || weightedDelta >= WEIGHTED_IMPROVEMENT_MIN || isReviewReadyGate(critique?.gate)) {
    verdict = 'improved';
    recommendedNextAction = 'review_gate';
    approvalRequired = true;
    summary = 'Current run improved meaningfully over the approved baseline and is ready for human review.';
  } else if (Math.abs(weightedDelta) <= FLAT_DELTA_LIMIT) {
    verdict = 'flat';
    recommendedNextAction = 'revise';
    summary = 'Current run is close to the approved baseline but did not improve enough to justify promotion.';
  }

  const strongestTrait =
    critique?.strongest_trait ??
    (noBaseline
      ? formatAxisLabel(strongestAxis(currentScores))
      : formatAxisLabel(strongestAxis(currentScores)));
  const topWeakness =
    critique?.top_weakness ??
    critique?.music_findings?.[0]?.title ??
    formatAxisLabel(weakestAxis(currentScores));
  const singleNextMove =
    critique?.single_next_move ??
    firstAction(critique?.revision_actions) ??
    (recommendedNextAction === 'review_gate'
      ? 'Listen once and approve or reject with one brief reason.'
      : 'Apply one focused revision pass instead of broad rewrites.');

  return {
    phase: 'verdict',
    version: REVIEW_GATE_VERSION,
    song: safeSlug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    verdict,
    approval_required: approvalRequired,
    recommended_next_action: recommendedNextAction,
    baseline_scores: baselineScores,
    current_scores: currentScores,
    preserve_axes: preserveAxes,
    target_axes: targetAxes,
    regression_flags: regressionFlags,
    change_summary: {
      weighted_baseline: weightedBaseline,
      weighted_current: weightedCurrent,
      weighted_delta: weightedDelta,
      top_metric_changes: ranked.slice(0, 4),
    },
    regression_vs_baseline: {
      baseline_run_dir: baselineRunDir,
      weighted_baseline: weightedBaseline,
      weighted_current: weightedCurrent,
      weighted_delta: weightedDelta,
      deltas,
      preserve_axes: preserveAxes.map((axis) => axis.key),
      target_axes: targetAxes.map((axis) => axis.key),
      regression_flags: regressionFlags,
    },
    taste_memory: {
      preferred_lanes: critique?.taste_memory?.preferred_lanes ?? [],
      avoid_lanes: critique?.taste_memory?.avoid_lanes ?? [],
      current_lane: critique?.taste_memory?.current_lane ?? null,
      current_accent: critique?.taste_memory?.current_accent ?? null,
      lane_notes: critique?.taste_memory?.lane_notes ?? [],
      preserve_traits: critique?.taste_memory?.preserve_traits ?? [],
      preserve_techniques: critique?.taste_memory?.preserve_techniques ?? [],
      avoid_traits: critique?.taste_memory?.avoid_traits ?? [],
      avoid_techniques: critique?.taste_memory?.avoid_techniques ?? [],
      source_material_sources: critique?.taste_memory?.source_material_sources ?? [],
      sourced_truths: critique?.taste_memory?.sourced_truths ?? [],
      musical_inferences: critique?.taste_memory?.musical_inferences ?? [],
      capability_gaps: critique?.taste_memory?.capability_gaps ?? [],
      example_targets: critique?.taste_memory?.example_targets ?? [],
      accepted_tradeoffs: critique?.taste_memory?.accepted_tradeoffs ?? [],
    },
    style_profile: critique?.style_profile ?? null,
    style_profile_usage: critique?.style_profile_usage ?? null,
    strudel_techniques: critique?.strudel_techniques ?? null,
    strongest_trait: strongestTrait,
    top_weakness: topWeakness,
    single_next_move: singleNextMove,
    example_alignment: {
      matched_examples:
        critique?.example_alignment?.comparisons
          ?.filter((entry) => Number(entry.fit ?? 0) >= 0.72)
          .map(
            (entry) =>
              `${entry.metric}: ${entry.value} stays near the target band around ${entry.center} (+/- ${entry.deadband})`,
          ) ?? [],
      missed_examples:
        critique?.example_alignment?.comparisons
          ?.filter((entry) => Number(entry.fit ?? 0) < 0.72)
          .slice(0, 4)
          .map(
            (entry) => `${entry.metric}: ${entry.value} vs target ${entry.center} (+/- ${entry.deadband})`,
          ) ?? [],
    },
    next_changes:
      critique?.revision_actions?.slice(0, 4).map((entry) => entry.action ?? entry).filter(Boolean) ??
      critique?.music_findings?.slice(0, 3).map((entry) => entry.title).filter(Boolean) ??
      [],
    summary,
  };
}

export function baselineComparisonForCandidate({ baselineRunDir, baselineCritique, candidate }) {
  const verdict = buildRunVerdict({
    slug: candidate.song,
    runDir: candidate.run_dir,
    critique: {
      gate: candidate.gate,
      summary: candidate.summary,
      scores: candidate.scores ?? {},
    },
    baselineRunDir,
    baselineCritique,
  });

  return {
    verdict: verdict.verdict,
    weighted_delta: verdict.change_summary.weighted_delta,
    deltas: verdict.regression_vs_baseline.deltas,
    regression_flags: verdict.regression_flags,
    summary: verdict.summary,
    recommended_next_action: verdict.recommended_next_action,
    approval_required: verdict.approval_required,
  };
}

export function appendMemoryHistory(memory, entry) {
  const history = [...(memory.history ?? []), entry].slice(-HISTORY_LIMIT);
  return {
    ...memory,
    history,
  };
}

export function critiqueForRun(runDir) {
  return readCritiqueFromRun(runDir);
}

export function buildApprovalRecord({
  slug,
  runDir,
  baselineRunDir,
  reason = null,
  preserve = [],
  preserveTechniques = [],
  avoid = [],
  avoidTechniques = [],
  tradeoffs = [],
}) {
  const verdict = loadRunVerdict(runDir);
  const critique = critiqueForRun(runDir);
  return {
    at: new Date().toISOString(),
    run_dir: runDir,
    baseline_run_dir: baselineRunDir ?? null,
    decision: 'approved',
    summary: reason ?? verdict?.summary ?? critique?.summary ?? `Approved ${slug}`,
    recommended_next_action: 'keep',
    reason: reason ?? null,
    preserve: preserve.length > 0 ? preserve : critique?.taste_memory?.preserve_traits ?? [],
    preserve_techniques:
      preserveTechniques.length > 0 ? preserveTechniques : critique?.taste_memory?.preserve_techniques ?? [],
    avoid: avoid.length > 0 ? avoid : critique?.taste_memory?.avoid_traits ?? [],
    avoid_techniques: avoidTechniques.length > 0 ? avoidTechniques : critique?.taste_memory?.avoid_techniques ?? [],
    tradeoffs: tradeoffs.length > 0 ? tradeoffs : critique?.taste_memory?.accepted_tradeoffs ?? [],
    applies_to: 'song',
    source_run_dir: runDir,
  };
}

export function buildRejectionRecord({
  slug,
  runDir,
  baselineRunDir,
  reason = null,
  preserve = [],
  preserveTechniques = [],
  avoid = [],
  avoidTechniques = [],
  tradeoffs = [],
}) {
  const verdict = loadRunVerdict(runDir);
  const critique = critiqueForRun(runDir);
  return {
    at: new Date().toISOString(),
    run_dir: runDir,
    baseline_run_dir: baselineRunDir ?? null,
    decision: 'rejected',
    summary: reason ?? verdict?.summary ?? critique?.summary ?? `Rejected ${slug}`,
    recommended_next_action: 'revise',
    reason: reason ?? null,
    preserve,
    preserve_techniques: preserveTechniques,
    avoid,
    avoid_techniques: avoidTechniques,
    tradeoffs,
    applies_to: 'song',
    source_run_dir: runDir,
  };
}
