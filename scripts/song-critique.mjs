import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  buildStyleRolePlan,
  buildPromptStyleLens,
  deriveGenerationStrategy,
  evaluateStyleProfileUsage,
  extractNamedLayers,
  normalizeRuntimeErrors,
  parseBrief,
  parseListItems,
  readText,
  resolveStyleProfile,
  resolveRunDir,
  resolveSongSlug,
  selectExampleProfiles,
  selectReferenceCards,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { average, confidenceLabel, round, clamp, scoreCalibrationAlignment } from '../lib/analysis-helpers.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { buildRunVerdict, chooseBaselineRun, critiqueForRun, diffScores, ensureSongMemory, writeVerdictArtifacts } from '../lib/review-gates.mjs';
import { reviewAudioWithProvider } from './song-review-provider.mjs';

const FINDING_TEMPLATES_VERSION = '2026-03-27-v4';
const CRITIC_VERSION = '2026-03-27-v2';
const CALIBRATION_VERSION = '2026-03-27-v2';

function parseJsonFile(filePath, fallback = null) {
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch (error) {
    if (fallback !== null) {
      console.warn(`Failed to parse ${filePath}: ${error.message}`);
      return fallback;
    }
    throw new CommandError(`Failed to parse required JSON artifact at ${filePath}: ${error.message}`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'analysis_parse_error',
    });
  }
}

function summarizeReferenceAlignment(referenceCards, embeddingAlignment) {
  const similarityByName = new Map(
    (embeddingAlignment.reference_scores ?? []).map((entry) => [entry.name, Number(entry.similarity ?? 0)]),
  );
  return referenceCards.map((card) => ({
    name: card.name,
    retrieval_score: card.score,
    matched_terms: card.matchedTerms,
    embedding_similarity: round(similarityByName.get(card.name) ?? Math.min(1, (card.score ?? 0) / 24)),
  }));
}

function buildStyleAlignment({
  brief,
  referenceCards,
  embeddingAlignment,
  analysis,
  validation,
  exampleAlignment,
  promptReferenceAlignment,
}) {
  const bpm = Number(validation.metadata.bpm ?? analysis.declared_bpm ?? 0);
  const bpmFit = bpm > 0 ? clamp(1 - Math.abs(bpm - 122) / 14) : 0.5;
  const retrievalFit = referenceCards.length > 0 ? clamp((referenceCards[0].score ?? 0) / 24) : 0;
  const grooveFit = clamp((analysis.rhythm?.groove_continuity ?? 0) * 0.7 + (analysis.rhythm?.syncopation_proxy ?? 0) * 0.3);
  const harmonicFit = clamp((analysis.tonal?.harmonic_stability ?? 0) * 0.6 + (1 - clamp(analysis.tonal?.chord_change_proxy ?? 0)) * 0.4);
  const embeddingFit = Number(embeddingAlignment.overall ?? 0);
  const exampleFit = Number(exampleAlignment?.overall ?? 0);
  const promptFit = Number(promptReferenceAlignment?.overall ?? 0);
  const overall =
    exampleAlignment?.targets?.length > 0
      ? round(
          exampleFit * 0.34 +
            promptFit * 0.18 +
            embeddingFit * 0.1 +
            retrievalFit * 0.14 +
            grooveFit * 0.14 +
            harmonicFit * 0.06 +
            bpmFit * 0.04,
        )
      : round(
          promptFit * 0.3 +
            embeddingFit * 0.3 +
            retrievalFit * 0.16 +
            grooveFit * 0.12 +
            harmonicFit * 0.07 +
            bpmFit * 0.05,
        );

  return {
    provider: embeddingAlignment.provider ?? 'none',
    status: embeddingAlignment.status ?? 'fallback',
    overall,
    bpm_fit: round(bpmFit),
    retrieval_fit: round(retrievalFit),
    groove_fit: round(grooveFit),
    harmonic_fit: round(harmonicFit),
    embedding_fit: round(embeddingFit),
    example_fit: round(exampleFit),
    prompt_reference_fit: round(promptFit),
    top_reference: embeddingAlignment.top_reference ?? null,
    brief_title: brief.title ?? null,
    confidence_notes: [
      ...(embeddingAlignment.confidence_notes ?? []),
      ...((exampleAlignment?.notes ?? []).filter(Boolean) ?? []),
      ...((promptReferenceAlignment?.notes ?? []).filter(Boolean) ?? []),
    ],
  };
}

function pickTransition(analysis, candidates) {
  const transitions = analysis.section_transitions ?? [];
  for (const [from, to] of candidates) {
    const match = transitions.find((entry) => entry.from === from && entry.to === to);
    if (match) {
      return match;
    }
  }
  return transitions[0] ?? null;
}

function makeFinding({ title, severity = 'medium', evidence, counterevidence, revisionActions, signalCount, maxSignals = 4 }) {
  const confidenceScore = round(clamp(signalCount / maxSignals));
  return {
    title,
    severity,
    evidence,
    counterevidence,
    confidence: confidenceLabel(confidenceScore),
    confidence_score: confidenceScore,
    revision_actions: revisionActions,
  };
}

function findSectionByRole(analysis, role, fallbackNames = []) {
  const map = analysis.section_role_map ?? {};
  const sections = analysis.sections ?? {};
  const match = Object.entries(map).find(([, mappedRole]) => mappedRole === role)?.[0];
  if (match && sections[match]) {
    return sections[match];
  }

  for (const name of fallbackNames) {
    if (sections[name]) {
      return sections[name];
    }
  }

  return analysis.metrics ?? {};
}

function buildExampleAlignment({ analysis, exampleProfiles }) {
  const alignment = scoreCalibrationAlignment({
    analysis,
    calibrationProfile: analysis.calibration_profile,
    metricReliability: analysis.metric_reliability,
  });

  return {
    overall: alignment.overall,
    targets: exampleProfiles.map((entry) => ({
      slug: entry.slug,
      title: entry.profile?.title ?? entry.slug,
      preserve_traits: entry.profile?.preserve_traits ?? [],
      avoid_traits: entry.profile?.avoid_traits ?? [],
    })),
    comparisons: alignment.comparisons,
    notes:
      exampleProfiles.length > 0
        ? []
        : ['No attached example profiles were available; style alignment falls back to generic references.'],
  };
}

function buildPromptReferenceAlignment({ analysis, promptStyleLens, layerNames = [], validation, dropTransition, dropSection }) {
  if (!promptStyleLens) {
    return {
      overall: 0.5,
      comparisons: [],
      notes: [],
      references: [],
      inferred_lanes: [],
    };
  }

  const promptLayers = {
    vocal_presence:
      layerNames.some((name) => /(vocal|hook|robot|mist|chop)/i.test(name)) ||
      (validation?.dependencies?.sampleRoles ?? []).includes('vocal_chop'),
    percussion_presence:
      layerNames.some((name) => /(perc|march|clap|hat)/i.test(name)) ||
      (validation?.dependencies?.sampleRoles ?? []).includes('perc_top'),
    cinematic_presence:
      layerNames.some((name) => /(pad|air|shimmer|riser|impact)/i.test(name)),
  };

  const comparisons = [];
  const bpmPreference = promptStyleLens.bpmPreference;
  if (bpmPreference?.center) {
    const fit = clamp(
      1 -
        Math.abs((analysis.rhythm?.estimated_tempo ?? 0) - bpmPreference.center) /
          Math.max((bpmPreference.deadband ?? 4) * 2, 1),
    );
    comparisons.push({
      metric: 'tempo_lane_fit',
      value: round(analysis.rhythm?.estimated_tempo ?? 0),
      target: `${bpmPreference.center} +/- ${bpmPreference.deadband ?? 4}`,
      fit: round(fit),
      note: `Prompt references imply a tempo lane near ${bpmPreference.center} BPM.`,
    });
  }

  if ((promptStyleLens.targetBiases?.percussion_focus ?? 0) >= 0.5) {
    comparisons.push({
      metric: 'percussion_motion',
      value: round((analysis.rhythm?.groove_continuity ?? 0) * 0.6 + (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) * 0.4),
      target: '>= 0.68 with clear percussion presence',
      fit: round(
        clamp(
          ((analysis.rhythm?.groove_continuity ?? 0) * 0.6 + (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) * 0.4) /
            0.68,
        ) * (promptLayers.percussion_presence ? 1 : 0.7),
      ),
      note: 'Prompt references ask for percussion-led movement rather than a plain loop.',
    });
  }

  if ((promptStyleLens.targetBiases?.vocal_focus ?? 0) >= 0.5) {
    comparisons.push({
      metric: 'vocal_fragment_identity',
      value: promptLayers.vocal_presence ? 1 : 0,
      target: 'vocal fragment or hook punctuation present',
      fit: promptLayers.vocal_presence ? 1 : 0.25,
      note: 'Prompt references ask for vocal-fragment energy or human punctuation.',
    });
  }

  if ((promptStyleLens.targetBiases?.warmth_focus ?? 0) >= 0.5) {
    const warmthFit = clamp(
      (clamp((analysis.timbre?.low_mid_energy_ratio ?? 0) / 0.38) * 0.55) +
        (1 - clamp(Math.abs((analysis.timbre?.spectral_centroid ?? 0) - 1950) / 1400)) * 0.45,
    );
    comparisons.push({
      metric: 'warmth_balance',
      value: round(warmthFit),
      target: 'warm low mids with restrained brightness',
      fit: round(warmthFit),
      note: 'Prompt references ask for warmth and nostalgic glow rather than brittle brightness.',
    });
  }

  if ((promptStyleLens.targetBiases?.return_focus ?? 0) >= 0.5) {
    const returnFit = clamp(((dropTransition?.boundary_strength ?? 0) * 0.6) + ((dropSection?.rms ?? 0) * 2.2 * 0.4));
    comparisons.push({
      metric: 'return_bloom',
      value: round(returnFit),
      target: 'clear breakdown-to-return bloom',
      fit: round(returnFit),
      note: 'Prompt references ask for a cinematic return that feels earned and wide.',
    });
  }

  const overall = comparisons.length > 0 ? round(average(comparisons.map((entry) => entry.fit))) : 0.5;
  return {
    overall,
    comparisons,
    notes:
      comparisons.length > 0
        ? []
        : ['Prompt references were present, but the temporary style lens did not produce strong metric checks.'],
    references: promptStyleLens.references.map((entry) => entry.label),
    inferred_lanes: promptStyleLens.inferredLanes,
    preserve_traits: promptStyleLens.preserveTraits,
    avoid_traits: promptStyleLens.avoidTraits,
  };
}

function describeStrength(scores = {}, styleAlignment, promptReferenceAlignment) {
  const entries = Object.entries(scores)
    .map(([key, value]) => [key, Number(value ?? 0)])
    .sort((left, right) => right[1] - left[1]);
  const [key, value] = entries[0] ?? [];
  if (!key) {
    return null;
  }

  const labels = {
    structure_clarity: 'The structure reads clearly from section to section.',
    groove_strength: 'The groove already has a convincing pocket.',
    section_contrast: 'The section contrast is strong enough to carry the arrangement.',
    transition_impact: 'The transitions already land with good impact.',
    melodic_memorability: 'The hook and melodic identity are already sticky.',
    low_end_cleanliness: 'The low end is already clean and disciplined.',
    top_end_harshness: 'The top end stays controlled without turning brittle.',
    style_fit: 'The song already fits its intended lane well.',
  };

  const base = labels[key] ?? `The strongest current axis is ${key}.`;
  if (key === 'style_fit' && promptReferenceAlignment?.overall >= 0.72) {
    return `${base} Prompt-reference fit is ${promptReferenceAlignment.overall}.`;
  }
  if (key === 'style_fit' && styleAlignment?.overall >= 0.72) {
    return `${base} Overall style alignment is ${styleAlignment.overall}.`;
  }
  return `${base} (${round(value)})`;
}

export async function handleSongCritique({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song critique <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const runDir = resolveRunDir(argv, slug) ?? '';
  const analysisPath = join(runDir, 'analysis.json');
  if (!runDir || !existsSync(analysisPath)) {
    throw new CommandError(`No analysis found for ${slug}. Run glass-harbor song analyze ${slug} first.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'analysis_missing',
    });
  }

  const analysis = parseJsonFile(analysisPath);
  const song = songPaths(slug);
  const brief = parseBrief(readText(song.briefPath));
  const memory = ensureSongMemory(slug, { excludeRunDir: runDir });
  const promptStyleLens = analysis.prompt_style_lens ?? buildPromptStyleLens(brief);
  const code = readText(song.songPath);
  const validation = validateSongCode(code);
  const strudelTechniques = validation.strudelTechniques ?? null;
  const runInfo = existsSync(join(runDir, 'run.json'))
    ? parseJsonFile(join(runDir, 'run.json'), { runtime_blockers: [], console_errors: [] })
    : { runtime_blockers: [], console_errors: [] };
  const providerReview = await reviewAudioWithProvider({
    song: slug,
    runDir,
    analysis,
    brief,
  });

  const exampleProfiles = selectExampleProfiles(brief);
  const styleProfile = resolveStyleProfile(brief, {
    tasteProfile: memory.taste_profile ?? null,
    styleLens: promptStyleLens,
    exampleProfiles,
  });
  const styleProfileUsage = evaluateStyleProfileUsage({
    dependencies: validation.dependencies,
    strudelTechniques,
    styleProfile,
  });
  const styleRolePlan = buildStyleRolePlan({
    styleProfile,
    dependencies: validation.dependencies,
    strudelTechniques,
  });
  const generationStrategy =
    analysis.generation_strategy ??
    deriveGenerationStrategy(brief, { exampleProfiles, styleLens: promptStyleLens, styleProfile });
  const referenceCards = selectReferenceCards(brief, 3, { styleLens: promptStyleLens, exampleProfiles });
  const embeddingAlignment = analysis.embedding_alignment ?? {
    provider: 'none',
    status: 'fallback',
      overall: 0,
    reference_scores: [],
    confidence_notes: ['Embedding alignment was not computed during analysis.'],
  };
  const exampleAlignment = buildExampleAlignment({
    analysis,
    exampleProfiles,
  });
  const layerNames = extractNamedLayers(code);
  const melodicLayers = layerNames.filter((name) => /(lead|pluck|arp|pad|hook|robot)/i.test(name));
  const transitionLayers = layerNames.filter((name) => /(riser|impact|shimmer|air|vocal)/i.test(name));
  const sections = analysis.sections ?? {};
  const grooveSection = findSectionByRole(analysis, 'groove', ['groove', 'pulse']);
  const breakdownSection = findSectionByRole(analysis, 'breath', ['breakdown', 'breath']);
  const dropSection = findSectionByRole(analysis, 'return', ['drop', 'bloom', 'release', 'second-drop', 'afterglow']);
  const dropTransition = pickTransition(analysis, [
    ['breakdown', 'drop'],
    ['breath', 'drop'],
    ['breath', 'bloom'],
    ['lift', 'drop'],
    ['lift', 'bloom'],
    ['groove', 'drop'],
  ]);
  const promptReferenceAlignmentRefined = buildPromptReferenceAlignment({
    analysis,
    promptStyleLens,
    layerNames,
    validation,
    dropTransition,
    dropSection,
  });
  const styleAlignment = buildStyleAlignment({
    brief,
    referenceCards,
    embeddingAlignment,
    analysis,
    validation,
    exampleAlignment,
    promptReferenceAlignment: promptReferenceAlignmentRefined,
  });
  const referenceAlignment = summarizeReferenceAlignment(referenceCards, embeddingAlignment);
  const runtimeErrors =
    runInfo.runtime_blockers?.length > 0
      ? runInfo.runtime_blockers
      : normalizeRuntimeErrors(runInfo.console_errors, runInfo.dependencies ?? validation.dependencies);
  const silentRender = (analysis.metrics?.rms ?? 0) === 0 && (analysis.metrics?.peak ?? 0) === 0;

  const structureClarity = clamp(
    (validation.errors.length === 0 ? 0.45 : 0) +
      (analysis.structure?.boundary_strength_proxy ?? 0) * 0.25 +
      (analysis.structure?.recurrence_strength ?? 0) * 0.15 +
      (analysis.structure?.repetition_variation_balance ?? 0) * 0.15,
  );
  const grooveStrength = clamp(
    (analysis.rhythm?.groove_continuity ?? 0) * 0.45 +
      (analysis.rhythm?.onset_to_beat_alignment ?? 0) * 0.2 +
      (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) * 0.15 +
      (1 - Math.abs((analysis.rhythm?.syncopation_proxy ?? 0) - 0.38) / 0.38) * 0.2,
  );
  const sectionContrast = clamp(
    Math.abs((dropSection.rms ?? 0) - (breakdownSection.rms ?? 0)) * 6 +
      Math.abs((dropSection.onset_density ?? 0) - (breakdownSection.onset_density ?? 0)) / 3 +
      Math.abs(((dropSection.timbre?.spectral_centroid ?? 0) - (breakdownSection.timbre?.spectral_centroid ?? 0)) / 5000),
  );
  const transitionImpact = clamp(
    (dropTransition?.boundary_strength ?? 0) * 0.65 + Math.min(1, transitionLayers.length / 5) * 0.35,
  );
  const melodicMemorability = clamp(
    Math.min(1, melodicLayers.length / 4) * 0.45 +
      (analysis.structure?.repetition_variation_balance ?? 0) * 0.15 +
      styleAlignment.retrieval_fit * 0.2 +
      styleAlignment.embedding_fit * 0.2,
  );
  const lowEndCleanliness = clamp(
    1 -
      Math.abs(((analysis.timbre?.sub_energy_ratio ?? 0) + (analysis.timbre?.bass_energy_ratio ?? 0)) - 0.58) / 0.35 -
      Math.max(0, 0.55 - (analysis.rhythm?.inter_beat_loudness_consistency ?? 0)) * 0.25,
  );
  const topEndHarshness = clamp(
    1 -
      Math.max(0, (analysis.timbre?.high_band_energy_ratio ?? 0) - 0.2) * 2.5 -
      Math.max(0, (analysis.timbre?.spectral_flatness ?? 0) - 0.22) * 1.2,
  );
  const styleFit = clamp(styleAlignment.overall * 0.8 + promptReferenceAlignmentRefined.overall * 0.2);

  const scores = {
    structure_clarity: round(structureClarity),
    groove_strength: round(grooveStrength),
    section_contrast: round(sectionContrast),
    transition_impact: round(transitionImpact),
    melodic_memorability: round(melodicMemorability),
    low_end_cleanliness: round(lowEndCleanliness),
    top_end_harshness: round(topEndHarshness),
    style_fit: round(styleFit),
  };

  const baselineRunDir = chooseBaselineRun(slug, { memory, excludeRunDir: runDir });
  const baselineCritique = critiqueForRun(baselineRunDir);
  const { deltas: baselineDeltas, ranked: rankedBaselineDeltas } = diffScores(
    baselineCritique?.scores ?? {},
    scores,
  );
  const tasteMemory = {
    example_targets: exampleProfiles.map((entry) => entry.slug),
    preferred_lanes: [
      ...new Set([
        ...(memory.taste_profile?.preferred_lanes ?? []),
        ...(styleProfile?.label ? [styleProfile.label] : []),
      ]),
    ],
    avoid_lanes: [...new Set(memory.taste_profile?.avoid_lanes ?? [])],
    current_lane: styleProfile?.label ?? memory.taste_profile?.current_lane ?? null,
    current_accent: styleProfile?.accent ?? memory.taste_profile?.current_accent ?? null,
    lane_notes: [
      ...new Set([
        ...(memory.taste_profile?.lane_notes ?? []),
        ...((styleProfile?.anti_patterns ?? []).map((entry) => `avoid: ${entry}`)),
        ...((styleProfileUsage?.warnings ?? []).map((entry) => `lane warning: ${entry}`)),
      ]),
    ],
    preserve_traits: [
      ...new Set([
        ...(memory.taste_profile?.preserve_traits ?? []),
        ...exampleProfiles.flatMap((entry) => entry.profile?.preserve_traits ?? []),
      ]),
    ],
    preserve_techniques: [...new Set(memory.taste_profile?.preserve_techniques ?? [])],
    avoid_traits: [
      ...new Set([
        ...(memory.taste_profile?.avoid_traits ?? []),
        ...exampleProfiles.flatMap((entry) => entry.profile?.avoid_traits ?? []),
      ]),
    ],
    avoid_techniques: [...new Set(memory.taste_profile?.avoid_techniques ?? [])],
    source_material_sources: [
      ...new Set([
        ...(memory.taste_profile?.source_material_sources ?? []),
        ...parseListItems(brief['source-material-sources']),
      ]),
    ],
    sourced_truths: [
      ...new Set([
        ...(memory.taste_profile?.sourced_truths ?? []),
        ...parseListItems(brief['sourced-truths']),
      ]),
    ],
    musical_inferences: [
      ...new Set([
        ...(memory.taste_profile?.musical_inferences ?? []),
        ...parseListItems(brief['musical-inferences']),
      ]),
    ],
    capability_gaps: [
      ...new Set([
        ...(memory.taste_profile?.capability_gaps ?? []),
        ...parseListItems(brief['capability-gaps']),
      ]),
    ],
    accepted_tradeoffs: memory.taste_profile?.accepted_tradeoffs ?? [],
    rejected_patterns: memory.taste_profile?.rejected_patterns ?? [],
    human_notes: memory.taste_profile?.human_notes ?? [],
  };

  const runtimeBlockers = [];
  if (silentRender || runtimeErrors.length > 0 || analysis.status === 'blocked') {
    runtimeBlockers.push({
      code: 'offline_render_unresolved',
      surface: 'render_harness',
      title: 'Offline render is unresolved',
      severity: 'high',
      evidence: [
        silentRender ? 'Rendered WAVs are silent, so audio metrics are not yet meaningful.' : 'Render completed with runtime errors.',
        ...runtimeErrors.slice(0, 3).map((error) => error.message ?? `${error}`),
      ],
      counterevidence: [],
      confidence: 'high',
      confidence_score: 1,
      revision_actions: [
        'Make sure the offline render harness loads the same sample and synth environment as the interactive Strudel path.',
        'Treat musical critique as provisional until the render path resolves missing sound errors.',
        'Use the local debug app or Strudel web for ear checks while fixing the offline render environment.',
      ],
    });
  }

  const musicFindings = [];
  const uncertaintyNotes = [];
  const triggeredChecks = [];
  const suppressedChecks = [];
  const reliabilityAdjustments = [];

  const signalReliability = analysis.signal_reliability ?? { overall: 0.5, level: 'medium', notes: [] };
  const metricReliability = analysis.metric_reliability ?? {};
  const calibrationComparisons = exampleAlignment.comparisons ?? [];
  const calibrationByMetric = Object.fromEntries(calibrationComparisons.map((entry) => [entry.metric, entry]));
  const exampleTargets = exampleAlignment.targets ?? [];

  if (signalReliability.level === 'low') {
    reliabilityAdjustments.push({
      source: 'signal_reliability',
      level: signalReliability.level,
      reason: 'Low analyzer reliability keeps the final gate provisional.',
    });
  }
  if ((styleProfileUsage?.score ?? 1) < 0.45) {
    reliabilityAdjustments.push({
      source: 'style_profile_usage',
      level: 'low',
      reason: `Current role usage does not strongly fit the ${styleProfileUsage.lane} lane yet.`,
    });
  }
  if ((styleRolePlan?.suggested_pruned_roles?.length ?? 0) > 0) {
    reliabilityAdjustments.push({
      source: 'style_role_plan',
      impact: -0.04,
      reason: `Lane discipline would improve if ${styleRolePlan.suggested_pruned_roles.join(', ')} were demoted or removed.`,
    });
  }
  for (const [family, payload] of Object.entries(metricReliability)) {
    if ((payload?.level ?? 'medium') === 'low') {
      reliabilityAdjustments.push({
        source: family,
        level: payload.level,
        reason: `${family} metrics are low-confidence and should not fire findings on their own.`,
      });
    }
  }

  const findingSpecs = [
    {
      id: 'weak_groove_lock',
      title: 'Weak groove lock',
      severity: 'high',
      checks: [
        {
          id: 'groove_core',
          pass: grooveStrength < 0.66 || (analysis.rhythm?.groove_continuity ?? 0) < 0.62,
          evidence: `Groove metrics are soft: groove_strength ${scores.groove_strength}, groove_continuity ${round(
            analysis.rhythm?.groove_continuity ?? 0,
          )}.`,
        },
        {
          id: 'groove_alignment',
          pass:
            (analysis.rhythm?.onset_to_beat_alignment ?? 0) < 0.58 ||
            (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) < 0.58,
          evidence: `Beat/onset coherence is moderate: alignment ${round(
            analysis.rhythm?.onset_to_beat_alignment ?? 0,
          )}, inter-beat consistency ${round(analysis.rhythm?.inter_beat_loudness_consistency ?? 0)}.`,
        },
        {
          id: 'groove_example_band',
          pass:
            exampleTargets.length > 0 &&
            ((calibrationByMetric.groove_continuity?.fit ?? 1) < 0.6 ||
              (calibrationByMetric.inter_beat_loudness_consistency?.fit ?? 1) < 0.6),
          evidence: `Groove sits outside the attached example band: continuity fit ${round(
            calibrationByMetric.groove_continuity?.fit ?? 0,
          )}, beat-consistency fit ${round(calibrationByMetric.inter_beat_loudness_consistency?.fit ?? 0)}.`,
        },
        {
          id: 'groove_baseline_delta',
          pass: Number(baselineDeltas.groove_strength ?? 0) < -0.01,
          evidence: `Groove strength regressed ${round(baselineDeltas.groove_strength ?? 0)} versus baseline.`,
        },
      ],
      counterevidence: [
        scores.section_contrast >= 0.85 ? `Section contrast is already strong at ${scores.section_contrast}.` : null,
      ],
      revision_actions: [
        'Tighten the kick/bass conversation before adding more tops.',
        'Let the groove feel settled earlier, then use filter and mute choreography for movement.',
      ],
    },
    {
      id: 'low_beat_onset_coherence',
      title: 'Low beat and onset coherence',
      severity: 'medium',
      checks: [
        {
          id: 'tempo_confidence',
          pass:
            (analysis.rhythm?.tempo_confidence ?? 0) < 0.5 ||
            (analysis.rhythm?.tempo_stability ?? 0) < 0.65,
          evidence: `Tempo confidence/stability is modest: ${round(analysis.rhythm?.tempo_confidence ?? 0)} / ${round(
            analysis.rhythm?.tempo_stability ?? 0,
          )}.`,
        },
        {
          id: 'onset_alignment',
          pass: (analysis.rhythm?.onset_to_beat_alignment ?? 0) < 0.55,
          evidence: `Onset-to-beat alignment is ${round(analysis.rhythm?.onset_to_beat_alignment ?? 0)}.`,
        },
        {
          id: 'syncopation_example_band',
          pass: exampleTargets.length > 0 && (calibrationByMetric.syncopation_proxy?.fit ?? 1) < 0.58,
          evidence: `Syncopation sits outside the attached example band at fit ${round(
            calibrationByMetric.syncopation_proxy?.fit ?? 0,
          )}.`,
        },
        {
          id: 'groove_delta',
          pass: Number(baselineDeltas.groove_strength ?? 0) < 0,
          evidence: `Groove-related score delta is ${round(baselineDeltas.groove_strength ?? 0)} versus baseline.`,
        },
      ],
      counterevidence: [],
      revision_actions: [
        'Simplify the busiest rhythm lane so the pulse reads more clearly.',
        'Move syncopated accents later in the phrase instead of competing with the main beat.',
      ],
    },
    {
      id: 'insufficient_timbral_evolution',
      title: 'Insufficient timbral or filter evolution',
      severity: 'medium',
      checks: [
        {
          id: 'variation_floor',
          pass:
            (analysis.structure?.repetition_variation_balance ?? 0) < 0.55 ||
            (analysis.structure?.novelty_peak_rate ?? 0) < 0.12,
          evidence: `Variation is limited: repetition_variation_balance ${round(
            analysis.structure?.repetition_variation_balance ?? 0,
          )}, novelty_peak_rate ${round(analysis.structure?.novelty_peak_rate ?? 0)}.`,
        },
        {
          id: 'return_transition_narrow',
          pass:
            !dropTransition ||
            (Math.abs(dropTransition.brightness_delta ?? 0) < 0.06 &&
              Math.abs(dropTransition.boundary_strength ?? 0) < 0.55),
          evidence: dropTransition
            ? `The strongest return transition is still narrow: brightness delta ${round(
                dropTransition.brightness_delta ?? 0,
              )}, boundary strength ${round(dropTransition.boundary_strength ?? 0)}.`
            : 'No strong section transition was detected for the return.',
        },
        {
          id: 'timbre_example_band',
          pass:
            exampleTargets.length > 0 &&
            ((calibrationByMetric.spectral_centroid?.fit ?? 1) < 0.58 ||
              (analysis.structure?.repetition_variation_balance ?? 0) < 0.58),
          evidence: `Timbre motion undershoots the example band: centroid fit ${round(
            calibrationByMetric.spectral_centroid?.fit ?? 0,
          )}, variation balance ${round(analysis.structure?.repetition_variation_balance ?? 0)}.`,
        },
      ],
      counterevidence: [
        scores.transition_impact >= 0.85 ? `Transition impact is already decent at ${scores.transition_impact}.` : null,
      ],
      revision_actions: [
        'Create motion with filter opening, mute choreography, or brightness staging before adding new harmony.',
        'Let one timbral lane evolve clearly between groove, lift, and return.',
      ],
    },
    {
      id: 'return_payoff_too_small',
      title: 'Return payoff is too small',
      severity: 'high',
      checks: [
        {
          id: 'contrast_floor',
          pass: scores.section_contrast < 0.74 || scores.transition_impact < 0.72,
          evidence: `Contrast and return impact are limited: ${scores.section_contrast} / ${scores.transition_impact}.`,
        },
        {
          id: 'return_transition_floor',
          pass:
            !dropTransition ||
            Math.abs(dropTransition.loudness_delta ?? 0) < 0.08 ||
            Math.abs(dropTransition.onset_delta ?? 0) < 0.5,
          evidence: dropTransition
            ? `Return transition is modest: loudness delta ${round(dropTransition.loudness_delta ?? 0)}, onset delta ${round(
                dropTransition.onset_delta ?? 0,
              )}.`
            : 'No explicit breakdown-to-return transition was found.',
        },
        {
          id: 'return_delta',
          pass: Number(baselineDeltas.section_contrast ?? 0) < 0 || Number(baselineDeltas.transition_impact ?? 0) < 0,
          evidence: `Return-related deltas are ${round(baselineDeltas.section_contrast ?? 0)} / ${round(
            baselineDeltas.transition_impact ?? 0,
          )} versus baseline.`,
        },
      ],
      counterevidence: [],
      revision_actions: [
        'Thin the breakdown harder before the return.',
        'Make the first returning downbeat clearer with one stronger impact or re-entry, not more simultaneous parts.',
      ],
    },
    {
      id: 'harmonic_drift',
      title: 'Too much harmonic drift for a loop-first brief',
      severity: 'medium',
      checks: [
        {
          id: 'harmonic_drift_floor',
          pass:
            (analysis.tonal?.harmonic_stability ?? 0) < 0.5 ||
            (analysis.tonal?.chord_change_proxy ?? 0) > 0.62,
          evidence: `Loop harmony is moving more than expected: harmonic_stability ${round(
            analysis.tonal?.harmonic_stability ?? 0,
          )}, chord_change_proxy ${round(analysis.tonal?.chord_change_proxy ?? 0)}.`,
        },
        {
          id: 'loop_first_brief',
          pass: /loop-first|french house|disco/i.test(`${brief.genre ?? ''} ${brief['notes-for-agent'] ?? ''}`),
          evidence: 'The brief explicitly asks for loop-first, style-disciplined harmony.',
        },
        {
          id: 'harmonic_example_band',
          pass:
            exampleTargets.length > 0 &&
            ((calibrationByMetric.harmonic_stability?.fit ?? 1) < 0.58 ||
              (calibrationByMetric.chord_change_proxy?.fit ?? 1) < 0.58),
          evidence: `Harmony drifts outside the attached example band: stability fit ${round(
            calibrationByMetric.harmonic_stability?.fit ?? 0,
          )}, chord-change fit ${round(calibrationByMetric.chord_change_proxy?.fit ?? 0)}.`,
        },
      ],
      counterevidence: [
        styleAlignment.harmonic_fit >= 0.7 ? `Harmonic fit is still decent at ${styleAlignment.harmonic_fit}.` : null,
      ],
      revision_actions: [
        'Reduce harmonic churn and let the main loop carry more of the identity.',
        'Save harmonic color shifts for section boundaries rather than every phrase.',
      ],
    },
    {
      id: 'kick_bass_pocket_conflict',
      title: 'Kick and bass pocket conflict',
      severity: 'high',
      checks: [
        {
          id: 'low_end_score',
          pass: scores.low_end_cleanliness < 0.68,
          evidence: `Low-end cleanliness is ${scores.low_end_cleanliness}.`,
        },
        {
          id: 'low_end_density',
          pass:
            ((analysis.timbre?.sub_energy_ratio ?? 0) + (analysis.timbre?.bass_energy_ratio ?? 0)) > 0.64 &&
            (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) < 0.7,
          evidence: `Low-end energy is dense while beat-to-beat consistency is only ${round(
            analysis.rhythm?.inter_beat_loudness_consistency ?? 0,
          )}.`,
        },
        {
          id: 'low_end_example_band',
          pass:
            exampleTargets.length > 0 &&
            ((calibrationByMetric.sub_energy_ratio?.fit ?? 1) < 0.6 || (calibrationByMetric.bass_energy_ratio?.fit ?? 1) < 0.6),
          evidence: `Low-end balance sits outside the example band: sub fit ${round(
            calibrationByMetric.sub_energy_ratio?.fit ?? 0,
          )}, bass fit ${round(calibrationByMetric.bass_energy_ratio?.fit ?? 0)}.`,
        },
        {
          id: 'low_end_delta',
          pass: Number(baselineDeltas.low_end_cleanliness ?? 0) < 0,
          evidence: `Low-end cleanliness regressed ${round(baselineDeltas.low_end_cleanliness ?? 0)} versus baseline.`,
        },
      ],
      counterevidence: [],
      revision_actions: [
        'Shorten the bass sustain or leave more empty space around the kick.',
        'Trim bass weight before adding extra sub or widening the kick.',
      ],
    },
    {
      id: 'repetition_fatigue',
      title: 'Repetition fatigue without enough change',
      severity: 'medium',
      checks: [
        {
          id: 'recurrence_without_variation',
          pass:
            (analysis.structure?.recurrence_strength ?? 0) > 0.68 &&
            (analysis.structure?.repetition_variation_balance ?? 0) < 0.48,
          evidence: `The loop repeats strongly (${round(
            analysis.structure?.recurrence_strength ?? 0,
          )}) without enough variation (${round(analysis.structure?.repetition_variation_balance ?? 0)}).`,
        },
        {
          id: 'limited_change_lanes',
          pass: melodicLayers.length <= 2 && transitionLayers.length <= 2,
          evidence: `There are only ${melodicLayers.length} melodic layers and ${transitionLayers.length} transition layers to carry long-form change.`,
        },
      ],
      counterevidence: [],
      revision_actions: [
        'Keep the loop, but add one clearer timbral or rhythmic evolution point every major section.',
        'Change one prominent lane at the return instead of adding several small gestures.',
      ],
    },
    {
      id: 'top_end_brittle',
      title: 'Top end is trending brittle',
      severity: 'medium',
      checks: [
        {
          id: 'top_end_brightness',
          pass:
            scores.top_end_harshness < 0.72 ||
            (analysis.timbre?.high_band_energy_ratio ?? 0) > 0.21 ||
            (analysis.timbre?.spectral_flatness ?? 0) > 0.24,
          evidence: `Top-end balance is bright: harshness score ${scores.top_end_harshness}, high-band ratio ${round(
            analysis.timbre?.high_band_energy_ratio ?? 0,
          )}, flatness ${round(analysis.timbre?.spectral_flatness ?? 0)}.`,
        },
        {
          id: 'return_centroid_high',
          pass:
            (dropSection.timbre?.spectral_centroid ?? 0) > 2800 ||
            (sections.lift?.timbre?.spectral_centroid ?? 0) > 2600,
          evidence: `Lift/drop centroid is elevated at ${round(
            dropSection.timbre?.spectral_centroid ?? 0,
          )} Hz in the return section.`,
        },
        {
          id: 'top_end_delta',
          pass: Number(baselineDeltas.top_end_harshness ?? 0) < 0,
          evidence: `Top-end harshness regressed ${round(baselineDeltas.top_end_harshness ?? 0)} versus baseline.`,
        },
      ],
      counterevidence: [],
      revision_actions: [
        'Soften the brightest hat or top lane before adding more lift effects.',
        'Use motion and contrast, not extra brittleness, to make the return feel bigger.',
      ],
    },
  ];

  for (const spec of findingSpecs) {
    const evidence = [];
    const firedChecks = [];
    for (const check of spec.checks) {
      if (check.pass) {
        evidence.push(check.evidence);
        firedChecks.push(check.id);
      }
    }
    const counterevidence = spec.counterevidence.filter(Boolean);
    if (evidence.length >= 2) {
      triggeredChecks.push({
        finding: spec.id,
        checks: firedChecks,
      });
      musicFindings.push(
        makeFinding({
          title: spec.title,
          severity: spec.severity,
          evidence,
          counterevidence,
          revisionActions: spec.revision_actions,
          signalCount: evidence.length,
        }),
      );
    } else if (evidence.length === 1) {
      suppressedChecks.push({
        finding: spec.id,
        checks: firedChecks,
        reason: 'Only one signal fired; leaving this as an uncertainty note instead of a hard finding.',
      });
      uncertaintyNotes.push({
        title: spec.title,
        evidence,
        counterevidence,
      });
    }
  }

  if (styleProfileUsage?.warnings?.length > 0) {
    uncertaintyNotes.push({
      title: `Lane drift risk for ${styleProfileUsage.lane}`,
      evidence: styleProfileUsage.warnings,
      counterevidence: styleProfileUsage.primary_hook_hits?.length > 0 ? [`Primary hook roles still match ${styleProfileUsage.primary_hook_hits.join(', ')}.`] : [],
    });
  }
  if ((styleProfileUsage?.hook_role_count ?? 0) > 3) {
    uncertaintyNotes.push({
      title: 'Hook identity is too spread out',
      evidence: [
        `There are ${styleProfileUsage.hook_role_count} hook-carrying roles active, which makes the song feel less singular.`,
      ],
      counterevidence: [],
    });
  }
  if ((styleRolePlan?.suggested_pruned_roles?.length ?? 0) > 0) {
    uncertaintyNotes.push({
      title: 'Role pruning likely needed',
      evidence: styleRolePlan.suggested_pruned_roles.map(
        (role) => `${role} is a strong candidate to demote or remove for this lane.`,
      ),
      counterevidence:
        styleRolePlan.primary_hook_roles?.length > 0
          ? [`Primary hook target roles are ${styleRolePlan.primary_hook_roles.join(', ')}.`]
          : [],
    });
  }

  const techniqueDrivenActions = [];
  const techniqueOpportunities = strudelTechniques?.opportunities ?? [];
  if (
    techniqueOpportunities.some((entry) => entry.includes('bass_pitched')) &&
    (musicFindings.some((finding) => finding.title === 'Kick and bass pocket conflict') || scores.low_end_cleanliness < 0.7)
  ) {
    techniqueDrivenActions.push('Try note(...).s("bass_pitched") for the main bassline and shorten the phrase before adding more sub weight.');
  }
  if (
    techniqueOpportunities.some((entry) => entry.includes('early() or off()')) &&
    (musicFindings.some((finding) => finding.title === 'Weak groove lock') || scores.groove_strength < 0.68)
  ) {
    techniqueDrivenActions.push('Use early() or off() on one hook or percussion phrase to create groove before adding another full-time lane.');
  }
  if (
    techniqueOpportunities.some((entry) => entry.includes('slice(), splice(), or chop()')) &&
    (musicFindings.some((finding) => finding.title === 'Repetition fatigue without enough change') || scores.melodic_memorability < 0.75)
  ) {
    techniqueDrivenActions.push('Turn one vocal, stab, or pluck phrase into identity with slice()/splice()/chop() instead of layering another motif.');
  }
  if (
    techniqueOpportunities.some((entry) => entry.includes('voicing()')) &&
    musicFindings.some((finding) => finding.title === 'Too much harmonic drift for a loop-first brief')
  ) {
    techniqueDrivenActions.push('Rewrite the harmonic bed with chord(...).voicing() so the motion stays smooth while the loop remains stable.');
  }
  if (
    techniqueOpportunities.some((entry) => entry.includes('orbit() or duckorbit()')) &&
    (scores.top_end_harshness < 0.72 || musicFindings.some((finding) => finding.title === 'Top end is trending brittle'))
  ) {
    techniqueDrivenActions.push('Move the brightest or wettest lanes onto separate orbit() buses and use duckorbit() before adding more delay or room.');
  }

  const revisionActions = [...new Set([...runtimeBlockers, ...musicFindings].flatMap((finding) => finding.revision_actions ?? []).concat(techniqueDrivenActions))].map(
    (action, index) => ({
      priority: index + 1,
      scope: runtimeBlockers.length > 0 ? 'runtime' : 'music',
      depends_on_blocker_resolution: runtimeBlockers.length > 0,
      action,
    }),
  );

  const evidenceStrength =
    musicFindings.length > 0
      ? average(musicFindings.map((finding) => finding.confidence_score ?? 0))
      : average([styleAlignment.overall, exampleAlignment.overall || styleAlignment.overall]);
  const confidenceScore = round(
    clamp((signalReliability.overall ?? 0.5) * 0.65 + evidenceStrength * 0.35),
  );
  const confidence = {
    level: confidenceLabel(confidenceScore),
    score: confidenceScore,
  };

  const highConfidenceFindingCount = musicFindings.filter((finding) => finding.confidence === 'high').length;
  const mediumConfidenceFindingCount = musicFindings.filter((finding) => finding.confidence === 'medium').length;
  const hasContractErrors = validation.errors.length > 0;
  const strongBaselineRegression =
    Number(baselineDeltas.groove_strength ?? 0) < -0.02 ||
    Number(baselineDeltas.low_end_cleanliness ?? 0) < -0.02 ||
    Number(baselineDeltas.transition_impact ?? 0) < -0.03 ||
    Number(baselineDeltas.style_fit ?? 0) < -0.03;
  let gate = 'review_gate';
  if (runtimeBlockers.length > 0 || hasContractErrors) {
    gate = 'blocked';
  } else if (highConfidenceFindingCount > 0 || (mediumConfidenceFindingCount >= 2 && strongBaselineRegression)) {
    gate = 'revise';
  } else if (
    musicFindings.length === 0 &&
    styleAlignment.overall >= 0.8 &&
    (exampleTargets.length === 0 || exampleAlignment.overall >= 0.72) &&
    confidence.level !== 'low' &&
    (styleProfileUsage?.score ?? 1) >= 0.55
  ) {
    gate = 'pass';
  } else {
    gate = 'review_gate';
  }

  const blockerClass =
    runtimeBlockers.length > 0
      ? 'runtime'
      : hasContractErrors
        ? 'contract'
        : analysis.status === 'blocked'
          ? 'analysis'
          : 'none';
  const provisional =
    analysis.readiness !== 'ready_for_critique' ||
    confidence.level === 'low' ||
    signalReliability.level === 'low';
  const topStrength = describeStrength(scores, styleAlignment, promptReferenceAlignmentRefined);
  const topWeakness = runtimeBlockers[0]?.title ?? musicFindings[0]?.title ?? null;
  const singleNextMove = revisionActions[0]?.action ?? null;
  const payload = {
    phase: 'critique',
    gate,
    blocker_class: blockerClass,
    provisional,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    scores,
    confidence,
    critic_version: CRITIC_VERSION,
    calibration_version: CALIBRATION_VERSION,
    runtime_blockers: runtimeBlockers,
    music_findings: musicFindings,
    uncertainty_notes: uncertaintyNotes,
    style_alignment: styleAlignment,
    style_profile: styleProfile,
    style_profile_usage: styleProfileUsage,
    style_role_plan: styleRolePlan,
    prompt_style_lens: promptStyleLens,
    prompt_reference_alignment: promptReferenceAlignmentRefined,
    generation_strategy: generationStrategy,
    example_alignment: exampleAlignment,
    reference_alignment: referenceAlignment,
    strudel_techniques: strudelTechniques,
    taste_memory: tasteMemory,
    strongest_trait: topStrength,
    top_weakness: topWeakness,
    single_next_move: singleNextMove,
    baseline_deltas: {
      baseline_run_dir: baselineRunDir,
      deltas: baselineDeltas,
      top_changes: rankedBaselineDeltas.slice(0, 4),
    },
    triggered_checks: triggeredChecks,
    suppressed_checks: suppressedChecks,
    reliability_adjustments: reliabilityAdjustments,
    retrieval_cards: referenceCards.map((card) => ({
      name: card.name,
      path: card.path,
      metadata_path: card.metadataPath,
      score: card.score,
      matched_terms: card.matchedTerms,
      metadata: card.metadata,
    })),
    provider_reviews: [providerReview],
    revision_actions: revisionActions,
    finding_templates_version: FINDING_TEMPLATES_VERSION,
    summary:
      gate === 'pass'
        ? 'The song clears the current rubric and style checks with no high-confidence issues.'
        : gate === 'blocked'
          ? blockerClass === 'contract'
            ? validation.errors[0] ?? 'Review blocked by song contract validation errors.'
            : runtimeBlockers[0]?.title ?? 'Review blocked by runtime issues.'
          : gate === 'revise'
            ? musicFindings[0]?.title ?? 'Song needs revision.'
            : exampleTargets.length > 0
              ? 'The song is close to the attached examples, but it still needs a human taste check before promotion.'
              : promptStyleLens
                ? 'The song is close to the prompt-reference lane, but it still needs a human taste check before promotion.'
                : 'The song is promising, but the evidence is mixed enough that it should stop at a human review gate.',
  };

  writeFileSync(join(runDir, 'critique.json'), `${JSON.stringify(payload, null, 2)}\n`);
  const verdictArtifacts = writeVerdictArtifacts(
    runDir,
    buildRunVerdict({
      slug,
      runDir,
      critique: payload,
      baselineRunDir,
      baselineCritique,
    }),
  );

  const markdown = [
    `# Critique: ${slug}`,
    '',
    `Gate: ${gate}`,
    `Summary: ${payload.summary}`,
    `Confidence: ${confidence.level} (${confidence.score})`,
    `Style alignment: ${styleAlignment.overall}`,
    `Signal reliability: ${signalReliability.level} (${signalReliability.overall})`,
    `Examples: ${exampleTargets.length > 0 ? exampleTargets.join(', ') : 'none'}`,
    '',
    '## Scores',
    ...Object.entries(scores).map(([key, value]) => `- ${key}: ${value}`),
    '',
    '## Findings',
    ...(musicFindings.length > 0
      ? musicFindings.map((finding) => `- ${finding.title} (${finding.confidence})`)
      : ['- none']),
    '',
    '## Uncertainty Notes',
    ...(uncertaintyNotes.length > 0 ? uncertaintyNotes.map((note) => `- ${note.title}`) : ['- none']),
  ].join('\n');
  writeFileSync(join(runDir, 'revision.md'), `${markdown}\n`);

  return {
    phase: 'song:critique',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir,
    gate,
    blocker_class: blockerClass,
    provisional,
    confidence,
    scores,
    style_alignment: styleAlignment,
    prompt_style_lens: promptStyleLens,
    prompt_reference_alignment: promptReferenceAlignmentRefined,
    reference_alignment: referenceAlignment,
    strudel_techniques: strudelTechniques,
    baseline_deltas: payload.baseline_deltas,
    runtime_blockers: runtimeBlockers,
    music_findings: musicFindings,
    uncertainty_notes: uncertaintyNotes,
    recommended_next_action: gate === 'pass' ? 'keep' : gate === 'review_gate' ? 'review_gate' : 'revise',
    approval_required: gate === 'review_gate',
    critique_path: join(runDir, 'critique.json'),
    revision_summary_path: join(runDir, 'revision.md'),
    verdict_path: verdictArtifacts.verdict_path,
    verdict_markdown_path: verdictArtifacts.verdict_markdown_path,
    summary_path: verdictArtifacts.summary_path,
    message: `Wrote critique to ${join(runDir, 'critique.json')}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongCritique, process.argv.slice(2)));
}
