import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { formatRunId, resolveSongSlug, runsRoot } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { writeVerdictArtifacts } from '../lib/review-gates.mjs';
import { handleSongCompare } from './song-compare.mjs';
import { handleSongLoop } from './song-loop.mjs';
import { handleSongVariants } from './song-variants.mjs';

function parseIntegerFlag(argv, flag, fallback) {
  const index = argv.indexOf(flag);
  if (index === -1 || !argv[index + 1]) {
    return fallback;
  }

  const value = Number.parseInt(argv[index + 1], 10);
  return Number.isFinite(value) && value > 0 ? value : Number.NaN;
}

function chooseNextAction(compareResult, loopBySlug) {
  const winner = compareResult.winner;
  const winnerLoop = loopBySlug.get(winner.song) ?? null;

  if (compareResult.recommended_next_action === 'review_gate') {
    return {
      type: 'review_gate',
      target_slug: winner.song,
      reason: compareResult.winner_reason,
    };
  }

  if (compareResult.recommended_next_action === 'abandon') {
    return {
      type: 'abandon_branch',
      target_slug: winner.song,
      reason: compareResult.winner_reason,
    };
  }

  if (compareResult.recommended_next_action === 'revise') {
    return {
      type: 'revise_winner',
      target_slug: winner.song,
      reason: compareResult.winner_reason,
    };
  }

  if (compareResult.readiness === 'blocked') {
    return {
      type: 'fix_blocker',
      target_slug: winner.song,
      reason: 'all compared candidates are blocked or missing review artifacts',
    };
  }

  if (compareResult.readiness === 'partial') {
    return {
      type: 'rerun',
      target_slug: null,
      reason: 'at least one candidate is missing a full review pass',
    };
  }

  if (winner.gate === 'pass' && !winner.provisional) {
    return {
      type: 'promote',
      target_slug: winner.song,
      reason: 'winner already clears the critique gate without provisional warnings',
    };
  }

  if (winner.gate === 'blocked') {
    return {
      type: 'fix_blocker',
      target_slug: winner.song,
      reason: winner.primary_liability ?? 'winner is blocked by runtime or contract issues',
    };
  }

  if (winnerLoop?.status === 'failed') {
    return {
      type: 'rerun',
      target_slug: winner.song,
      reason: 'winner loop did not complete cleanly',
    };
  }

  return {
    type: 'revise_winner',
    target_slug: winner.song,
    reason: winner.primary_liability ?? 'winner is the strongest candidate but still needs revision',
  };
}

function buildExploreMarkdown(payload) {
  return [
    `# Song Explore: ${payload.source_song}`,
    '',
    `Generated at: ${payload.generated_at}`,
    `Readiness: ${payload.readiness}`,
    `Baseline run: ${payload.baseline_run_dir ?? 'none'}`,
    `Recommended next action: ${payload.recommended_next_action}`,
    `Approval required: ${payload.approval_required ? 'yes' : 'no'}`,
    '',
    '## Variants',
    ...payload.variants.map(
      (variant) =>
        `- ${variant.slug}: loop_status=${variant.loop_status}, gate=${variant.gate}, weighted_score=${variant.weighted_score ?? 'n/a'}, regression=${variant.regression_vs_baseline?.verdict ?? 'n/a'}, run_dir=${variant.run_dir ?? 'none'}`,
    ),
    '',
    '## Compare',
    `- winner: ${payload.compare.winner_slug}`,
    `- winner run: ${payload.compare.winner_run_dir ?? 'none'}`,
    `- decision basis: ${payload.compare.decision_basis}`,
    `- winner reason: ${payload.compare.winner_reason}`,
    '',
    '## Next Action',
    `- ${payload.next_action.type}: ${payload.next_action.target_slug ?? 'global'}`,
    `- reason: ${payload.next_action.reason}`,
  ].join('\n');
}

export async function handleSongExplore({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song explore <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const count = parseIntegerFlag(argv, '--count', 3);
  const maxIters = parseIntegerFlag(argv, '--max-iters', 1);
  if (!Number.isFinite(count) || !Number.isFinite(maxIters)) {
    throw new CommandError('Count and max-iters must both be positive integers.', {
      exitCode: EXIT_CODES.USAGE,
      code: 'invalid_explore_args',
    });
  }

  const force = argv.includes('--force');
  const variantsResult = await handleSongVariants({
    argv: ['--song', slug, '--count', `${count}`, ...(force ? ['--force'] : [])],
  });

  const loopResults = [
    await handleSongLoop({
      argv: ['--song', slug, '--max-iters', `${maxIters}`],
    }),
  ];
  for (const variant of variantsResult.variants) {
    const loopResult = await handleSongLoop({
      argv: ['--song', variant.slug, '--max-iters', `${maxIters}`],
    });
    loopResults.push(loopResult);
  }

  const candidateSlugs = [slug, ...variantsResult.variants.map((variant) => variant.slug)];
  const compareResult = await handleSongCompare({
    argv: candidateSlugs,
    positionals: candidateSlugs,
  });

  const loopBySlug = new Map(loopResults.map((result) => [result.song, result]));
  const explorationDir = join(runsRoot, slug, 'explorations', formatRunId());
  mkdirSync(explorationDir, { recursive: true });

  const variants = compareResult.candidates
    .filter((candidate) => candidate.song !== slug)
    .map((candidate) => {
      const loopResult = loopBySlug.get(candidate.song);
      return {
        slug: candidate.song,
        loop_status: loopResult?.status ?? 'missing',
        run_dir: candidate.run_dir ?? loopResult?.run_dir ?? null,
        baseline_run_dir: candidate.baseline_run_dir ?? compareResult.baseline_run_dir ?? null,
        gate: candidate.gate,
        provisional: candidate.provisional,
        weighted_score: candidate.gate === 'missing' ? null : candidate.weighted_score,
        blocker_class: candidate.blocker_class,
        regression_vs_baseline: candidate.regression_vs_baseline ?? null,
        recommended_next_action: candidate.recommended_next_action ?? null,
      };
    });

  const payload = {
    phase: 'song:explore',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    source_song: slug,
    generated_at: new Date().toISOString(),
    readiness: compareResult.readiness,
    formula_version: compareResult.formula_version,
    run_dir: explorationDir,
    baseline_run_dir: compareResult.baseline_run_dir ?? null,
    variants,
    compare: {
      winner_slug: compareResult.winner.song,
      winner_run_dir: compareResult.winner.run_dir,
      comparison_json_path: compareResult.comparison_json_path,
      comparison_markdown_path: compareResult.comparison_markdown_path,
      winner_reason: compareResult.winner_reason,
      loser_reasons: compareResult.loser_reasons,
      regression_vs_baseline: compareResult.regression_vs_baseline,
      decision_basis: 'tier_then_weighted_score',
    },
    next_action: chooseNextAction(compareResult, loopBySlug),
    recommended_next_action: compareResult.recommended_next_action,
    approval_required: compareResult.approval_required,
    regression_vs_baseline: compareResult.regression_vs_baseline,
  };

  const exploreJsonPath = join(explorationDir, 'explore.json');
  const exploreMarkdownPath = join(explorationDir, 'explore.md');
  const winnerRegression = compareResult.winner.regression_vs_baseline ?? {};
  const verdictArtifacts = writeVerdictArtifacts(explorationDir, {
    ...winnerRegression,
    phase: 'explore_verdict',
    version: compareResult.formula_version,
    song: slug,
    run_dir: compareResult.winner.run_dir,
    baseline_run_dir: compareResult.baseline_run_dir,
    verdict: winnerRegression.verdict ?? 'flat',
    approval_required: compareResult.approval_required,
    recommended_next_action: compareResult.recommended_next_action,
    baseline_scores: {},
    current_scores: compareResult.winner.scores ?? {},
    preserve_axes: [],
    target_axes: [],
    change_summary: {
      weighted_baseline: 0,
      weighted_current: compareResult.winner.weighted_score ?? 0,
      weighted_delta: winnerRegression.weighted_delta ?? 0,
      top_metric_changes: [],
    },
    summary: compareResult.winner_reason,
  });
  writeFileSync(exploreJsonPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeFileSync(exploreMarkdownPath, `${buildExploreMarkdown(payload)}\n`);

  return {
    ...payload,
    exploration_dir: explorationDir,
    explore_json_path: exploreJsonPath,
    explore_markdown_path: exploreMarkdownPath,
    verdict_path: verdictArtifacts.verdict_path,
    verdict_markdown_path: verdictArtifacts.verdict_markdown_path,
    summary_path: verdictArtifacts.summary_path,
    messages: [
      `Exploration completed for ${slug}; winner: ${compareResult.winner.song}`,
      exploreJsonPath,
      exploreMarkdownPath,
    ],
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongExplore, process.argv.slice(2)));
}
