import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  findLatestRunDir,
  formatRunId,
  listSongRunDirs,
  sanitizeSlug,
  songPaths,
} from './song-contract.mjs';

export const REVIEW_GATE_VERSION = '2026-03-27-v1';

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

export function loadSongMemory(slug) {
  const filePath = songMemoryPath(slug);
  if (!existsSync(filePath)) {
    return null;
  }
  return readJson(filePath);
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
    current_open_issue: approvedCritique?.summary ?? null,
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

  writeFileSync(songMemoryPath(safeSlug), `${JSON.stringify(seeded, null, 2)}\n`);
  return seeded;
}

export function chooseBaselineRun(slug, options = {}) {
  const safeSlug = sanitizeSlug(slug);
  const memory = options.memory ?? ensureSongMemory(safeSlug, options);
  const approved = memory.approved_baseline_run_dir;
  if (approved && approved !== options.excludeRunDir) {
    return approved;
  }

  const fallback = seedBaselineRun(safeSlug, options.excludeRunDir ?? null);
  return fallback ?? approved ?? findLatestRunDir(safeSlug, { requiredFiles: ['critique.json', 'run.json'] });
}

export function updateSongMemory(slug, updater) {
  const safeSlug = sanitizeSlug(slug);
  const current = ensureSongMemory(safeSlug);
  const next = updater(structuredClone(current)) ?? current;
  writeFileSync(songMemoryPath(safeSlug), `${JSON.stringify(next, null, 2)}\n`);
  return next;
}

export function verdictPath(runDir) {
  return runDir ? join(runDir, 'verdict.json') : '';
}

export function summaryPath(runDir) {
  return runDir ? join(runDir, 'summary.md') : '';
}

export function loadRunVerdict(runDir) {
  const filePath = verdictPath(runDir);
  if (!filePath || !existsSync(filePath)) {
    return null;
  }
  return readJson(filePath);
}

function verdictMarkdown(payload) {
  const topChanges =
    payload.change_summary?.top_metric_changes?.length > 0
      ? payload.change_summary.top_metric_changes
      : [];

  return [
    `# Verdict: ${payload.song}`,
    '',
    `Verdict: ${payload.verdict}`,
    `Recommended next action: ${payload.recommended_next_action}`,
    `Approval required: ${payload.approval_required ? 'yes' : 'no'}`,
    `Baseline run: ${payload.baseline_run_dir ?? 'none'}`,
    `Current run: ${payload.run_dir ?? 'none'}`,
    '',
    `Summary: ${payload.summary}`,
    '',
    '## Key Changes',
    ...(topChanges.length > 0
      ? topChanges.map((change) => `- ${change.key}: ${change.baseline} -> ${change.current} (${formatDelta(change.delta)})`)
      : ['- none']),
    '',
    '## Regression Flags',
    ...(payload.regression_flags?.length > 0
      ? payload.regression_flags.map((flag) => `- ${flag.axis}: ${flag.reason}`)
      : ['- none']),
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
    `Baseline run: ${payload.baseline_run_dir ?? 'none'}`,
    `Current run: ${payload.run_dir ?? 'none'}`,
    '',
    '## What changed',
    ...(payload.change_summary?.top_metric_changes?.length > 0
      ? payload.change_summary.top_metric_changes.map(
          (change) => `- ${change.key}: ${change.baseline} -> ${change.current} (${formatDelta(change.delta)})`,
        )
      : ['- no comparable baseline metrics']),
    '',
    '## Next step',
    `- ${payload.recommended_next_action}`,
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

export function buildApprovalRecord({ slug, runDir, baselineRunDir, reason = null }) {
  const verdict = loadRunVerdict(runDir);
  const critique = critiqueForRun(runDir);
  return {
    at: new Date().toISOString(),
    run_dir: runDir,
    baseline_run_dir: baselineRunDir ?? null,
    decision: 'approved',
    summary: reason ?? verdict?.summary ?? critique?.summary ?? `Approved ${slug}`,
    recommended_next_action: 'keep',
  };
}

export function buildRejectionRecord({ slug, runDir, baselineRunDir, reason = null }) {
  const verdict = loadRunVerdict(runDir);
  const critique = critiqueForRun(runDir);
  return {
    at: new Date().toISOString(),
    run_dir: runDir,
    baseline_run_dir: baselineRunDir ?? null,
    decision: 'rejected',
    summary: reason ?? verdict?.summary ?? critique?.summary ?? `Rejected ${slug}`,
    recommended_next_action: 'revise',
  };
}
