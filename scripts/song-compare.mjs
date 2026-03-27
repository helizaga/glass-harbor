import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  findLatestRunDir,
  formatRunId,
  resolveSongSlug,
  runsRoot,
  sanitizeSlug,
  songPaths,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  baselineComparisonForCandidate,
  chooseBaselineRun,
  critiqueForRun,
  ensureSongMemory,
  strongestAxis,
  weakestAxis,
  weightedScore,
  writeVerdictArtifacts,
  REVIEW_GATE_VERSION,
} from '../lib/review-gates.mjs';

const FORMULA_VERSION = REVIEW_GATE_VERSION;

function parseCompareSlugs(argv) {
  const normalized = [];

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--song' || value === '-s') {
      const slug = sanitizeSlug(argv[index + 1]);
      if (slug) {
        normalized.push(slug);
      }
      index += 1;
      continue;
    }
    if (value === '--run') {
      index += 1;
      continue;
    }
    if (value.startsWith('-')) {
      continue;
    }
    normalized.push(sanitizeSlug(value));
  }

  return [...new Set(normalized.filter(Boolean))];
}

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, 'utf8'));
}

function loadVariantsFromManifest(sourceSlug) {
  const manifestPath = join(songPaths(sourceSlug).dir, 'variants.json');
  if (!existsSync(manifestPath)) {
    return [];
  }

  const manifest = readJson(manifestPath);
  const variantSlugs = Array.isArray(manifest.variants)
    ? manifest.variants.map((variant) => sanitizeSlug(variant.slug))
    : [];
  return [...new Set([sanitizeSlug(sourceSlug), ...variantSlugs].filter(Boolean))];
}

function candidateSummary(candidate) {
  if (candidate.gate === 'blocked' || candidate.gate === 'missing') {
    return `${candidate.song} is blocked by ${candidate.primary_liability ?? 'runtime issues'}.`;
  }
  if (candidate.gate === 'pass') {
    return `${candidate.song} is the cleanest current option and already clears the critique gate.`;
  }
  if (candidate.gate === 'review_gate') {
    return `${candidate.song} is promising and ready for human review, but the evidence is still mixed.`;
  }
  return `${candidate.song} is currently the strongest revise candidate with better ${candidate.strongest_axis?.key?.replaceAll('_', ' ') ?? 'overall balance'}.`;
}

function buildComparisonMarkdown({ sourceSong, winner, candidates, comparisonPath, baselineRunDir, verdict }) {
  return [
    `# Song Comparison: ${sourceSong}`,
    '',
    `Winner: ${winner.song}`,
    `Baseline run: ${baselineRunDir ?? 'none'}`,
    `Recommended next action: ${verdict.recommended_next_action}`,
    `Approval required: ${verdict.approval_required ? 'yes' : 'no'}`,
    '',
    winner.summary,
    '',
    '## Ranked Candidates',
    ...candidates.map(
      (candidate, index) =>
        `- #${index + 1} ${candidate.song} | ${candidate.rank_bucket_label} | score ${candidate.weighted_score}\n  summary: ${candidate.summary}\n  regression: ${candidate.regression_vs_baseline.verdict}\n  watch: ${candidate.primary_liability ?? 'none'}`,
    ),
    '',
    '## Next Step',
    `- ${verdict.recommended_next_action}`,
    '',
    `JSON artifact: ${join(comparisonPath, 'comparison.json')}`,
  ].join('\n');
}

function rankBucket(candidate) {
  if (candidate.gate === 'pass' && !candidate.provisional) {
    return { rank: 7, label: 'pass' };
  }
  if (candidate.gate === 'review_gate' && !candidate.provisional) {
    return { rank: 6, label: 'review_gate' };
  }
  if (candidate.gate === 'review_gate' && candidate.provisional) {
    return { rank: 6, label: 'review_gate*' };
  }
  if (candidate.gate === 'pass' && candidate.provisional) {
    return { rank: 6, label: 'pass*' };
  }
  if (candidate.gate === 'revise' && !candidate.provisional) {
    return { rank: 5, label: 'revise' };
  }
  if (candidate.gate === 'revise' && candidate.provisional) {
    return { rank: 4, label: 'revise*' };
  }
  if (candidate.gate === 'blocked' && candidate.blocker_class === 'analysis') {
    return { rank: 3, label: 'blocked:analysis' };
  }
  if (candidate.gate === 'blocked' && candidate.blocker_class === 'contract') {
    return { rank: 2, label: 'blocked:contract' };
  }
  if (candidate.gate === 'blocked' && candidate.blocker_class === 'runtime') {
    return { rank: 1, label: 'blocked:runtime' };
  }
  return { rank: 0, label: 'missing' };
}

function compareCandidates(left, right) {
  const leftBucket = rankBucket(left);
  const rightBucket = rankBucket(right);

  return (
    rightBucket.rank - leftBucket.rank ||
    right.weighted_score - left.weighted_score ||
    right.regression_vs_baseline.weighted_delta - left.regression_vs_baseline.weighted_delta ||
    (left.music_findings?.length ?? 0) - (right.music_findings?.length ?? 0) ||
    (left.revision_actions?.length ?? 0) - (right.revision_actions?.length ?? 0) ||
    left.song.localeCompare(right.song)
  );
}

function loadCandidate(slug, baselineRunDir, baselineCritique) {
  const runDir = findLatestRunDir(slug, { requiredFiles: ['critique.json', 'run.json'] });
  const critiquePath = runDir ? join(runDir, 'critique.json') : '';
  const runPath = runDir ? join(runDir, 'run.json') : '';
  const critiqueMissing = !runDir || !existsSync(critiquePath);

  if (critiqueMissing) {
    return {
      song: slug,
      run_dir: runDir,
      gate: 'missing',
      blocker_class: 'analysis',
      provisional: true,
      weighted_score: 0,
      comparison_score: 0,
      scores: {},
      runtime_blockers: [
        {
          code: 'critique_missing',
          message: `No critique artifact found for ${slug}. Run glass-harbor song loop ${slug} --max-iters 1 --json first.`,
        },
      ],
      music_findings: [],
      strongest_axis: null,
      weakest_axis: null,
      primary_liability: 'critique_missing',
      summary: `No critique artifact found for ${slug}.`,
      revision_actions: [`Run glass-harbor song loop ${slug} --max-iters 1 --json before comparing variants.`],
      critique_path: critiquePath || null,
      run_path: runPath || null,
      regression_vs_baseline: {
        verdict: 'missing',
        weighted_delta: 0,
        deltas: {},
        regression_flags: [],
        summary: `No critique artifact found for ${slug}.`,
        recommended_next_action: 'revise',
        approval_required: false,
      },
      ranking: {
        bucket_label: 'missing',
        weighted_score: 0,
        music_findings_count: 0,
        revision_actions_count: 1,
        sort_key: [0, 0, 0, -1, slug],
      },
    };
  }

  const critique = readJson(critiquePath);
  const score = weightedScore(critique.scores);
  const strongest = strongestAxis(critique.scores);
  const weakest = weakestAxis(critique.scores);
  const primaryLiability =
    critique.runtime_blockers?.[0]?.code ??
    critique.music_findings?.[0]?.title ??
    weakest?.key ??
    null;

  const regressionVsBaseline = baselineComparisonForCandidate({
    baselineRunDir,
    baselineCritique,
    candidate: {
      song: slug,
      run_dir: runDir,
      gate: critique.gate ?? 'missing',
      summary: critique.summary ?? null,
      scores: critique.scores ?? {},
    },
  });

  const ranking = {
    bucket_label: rankBucket({
      gate: critique.gate ?? 'missing',
      blocker_class: critique.blocker_class ?? 'none',
      provisional: Boolean(critique.provisional),
    }).label,
    weighted_score: score,
    music_findings_count: (critique.music_findings ?? []).length,
    revision_actions_count: (critique.revision_actions ?? []).length,
    sort_key: [
      rankBucket({
        gate: critique.gate ?? 'missing',
        blocker_class: critique.blocker_class ?? 'none',
        provisional: Boolean(critique.provisional),
      }).rank,
      score,
      regressionVsBaseline.weighted_delta,
      -((critique.music_findings ?? []).length),
      -((critique.revision_actions ?? []).length),
      slug,
    ],
  };

  return {
    song: slug,
    run_dir: runDir,
    gate: critique.gate ?? 'missing',
    blocker_class: critique.blocker_class ?? 'none',
    provisional: Boolean(critique.provisional),
    weighted_score: score,
    comparison_score: score,
    scores: critique.scores ?? {},
    runtime_blockers: critique.runtime_blockers ?? [],
    music_findings: critique.music_findings ?? [],
    strongest_axis: strongest,
    weakest_axis: weakest,
    primary_liability: primaryLiability,
    summary:
      critique.summary ??
      candidateSummary({
        song: slug,
        gate: critique.gate ?? 'missing',
        strongest_axis: strongest,
        primary_liability: primaryLiability,
      }),
    revision_actions: (critique.revision_actions ?? []).map((action) => action.action ?? action).filter(Boolean),
    critique_path: critiquePath,
    run_path: runPath,
    regression_vs_baseline: regressionVsBaseline,
    ranking,
  };
}

function buildComparisonDecision({ sourceSong, baselineRunDir, baselineCritique, rankedCandidates }) {
  const winner = rankedCandidates[0];
  const loserReasons = Object.fromEntries(
    rankedCandidates
      .filter((candidate) => candidate.song !== winner.song)
      .map((candidate) => [
        candidate.song,
        candidate.gate === 'missing' || candidate.gate === 'blocked'
          ? candidate.primary_liability ?? 'not review-ready'
          : candidate.regression_vs_baseline.verdict === 'improved'
            ? 'still scored lower than the winner after weighting'
            : candidate.regression_vs_baseline.summary,
      ]),
  );

  let recommendedNextAction = 'revise';
  let approvalRequired = false;
  let winnerReason = `${winner.song} leads on weighted score within the strongest critique bucket.`;

  if (winner.gate === 'missing' || winner.gate === 'blocked') {
    recommendedNextAction = 'revise';
    winnerReason = `${winner.song} only leads because the other candidates are even less review-ready.`;
  } else if (winner.regression_vs_baseline.verdict === 'improved') {
    recommendedNextAction = 'review_gate';
    approvalRequired = true;
    winnerReason = `${winner.song} beats the approved baseline and is ready for human review.`;
  } else if (winner.song === sourceSong) {
    recommendedNextAction = 'revise';
    winnerReason = `${winner.song} remains the best direction, but no candidate beat the approved baseline.`;
  } else {
    recommendedNextAction = 'abandon';
    winnerReason = `${winner.song} wins among the candidates, but it does not beat the approved baseline.`;
  }

  const verdict = {
    phase: 'comparison_verdict',
    version: REVIEW_GATE_VERSION,
    song: sourceSong,
    run_dir: winner.run_dir,
    baseline_run_dir: baselineRunDir,
    verdict:
      winner.regression_vs_baseline.verdict === 'improved'
        ? 'improved'
        : winner.gate === 'missing' || winner.gate === 'blocked'
          ? 'blocked'
          : recommendedNextAction === 'abandon'
            ? 'regressed'
            : 'flat',
    approval_required: approvalRequired,
    recommended_next_action: recommendedNextAction,
    baseline_scores: baselineCritique?.scores ?? {},
    current_scores: winner.scores ?? {},
    preserve_axes: [],
    target_axes: [],
    regression_flags: winner.regression_vs_baseline.regression_flags ?? [],
    change_summary: {
      weighted_baseline: weightedScore(baselineCritique?.scores ?? {}),
      weighted_current: winner.weighted_score ?? 0,
      weighted_delta: winner.regression_vs_baseline.weighted_delta ?? 0,
      top_metric_changes: [],
    },
    regression_vs_baseline: {
      baseline_run_dir: baselineRunDir,
      winner_song: winner.song,
      verdict: winner.regression_vs_baseline.verdict,
      weighted_delta: winner.regression_vs_baseline.weighted_delta ?? 0,
      deltas: winner.regression_vs_baseline.deltas ?? {},
      regression_flags: winner.regression_vs_baseline.regression_flags ?? [],
    },
    summary: winnerReason,
  };

  return {
    winnerReason,
    loserReasons,
    verdict,
    recommendedNextAction,
    approvalRequired,
  };
}

export async function handleSongCompare({ argv, positionals }) {
  const positionalSlugs = positionals
    .filter((value, index) => value !== '--song' && value !== '-s' && !(index > 0 && (positionals[index - 1] === '--song' || positionals[index - 1] === '-s')))
    .map((value) => sanitizeSlug(value))
    .filter(Boolean);
  const sourceSong = resolveSongSlug(argv) || positionalSlugs[0];
  if (!sourceSong) {
    throw new CommandError('Usage: glass-harbor song compare <slug> [<other-slug> ...]', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const explicitSlugs = parseCompareSlugs(argv);
  const explicitCandidates = explicitSlugs.filter((slug) => slug !== sourceSong);
  const candidateSlugs =
    explicitCandidates.length > 0 ? [sourceSong, ...explicitCandidates] : loadVariantsFromManifest(sourceSong);

  if (candidateSlugs.length === 0) {
    throw new CommandError(
      `No comparison candidates found for ${sourceSong}. Pass multiple slugs or scaffold variants first with glass-harbor song variants ${sourceSong}.`,
      {
        exitCode: EXIT_CODES.USAGE,
        code: 'comparison_candidates_missing',
      },
    );
  }

  const memory = ensureSongMemory(sourceSong);
  const baselineRunDir = chooseBaselineRun(sourceSong, { memory });
  const baselineCritique = critiqueForRun(baselineRunDir);
  const candidates = [...new Set(candidateSlugs)]
    .map((slug) => loadCandidate(slug, baselineRunDir, baselineCritique))
    .sort(compareCandidates);
  const rankedCandidates = candidates.map((candidate) => {
    const bucket = rankBucket(candidate);
    return {
      ...candidate,
      rank_bucket: bucket.rank,
      rank_bucket_label: bucket.label,
    };
  });
  const rankedWinner = rankedCandidates[0];
  const comparisonDir = join(runsRoot, sourceSong, 'comparisons', formatRunId());
  mkdirSync(comparisonDir, { recursive: true });
  const missingCandidates = rankedCandidates.filter((candidate) => candidate.gate === 'missing').map((candidate) => candidate.song);
  const blockedCandidates = rankedCandidates.filter((candidate) => candidate.gate === 'blocked').map((candidate) => candidate.song);
  const readiness =
    missingCandidates.length > 0 || blockedCandidates.length > 0
      ? rankedCandidates.every((candidate) => candidate.gate === 'missing' || candidate.gate === 'blocked')
        ? 'blocked'
        : 'partial'
      : 'ready';

  const decision = buildComparisonDecision({
    sourceSong,
    baselineRunDir,
    baselineCritique,
    rankedCandidates,
  });

  const payload = {
    phase: 'song:compare',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    readiness,
    formula_version: FORMULA_VERSION,
    source_song: sourceSong,
    run_dir: comparisonDir,
    baseline_run_dir: baselineRunDir,
    compared_songs: rankedCandidates.map((candidate) => candidate.song),
    candidate_count: rankedCandidates.length,
    missing_candidates: missingCandidates,
    blocked_candidates: blockedCandidates,
    comparison_dir: comparisonDir,
    winner: {
      song: rankedWinner.song,
      run_dir: rankedWinner.run_dir,
      gate: rankedWinner.gate,
      rank_bucket: rankedWinner.rank_bucket,
      rank_bucket_label: rankedWinner.rank_bucket_label,
      comparison_score: rankedWinner.comparison_score,
      weighted_score: rankedWinner.weighted_score,
      summary: decision.winnerReason,
      strongest_axis: rankedWinner.strongest_axis,
      primary_liability: rankedWinner.primary_liability,
      revision_actions: rankedWinner.revision_actions,
      regression_vs_baseline: rankedWinner.regression_vs_baseline,
    },
    winner_reason: decision.winnerReason,
    loser_reasons: decision.loserReasons,
    candidates: rankedCandidates,
    regression_vs_baseline: rankedWinner.regression_vs_baseline,
    recommended_next_action: decision.recommendedNextAction,
    approval_required: decision.approvalRequired,
    message:
      rankedWinner.gate === 'blocked' || rankedWinner.gate === 'missing'
        ? `Comparison completed for ${sourceSong}, but the leading candidate is still blocked.`
        : `Comparison completed for ${sourceSong}; ${rankedWinner.song} is the current best direction.`,
  };

  const verdictArtifacts = writeVerdictArtifacts(comparisonDir, decision.verdict);
  const comparisonJsonPath = join(comparisonDir, 'comparison.json');
  const comparisonMarkdownPath = join(comparisonDir, 'comparison.md');
  writeFileSync(comparisonJsonPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeFileSync(
    comparisonMarkdownPath,
    `${buildComparisonMarkdown({
      sourceSong,
      winner: { ...payload.winner, summary: payload.winner.summary },
      candidates: rankedCandidates,
      comparisonPath: comparisonDir,
      baselineRunDir,
      verdict: decision.verdict,
    })}\n`,
  );

  return {
    ...payload,
    comparison_json_path: comparisonJsonPath,
    comparison_markdown_path: comparisonMarkdownPath,
    verdict_path: verdictArtifacts.verdict_path,
    verdict_markdown_path: verdictArtifacts.verdict_markdown_path,
    summary_path: verdictArtifacts.summary_path,
    messages: [payload.message, comparisonJsonPath, comparisonMarkdownPath],
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongCompare, process.argv.slice(2)));
}
