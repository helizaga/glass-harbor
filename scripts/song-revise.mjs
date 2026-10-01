import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  buildStyleRolePlan,
  extractStrudelTechniqueProfile,
  OPTIONAL_TONAL_SAMPLE_ROLES,
  OPTIONAL_PITCHED_SAMPLE_ROLES,
  STABLE_SOUND_ROLES,
  buildPromptStyleLens,
  deriveGenerationStrategy,
  parseBrief,
  readText,
  resolveStyleProfile,
  resolveRunDir,
  resolveSongSlug,
  selectExampleProfiles,
  selectReferenceCards,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import {
  buildRunVerdict,
  chooseBaselineRun,
  critiqueForRun,
  derivePreserveAxes,
  deriveTargetAxes,
  ensureSongMemory,
  REVIEW_GATE_VERSION,
  writeVerdictArtifacts,
} from '../lib/review-gates.mjs';

function referenceCardSummaries(critique, brief) {
  if (Array.isArray(critique.retrieval_cards) && critique.retrieval_cards.length > 0) {
    return critique.retrieval_cards.map((card) => ({
      name: card.name,
      path: card.path,
      metadata_path: card.metadata_path ?? card.metadataPath ?? null,
      matched_terms: card.matched_terms ?? card.matchedTerms ?? [],
      score: card.score ?? 0,
    }));
  }

  const promptStyleLens = buildPromptStyleLens(brief);
  const exampleProfiles = selectExampleProfiles(brief);
  return selectReferenceCards(brief, 3, { styleLens: promptStyleLens, exampleProfiles }).map((card) => ({
    name: card.name,
    path: card.path,
    metadata_path: card.metadataPath,
    matched_terms: card.matchedTerms,
    score: card.score,
  }));
}

function buildRevisionPrompt({
  slug,
  brief,
  song,
  critique,
  references,
  runDir,
  verdict,
  baselineRunDir,
  generationStrategy,
  techniqueProfile,
  styleProfile,
  styleProfileUsage,
  styleRolePlan,
}) {
  const actions = critique.revision_actions ?? [];
  const scoreLines = Object.entries(critique.scores ?? {}).map(([key, value]) => `- ${key}: ${value}`);
  const referenceLines =
    references.length > 0
      ? references.map((card) => `- ${card.name}: ${card.path}`)
      : ['- none'];

  return [
    `# Revision Task: ${brief.title ?? slug}`,
    '',
    'Revise the canonical song file in place using the latest critique artifacts.',
    '',
    '## Target Files',
    `- brief: ${song.briefPath}`,
    `- song: ${song.songPath}`,
    '',
    '## Run Artifacts',
    `- run: ${join(runDir, 'run.json')}`,
    `- analysis: ${join(runDir, 'analysis.json')}`,
    `- critique: ${join(runDir, 'critique.json')}`,
    `- verdict: ${join(runDir, 'verdict.json')}`,
    `- human summary: ${join(runDir, 'revision.md')}`,
    '',
    '## Required Constraints',
    '- keep the song directly pasteable into https://strudel.cc/ after `glass-harbor song serve`',
    '- preserve top metadata comments: @title, @genre, @bpm, @details, @sections',
    '- keep `samples(\'http://localhost:5432\')` as the runtime sample source',
    '- do not add repo-specific wrappers or imports to the song file',
    `- keep the required core sampled roles limited to: ${STABLE_SOUND_ROLES.join(', ')}`,
    `- optional tonal sample families may be used only when they materially improve hook quality: ${OPTIONAL_TONAL_SAMPLE_ROLES.join(', ')}`,
    `- prefer pitch-aware tonal sample families when writing note-driven hooks or harmony: ${OPTIONAL_PITCHED_SAMPLE_ROLES.join(', ')}`,
    '- keep tonal parts readable and modular with named layer constants',
    '- revise the canonical song file, not a private vendor-specific copy',
    '',
    '## Critique Summary',
    `- gate: ${critique.gate ?? 'unknown'}`,
    `- blocker class: ${critique.blocker_class ?? 'none'}`,
    `- provisional: ${critique.provisional ? 'yes' : 'no'}`,
    `- summary: ${critique.summary ?? 'No summary available.'}`,
    `- baseline run: ${baselineRunDir ?? 'none'}`,
    `- verdict: ${verdict.verdict}`,
    `- recommended next action: ${verdict.recommended_next_action}`,
    `- approval required: ${verdict.approval_required ? 'yes' : 'no'}`,
    `- generation strategy: ${generationStrategy?.mode ?? 'single_draft'}`,
    `- style lane: ${styleProfile?.label ?? 'none'}`,
    `- accent: ${styleProfile?.accent ?? 'none'}`,
    `- lane fit score: ${styleProfileUsage?.score ?? 'n/a'}`,
    '',
    '## Scores',
    ...(scoreLines.length > 0 ? scoreLines : ['- none']),
    '',
    '## Protected Strengths',
    ...(verdict.preserve_axes?.length > 0
      ? verdict.preserve_axes.map((axis) => `- keep ${axis.key} near ${axis.value}; do not sacrifice it casually`)
      : ['- none']),
    ...(verdict.taste_memory?.preserve_traits?.length > 0
      ? ['', '## Human Preserve Traits', ...verdict.taste_memory.preserve_traits.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.avoid_traits?.length > 0
      ? ['', '## Human Avoid Traits', ...verdict.taste_memory.avoid_traits.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.accepted_tradeoffs?.length > 0
      ? ['', '## Accepted Tradeoffs', ...verdict.taste_memory.accepted_tradeoffs.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.source_material_sources?.length > 0
      ? ['', '## Source Material Sources', ...verdict.taste_memory.source_material_sources.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.sourced_truths?.length > 0
      ? ['', '## Sourced Truths', ...verdict.taste_memory.sourced_truths.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.musical_inferences?.length > 0
      ? ['', '## Musical Inferences', ...verdict.taste_memory.musical_inferences.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.capability_gaps?.length > 0
      ? ['', '## Capability Gaps', ...verdict.taste_memory.capability_gaps.map((entry) => `- ${entry}`)]
      : []),
    ...(verdict.taste_memory?.example_targets?.length > 0
      ? ['', '## Example Targets', ...verdict.taste_memory.example_targets.map((entry) => `- ${entry}`)]
      : []),
    ...(critique.prompt_style_lens?.references?.length > 0
      ? [
          '',
          '## Prompt Reference Lens',
          ...critique.prompt_style_lens.references.map((entry) => `- ${entry.label}`),
          ...(critique.prompt_style_lens.preserveTraits?.length > 0
            ? ['', '### Keep From Prompt Lens', ...critique.prompt_style_lens.preserveTraits.map((entry) => `- ${entry}`)]
            : []),
          ...(critique.prompt_style_lens.avoidTraits?.length > 0
            ? ['', '### Do Not Drift Toward', ...critique.prompt_style_lens.avoidTraits.map((entry) => `- ${entry}`)]
            : []),
        ]
      : []),
    '',
    '## Improvement Targets',
    ...(verdict.target_axes?.length > 0
      ? verdict.target_axes.map((axis) => `- improve ${axis.key} from ${axis.value}`)
      : ['- none']),
    ...(generationStrategy?.mode === 'two_candidate_hidden'
      ? [
          '',
          '## Hidden Branching Guidance',
          '- If the next draft still feels uncertain, branch two candidates internally and keep only the better one.',
          ...generationStrategy.candidate_profiles.map((entry) => `- ${entry.label}: ${entry.guidance}`),
        ]
      : []),
    ...(styleProfile
      ? [
          '',
          '## Style Lane Profile',
          `- lane: ${styleProfile.label}`,
          ...(styleProfile.accent ? [`- accent: ${styleProfile.accent}`] : []),
          ...(styleProfile.arrangement_archetypes?.length > 0
            ? [`- archetypes: ${styleProfile.arrangement_archetypes.join(', ')}`]
            : []),
          ...(styleProfile.preferred_roles?.length > 0
            ? [`- prefer roles: ${styleProfile.preferred_roles.join(', ')}`]
            : []),
          ...(styleProfile.preferred_techniques?.length > 0
            ? [`- prefer techniques: ${styleProfile.preferred_techniques.join(', ')}`]
            : []),
          ...(styleProfile.anti_patterns?.length > 0
            ? [`- avoid: ${styleProfile.anti_patterns.join(', ')}`]
            : []),
          ...(styleProfileUsage?.warnings?.length > 0
            ? [`- lane warnings: ${styleProfileUsage.warnings.join(' | ')}`]
            : []),
        ]
      : []),
    ...(styleRolePlan
      ? [
          '',
          '## Style Role Plan',
          ...(styleRolePlan.dominant_roles?.length > 0
            ? [`- dominant roles: ${styleRolePlan.dominant_roles.join(', ')}`]
            : []),
          ...(styleRolePlan.support_roles?.length > 0
            ? [`- support roles: ${styleRolePlan.support_roles.join(', ')}`]
            : []),
          ...(styleRolePlan.primary_hook_roles?.length > 0
            ? [`- primary hook roles: ${styleRolePlan.primary_hook_roles.join(', ')}`]
            : []),
          `- max hook roles: ${styleRolePlan.max_hook_roles}`,
          ...(styleRolePlan.prune_first_roles?.length > 0
            ? [`- prune first if the lane drifts: ${styleRolePlan.prune_first_roles.join(', ')}`]
            : []),
          ...(styleRolePlan.suggested_pruned_roles?.length > 0
            ? [`- suggested prune now: ${styleRolePlan.suggested_pruned_roles.join(', ')}`]
            : []),
          ...(styleRolePlan.guidance?.length > 0
            ? styleRolePlan.guidance.map((entry) => `- ${entry}`)
            : []),
        ]
      : []),
    '',
    '## Strudel Technique Snapshot',
    ...(techniqueProfile?.strengths?.length > 0
      ? techniqueProfile.strengths.map((entry) => `- keep: ${entry}`)
      : ['- keep: readable named layers and section assembly']),
    ...(techniqueProfile?.opportunities?.length > 0
      ? ['', '## Strudel Technique Opportunities', ...techniqueProfile.opportunities.map((entry) => `- ${entry}`)]
      : []),
    '',
    '## Revision Actions',
    ...(actions.length > 0
      ? actions.map((action) => `- ${action.action}`)
      : ['- No specific revision actions were provided. Keep the current arrangement unless you find an obvious readability fix.']),
    '',
    '## Reference Cards',
    ...referenceLines,
    '',
    '## What To Do',
    '- Update only the canonical song file unless the brief itself is clearly out of sync.',
    '- Make the smallest set of changes that addresses the critique cleanly.',
    '- Preserve the emotional intent and structure unless the critique explicitly points to a structural problem.',
    '- If the critique already passes, make no musical changes and explain that the current version should stand.',
    '',
    '## After Editing',
    `- rerun: glass-harbor song loop ${slug} --max-iters 1 --json`,
    '- compare the new critique summary and scores against this run before doing another pass.',
  ].join('\n');
}

export async function handleSongRevise({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song revise <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const runDir = resolveRunDir(argv, slug) ?? '';
  const critiquePath = runDir ? join(runDir, 'critique.json') : '';
  if (!runDir || !existsSync(critiquePath)) {
    throw new CommandError(`No critique found for ${slug}. Run glass-harbor song critique ${slug} first.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'critique_missing',
    });
  }

  const song = songPaths(slug);
  if (!existsSync(song.briefPath) || !existsSync(song.songPath)) {
    throw new CommandError(`Missing brief or song file for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'song_missing',
      details: song,
    });
  }

  const brief = parseBrief(readText(song.briefPath));
  const currentSongCode = readText(song.songPath);
  const currentValidation = validateSongCode(currentSongCode);
  const exampleProfiles = selectExampleProfiles(brief);
  const memory = ensureSongMemory(slug, { excludeRunDir: runDir });
  const styleLens = buildPromptStyleLens(brief);
  const styleProfile = resolveStyleProfile(brief, { tasteProfile: memory.taste_profile ?? null, styleLens, exampleProfiles });
  const generationStrategy = deriveGenerationStrategy(brief, { exampleProfiles, styleLens, styleProfile });
  const styleRolePlan = buildStyleRolePlan({
    styleProfile,
    dependencies: currentValidation.dependencies,
    strudelTechniques: currentValidation.strudelTechniques,
  });
  let critique;
  try {
    critique = JSON.parse(readFileSync(critiquePath, 'utf8'));
  } catch (error) {
    throw new CommandError(`Failed to parse critique.json at ${critiquePath}: ${error.message}`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'critique_parse_error',
    });
  }
  const references = referenceCardSummaries(critique, brief);
  const techniqueProfile = extractStrudelTechniqueProfile(currentSongCode);
  const baselineRunDir = chooseBaselineRun(slug, { memory, excludeRunDir: runDir });
  const baselineCritique = critiqueForRun(baselineRunDir);
  const verdict =
    critique.gate === 'blocked' || baselineCritique || baselineRunDir === runDir
      ? buildRunVerdict({
          slug,
          runDir,
          critique,
          baselineRunDir,
          baselineCritique,
        })
      : {
          phase: 'verdict',
          version: REVIEW_GATE_VERSION,
          song: slug,
          run_dir: runDir,
          baseline_run_dir: baselineRunDir,
          verdict: 'flat',
          approval_required: false,
          recommended_next_action: 'revise',
          baseline_scores: {},
          current_scores: critique.scores ?? {},
          preserve_axes: derivePreserveAxes(critique.scores ?? {}),
          target_axes: deriveTargetAxes(critique.scores ?? {}),
          regression_flags: [],
          change_summary: {
            weighted_baseline: 0,
            weighted_current: 0,
            weighted_delta: 0,
            top_metric_changes: [],
          },
          regression_vs_baseline: {
            baseline_run_dir: baselineRunDir,
            weighted_baseline: 0,
            weighted_current: 0,
            weighted_delta: 0,
            deltas: {},
            preserve_axes: [],
            target_axes: [],
            regression_flags: [],
          },
          summary: critique.summary ?? 'Current run needs revision.',
        };
  const verdictArtifacts = writeVerdictArtifacts(runDir, verdict);
  const promptPath = join(runDir, 'revision-prompt.md');
  const requestPath = join(runDir, 'revision-request.json');
  const revisionActions = critique.revision_actions ?? [];
  const status = critique.gate === 'pass' || revisionActions.length === 0 ? 'noop' : 'ready';

  const requestPayload = {
    phase: 'revise',
    status,
    song: slug,
    run_dir: runDir,
    target: {
      brief_path: song.briefPath,
      song_path: song.songPath,
      edit_mode: 'in_place',
    },
    source: {
      brief_path: song.briefPath,
      song_path: song.songPath,
      run_path: join(runDir, 'run.json'),
      analysis_path: join(runDir, 'analysis.json'),
      critique_path: critiquePath,
      revision_summary_path: join(runDir, 'revision.md'),
    },
    critique: {
      gate: critique.gate ?? 'unknown',
      blocker_class: critique.blocker_class ?? 'none',
      provisional: critique.provisional ?? false,
      summary: critique.summary ?? null,
      scores: critique.scores ?? {},
      revision_actions: revisionActions,
    },
    baseline_run_dir: baselineRunDir,
    baseline_scores: verdict.baseline_scores,
    taste_memory: verdict.taste_memory ?? memory.taste_profile ?? null,
    style_profile: styleProfile,
    style_profile_usage: verdict.style_profile_usage ?? null,
    style_role_plan: styleRolePlan,
    generation_strategy: generationStrategy,
    style_lens: critique.prompt_style_lens ?? null,
    prompt_reference_alignment: critique.prompt_reference_alignment ?? null,
    preserve_axes: verdict.preserve_axes,
    target_axes: verdict.target_axes,
    strudel_techniques: techniqueProfile,
    approval_required: verdict.approval_required,
    recommended_next_action: verdict.recommended_next_action,
    constraints: {
      paste_target: 'https://strudel.cc/',
      sample_server_url: 'http://localhost:5432',
      required_metadata: ['title', 'genre', 'bpm', 'details', 'sections'],
      stable_sample_roles: STABLE_SOUND_ROLES,
      optional_tonal_sample_roles: OPTIONAL_TONAL_SAMPLE_ROLES,
      optional_pitched_sample_roles: OPTIONAL_PITCHED_SAMPLE_ROLES,
      must_edit_in_place: true,
    },
    references,
    outputs: {
      prompt_path: promptPath,
      request_path: requestPath,
      verdict_path: verdictArtifacts.verdict_path,
      verdict_markdown_path: verdictArtifacts.verdict_markdown_path,
      summary_path: verdictArtifacts.summary_path,
    },
  };

  const prompt = buildRevisionPrompt({
    slug,
    brief,
    song,
    critique,
    references,
    runDir,
    verdict,
    baselineRunDir,
    generationStrategy,
    techniqueProfile,
    styleProfile,
    styleProfileUsage: verdict.style_profile_usage ?? null,
    styleRolePlan,
  });
  writeFileSync(requestPath, `${JSON.stringify(requestPayload, null, 2)}\n`);
  writeFileSync(promptPath, `${prompt}\n`);

  return {
    phase: 'song:revise',
    status,
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    request_path: requestPath,
    prompt_path: promptPath,
    style_role_plan: requestPayload.style_role_plan,
    verdict_path: verdictArtifacts.verdict_path,
    verdict_markdown_path: verdictArtifacts.verdict_markdown_path,
    summary_path: verdictArtifacts.summary_path,
    recommended_next_action: verdict.recommended_next_action,
    approval_required: verdict.approval_required,
    preserve_axes: verdict.preserve_axes,
    target_axes: verdict.target_axes,
    revision_actions: revisionActions,
    message:
      status === 'noop'
        ? `Revision package written for ${slug}; critique already passes, so no changes are currently recommended.`
        : `Prepared a revision package for ${slug} at ${requestPath}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongRevise, process.argv.slice(2)));
}
