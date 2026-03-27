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

const SCORE_WEIGHTS = {
  groove_strength: 0.22,
  section_contrast: 0.18,
  low_end_cleanliness: 0.16,
  style_fit: 0.14,
  transition_impact: 0.12,
  melodic_memorability: 0.1,
  top_end_harshness: 0.05,
  structure_clarity: 0.03,
};

function round(value) {
  return Number(value.toFixed(3));
}

function parseCompareSlugs(argv) {
  const normalized = [];
  let skipNext = false;

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (skipNext) {
      skipNext = false;
      continue;
    }
    if (value === '--song' || value === '-s' || value === '--run') {
      skipNext = true;
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

function weightedScore(scores = {}) {
  return round(
    Object.entries(SCORE_WEIGHTS).reduce((sum, [key, weight]) => sum + (Number(scores[key] ?? 0) * weight), 0),
  );
}

function strongestAxis(scores = {}) {
  const entries = Object.entries(scores);
  if (entries.length === 0) {
    return null;
  }

  const [key, value] = entries.sort((left, right) => Number(right[1]) - Number(left[1]))[0];
  return { key, value: round(Number(value)) };
}

function lowestAxis(scores = {}) {
  const entries = Object.entries(scores);
  if (entries.length === 0) {
    return null;
  }

  const [key, value] = entries.sort((left, right) => Number(left[1]) - Number(right[1]))[0];
  return { key, value: round(Number(value)) };
}

function candidateSummary(candidate) {
  if (candidate.gate === 'blocked' || candidate.gate === 'missing') {
    return `${candidate.song} is blocked by ${candidate.primary_liability ?? 'runtime issues'}.`;
  }
  if (candidate.gate === 'pass') {
    return `${candidate.song} is the cleanest current option and already clears the critique gate.`;
  }
  return `${candidate.song} is currently the strongest revise candidate with better ${candidate.strongest_axis?.key?.replaceAll('_', ' ') ?? 'overall balance'}.`;
}

function buildComparisonMarkdown({ sourceSong, winner, candidates, comparisonPath }) {
  return [
    `# Song Comparison: ${sourceSong}`,
    '',
    `Winner: ${winner.song}`,
    '',
    winner.summary,
    '',
    '## Ranked Candidates',
    ...candidates.map((candidate, index) => `- #${index + 1} ${candidate.song} | ${candidate.rank_bucket_label} | score ${candidate.weighted_score}\n  summary: ${candidate.summary}\n  top: groove ${candidate.scores?.groove_strength ?? 0}, contrast ${candidate.scores?.section_contrast ?? 0}, low-end ${candidate.scores?.low_end_cleanliness ?? 0}\n  watch: ${candidate.primary_liability ?? 'none'}`),
    '',
    '## Winner Actions',
    ...(winner.revision_actions.length > 0 ? winner.revision_actions.map((action) => `- ${action}`) : ['- none']),
    '',
    `JSON artifact: ${join(comparisonPath, 'comparison.json')}`,
  ].join('\n');
}

function rankBucket(candidate) {
  if (candidate.gate === 'pass' && !candidate.provisional) {
    return { rank: 7, label: 'pass' };
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
    (left.music_findings?.length ?? 0) - (right.music_findings?.length ?? 0) ||
    (left.revision_actions?.length ?? 0) - (right.revision_actions?.length ?? 0) ||
    left.song.localeCompare(right.song)
  );
}

function loadCandidate(slug) {
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
      strongest_axis: null,
      weakest_axis: null,
      primary_liability: 'critique_missing',
      summary: `No critique artifact found for ${slug}.`,
      revision_actions: [`Run glass-harbor song loop ${slug} --max-iters 1 --json before comparing variants.`],
      critique_path: critiquePath || null,
      run_path: runPath || null,
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
  const weakest = lowestAxis(critique.scores);
  const primaryLiability =
    critique.runtime_blockers?.[0]?.code ??
    critique.music_findings?.[0]?.title ??
    weakest?.key ??
    null;

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
    summary: critique.summary ?? candidateSummary({ song: slug, gate: critique.gate ?? 'missing', strongest_axis: strongest, primary_liability: primaryLiability }),
    revision_actions: (critique.revision_actions ?? []).map((action) => action.action ?? action).filter(Boolean),
    critique_path: critiquePath,
    run_path: runPath,
    ranking,
  };
}

export async function handleSongCompare({ argv, positionals }) {
  const positionalSlugs = positionals.map((value) => sanitizeSlug(value)).filter(Boolean);
  const sourceSong = positionalSlugs[0] || resolveSongSlug(argv);
  if (!sourceSong) {
    throw new CommandError('Usage: glass-harbor song compare <slug> [<other-slug> ...]', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const explicitSlugs = parseCompareSlugs(argv);
  const candidateSlugs =
    explicitSlugs.length > 1 ? explicitSlugs : loadVariantsFromManifest(sourceSong);

  if (candidateSlugs.length === 0) {
    throw new CommandError(
      `No comparison candidates found for ${sourceSong}. Pass multiple slugs or scaffold variants first with glass-harbor song variants ${sourceSong}.`,
      {
        exitCode: EXIT_CODES.USAGE,
        code: 'comparison_candidates_missing',
      },
    );
  }

  const candidates = [...new Set(candidateSlugs)].map(loadCandidate).sort(compareCandidates);
  const winner = candidates[0];
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

  const payload = {
    phase: 'song:compare',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    readiness,
    formula_version: '2026-03-27-v1',
    source_song: sourceSong,
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
      summary:
        rankedWinner.gate === 'blocked' || rankedWinner.gate === 'missing'
          ? `${rankedWinner.song} only leads because the other candidates are even less review-ready.`
          : `${rankedWinner.song} is the current best direction because it wins the strongest review bucket and has the highest weighted musical score in that bucket.`,
      strongest_axis: rankedWinner.strongest_axis,
      primary_liability: rankedWinner.primary_liability,
      revision_actions: rankedWinner.revision_actions,
    },
    candidates: rankedCandidates,
    message:
      rankedWinner.gate === 'blocked' || rankedWinner.gate === 'missing'
        ? `Comparison completed for ${sourceSong}, but the leading candidate is still blocked.`
        : `Comparison completed for ${sourceSong}; ${rankedWinner.song} is the current best direction.`,
  };

  const comparisonJsonPath = join(comparisonDir, 'comparison.json');
  const comparisonMarkdownPath = join(comparisonDir, 'comparison.md');
  writeFileSync(comparisonJsonPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeFileSync(
    comparisonMarkdownPath,
    `${buildComparisonMarkdown({
      sourceSong,
      winner: { ...payload.winner, summary: payload.winner.summary, revision_actions: rankedWinner.revision_actions },
      candidates: rankedCandidates,
      comparisonPath: comparisonDir,
    })}\n`,
  );

  return {
    ...payload,
    comparison_json_path: comparisonJsonPath,
    comparison_markdown_path: comparisonMarkdownPath,
    messages: [
      payload.message,
      comparisonJsonPath,
      comparisonMarkdownPath,
    ],
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongCompare, process.argv.slice(2)));
}
