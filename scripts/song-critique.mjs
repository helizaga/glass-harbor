import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  extractNamedLayers,
  normalizeRuntimeErrors,
  parseBrief,
  readText,
  resolveRunDir,
  resolveSongSlug,
  selectReferenceCards,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { chooseBaselineRun, critiqueForRun, diffScores, ensureSongMemory } from '../lib/review-gates.mjs';
import { reviewAudioWithProvider } from './song-review-provider.mjs';

const FINDING_TEMPLATES_VERSION = '2026-03-27-v2';

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

function average(values) {
  return values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;
}

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

function buildStyleAlignment({ brief, referenceCards, embeddingAlignment, analysis, validation }) {
  const bpm = Number(validation.metadata.bpm ?? analysis.declared_bpm ?? 0);
  const bpmFit = bpm > 0 ? clamp(1 - Math.abs(bpm - 122) / 14) : 0.5;
  const retrievalFit = referenceCards.length > 0 ? clamp((referenceCards[0].score ?? 0) / 24) : 0;
  const grooveFit = clamp((analysis.rhythm?.groove_continuity ?? 0) * 0.7 + (analysis.rhythm?.syncopation_proxy ?? 0) * 0.3);
  const harmonicFit = clamp((analysis.tonal?.harmonic_stability ?? 0) * 0.6 + (1 - clamp(analysis.tonal?.chord_change_proxy ?? 0)) * 0.4);
  const embeddingFit = Number(embeddingAlignment.overall ?? 0);
  const overall = round(embeddingFit * 0.45 + retrievalFit * 0.2 + grooveFit * 0.15 + harmonicFit * 0.1 + bpmFit * 0.1);

  return {
    provider: embeddingAlignment.provider ?? 'none',
    status: embeddingAlignment.status ?? 'fallback',
    overall,
    bpm_fit: round(bpmFit),
    retrieval_fit: round(retrievalFit),
    groove_fit: round(grooveFit),
    harmonic_fit: round(harmonicFit),
    embedding_fit: round(embeddingFit),
    top_reference: embeddingAlignment.top_reference ?? null,
    brief_title: brief.title ?? null,
    confidence_notes: embeddingAlignment.confidence_notes ?? [],
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

function confidenceLabel(score) {
  if (score >= 0.8) {
    return 'high';
  }
  if (score >= 0.6) {
    return 'medium';
  }
  return 'low';
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

  const song = songPaths(slug);
  const brief = parseBrief(readText(song.briefPath));
  const code = readText(song.songPath);
  const validation = validateSongCode(code);
  const analysis = parseJsonFile(analysisPath);
  const runInfo = existsSync(join(runDir, 'run.json'))
    ? parseJsonFile(join(runDir, 'run.json'), { runtime_blockers: [], console_errors: [] })
    : { runtime_blockers: [], console_errors: [] };
  const providerReview = await reviewAudioWithProvider({
    song: slug,
    runDir,
    analysis,
    brief,
  });

  const referenceCards = selectReferenceCards(brief, 3);
  const embeddingAlignment = analysis.embedding_alignment ?? {
    provider: 'none',
    status: 'fallback',
    overall: 0,
    reference_scores: [],
    confidence_notes: ['Embedding alignment was not computed during analysis.'],
  };
  const styleAlignment = buildStyleAlignment({
    brief,
    referenceCards,
    embeddingAlignment,
    analysis,
    validation,
  });
  const referenceAlignment = summarizeReferenceAlignment(referenceCards, embeddingAlignment);
  const layerNames = extractNamedLayers(code);
  const melodicLayers = layerNames.filter((name) => /(lead|pluck|arp|pad|hook|robot)/i.test(name));
  const transitionLayers = layerNames.filter((name) => /(riser|impact|shimmer|air|vocal)/i.test(name));
  const sections = analysis.sections ?? {};
  const grooveSection = sections.groove ?? analysis.metrics ?? {};
  const breakdownSection = sections.breakdown ?? analysis.metrics ?? {};
  const dropSection = sections.drop ?? analysis.metrics ?? {};
  const dropTransition = pickTransition(analysis, [
    ['breakdown', 'drop'],
    ['lift', 'drop'],
    ['groove', 'drop'],
  ]);
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
  const styleFit = styleAlignment.overall;

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

  const memory = ensureSongMemory(slug, { excludeRunDir: runDir });
  const baselineRunDir = chooseBaselineRun(slug, { memory, excludeRunDir: runDir });
  const baselineCritique = critiqueForRun(baselineRunDir);
  const { deltas: baselineDeltas, ranked: rankedBaselineDeltas } = diffScores(
    baselineCritique?.scores ?? {},
    scores,
  );

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

  const findingSpecs = [
    {
      title: 'Weak groove lock',
      severity: 'high',
      checks: [
        {
          pass: grooveStrength < 0.66 || (analysis.rhythm?.groove_continuity ?? 0) < 0.62,
          evidence: `Groove metrics are soft: groove_strength ${scores.groove_strength}, groove_continuity ${round(
            analysis.rhythm?.groove_continuity ?? 0,
          )}.`,
        },
        {
          pass:
            (analysis.rhythm?.onset_to_beat_alignment ?? 0) < 0.58 ||
            (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) < 0.58,
          evidence: `Beat/onset coherence is moderate: alignment ${round(
            analysis.rhythm?.onset_to_beat_alignment ?? 0,
          )}, inter-beat consistency ${round(analysis.rhythm?.inter_beat_loudness_consistency ?? 0)}.`,
        },
        {
          pass: styleAlignment.overall < 0.82 && referenceAlignment.some((entry) => entry.retrieval_score >= 8),
          evidence: `Style alignment ${styleAlignment.overall} is below the loop-first target suggested by the reference cluster.`,
        },
        {
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
      title: 'Low beat and onset coherence',
      severity: 'medium',
      checks: [
        {
          pass:
            (analysis.rhythm?.tempo_confidence ?? 0) < 0.5 ||
            (analysis.rhythm?.tempo_stability ?? 0) < 0.65,
          evidence: `Tempo confidence/stability is modest: ${round(analysis.rhythm?.tempo_confidence ?? 0)} / ${round(
            analysis.rhythm?.tempo_stability ?? 0,
          )}.`,
        },
        {
          pass: (analysis.rhythm?.onset_to_beat_alignment ?? 0) < 0.55,
          evidence: `Onset-to-beat alignment is ${round(analysis.rhythm?.onset_to_beat_alignment ?? 0)}.`,
        },
        {
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
      title: 'Insufficient timbral or filter evolution',
      severity: 'medium',
      checks: [
        {
          pass:
            (analysis.structure?.repetition_variation_balance ?? 0) < 0.55 ||
            (analysis.structure?.novelty_peak_rate ?? 0) < 0.12,
          evidence: `Variation is limited: repetition_variation_balance ${round(
            analysis.structure?.repetition_variation_balance ?? 0,
          )}, novelty_peak_rate ${round(analysis.structure?.novelty_peak_rate ?? 0)}.`,
        },
        {
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
          pass:
            referenceAlignment.some((entry) => /filter|chrome|strobe|drift/i.test(entry.name)) &&
            styleAlignment.embedding_fit < 0.82,
          evidence: `Reference alignment suggests the filter/timbre lane is under-realized at ${styleAlignment.embedding_fit}.`,
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
      title: 'Return payoff is too small',
      severity: 'high',
      checks: [
        {
          pass: scores.section_contrast < 0.74 || scores.transition_impact < 0.72,
          evidence: `Contrast and return impact are limited: ${scores.section_contrast} / ${scores.transition_impact}.`,
        },
        {
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
      title: 'Too much harmonic drift for a loop-first brief',
      severity: 'medium',
      checks: [
        {
          pass:
            (analysis.tonal?.harmonic_stability ?? 0) < 0.5 ||
            (analysis.tonal?.chord_change_proxy ?? 0) > 0.62,
          evidence: `Loop harmony is moving more than expected: harmonic_stability ${round(
            analysis.tonal?.harmonic_stability ?? 0,
          )}, chord_change_proxy ${round(analysis.tonal?.chord_change_proxy ?? 0)}.`,
        },
        {
          pass: /loop-first|french house|disco/i.test(`${brief.genre ?? ''} ${brief['notes-for-agent'] ?? ''}`),
          evidence: 'The brief explicitly asks for loop-first, style-disciplined harmony.',
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
      title: 'Kick and bass pocket conflict',
      severity: 'high',
      checks: [
        {
          pass: scores.low_end_cleanliness < 0.68,
          evidence: `Low-end cleanliness is ${scores.low_end_cleanliness}.`,
        },
        {
          pass:
            ((analysis.timbre?.sub_energy_ratio ?? 0) + (analysis.timbre?.bass_energy_ratio ?? 0)) > 0.64 &&
            (analysis.rhythm?.inter_beat_loudness_consistency ?? 0) < 0.7,
          evidence: `Low-end energy is dense while beat-to-beat consistency is only ${round(
            analysis.rhythm?.inter_beat_loudness_consistency ?? 0,
          )}.`,
        },
        {
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
      title: 'Repetition fatigue without enough change',
      severity: 'medium',
      checks: [
        {
          pass:
            (analysis.structure?.recurrence_strength ?? 0) > 0.68 &&
            (analysis.structure?.repetition_variation_balance ?? 0) < 0.48,
          evidence: `The loop repeats strongly (${round(
            analysis.structure?.recurrence_strength ?? 0,
          )}) without enough variation (${round(analysis.structure?.repetition_variation_balance ?? 0)}).`,
        },
        {
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
      title: 'Top end is trending brittle',
      severity: 'medium',
      checks: [
        {
          pass:
            scores.top_end_harshness < 0.72 ||
            (analysis.timbre?.high_band_energy_ratio ?? 0) > 0.21 ||
            (analysis.timbre?.spectral_flatness ?? 0) > 0.24,
          evidence: `Top-end balance is bright: harshness score ${scores.top_end_harshness}, high-band ratio ${round(
            analysis.timbre?.high_band_energy_ratio ?? 0,
          )}, flatness ${round(analysis.timbre?.spectral_flatness ?? 0)}.`,
        },
        {
          pass:
            (dropSection.timbre?.spectral_centroid ?? 0) > 2800 ||
            (sections.lift?.timbre?.spectral_centroid ?? 0) > 2600,
          evidence: `Lift/drop centroid is elevated at ${round(
            dropSection.timbre?.spectral_centroid ?? 0,
          )} Hz in the return section.`,
        },
        {
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
    for (const check of spec.checks) {
      if (check.pass) {
        evidence.push(check.evidence);
      }
    }
    const counterevidence = spec.counterevidence.filter(Boolean);
    if (evidence.length >= 2) {
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
      uncertaintyNotes.push({
        title: spec.title,
        evidence,
        counterevidence,
      });
    }
  }

  const revisionActions = [...new Set([...runtimeBlockers, ...musicFindings].flatMap((finding) => finding.revision_actions ?? []))].map(
    (action, index) => ({
      priority: index + 1,
      scope: runtimeBlockers.length > 0 ? 'runtime' : 'music',
      depends_on_blocker_resolution: runtimeBlockers.length > 0,
      action,
    }),
  );

  const signalPool = [
    analysis.analysis_engine === 'librosa-rich' ? 1 : 0,
    analysis.readiness === 'ready_for_critique' ? 1 : 0,
    embeddingAlignment.status === 'ok' ? 1 : 0,
    referenceAlignment.length > 0 ? 1 : 0,
  ];
  const confidenceScore = round(signalPool.reduce((sum, value) => sum + value, 0) / signalPool.length);
  const confidence = {
    level: confidenceLabel(confidenceScore),
    score: confidenceScore,
  };

  const highConfidenceFindingCount = musicFindings.filter((finding) => finding.confidence === 'high').length;
  const hasContractErrors = validation.errors.length > 0;
  let gate = 'review_gate';
  if (runtimeBlockers.length > 0 || hasContractErrors) {
    gate = 'blocked';
  } else if (highConfidenceFindingCount > 0) {
    gate = 'revise';
  } else if (musicFindings.length === 0 && styleAlignment.overall >= 0.78 && confidence.level !== 'low') {
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
  const provisional = analysis.readiness !== 'ready_for_critique' || confidence.level === 'low';
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
    runtime_blockers: runtimeBlockers,
    music_findings: musicFindings,
    uncertainty_notes: uncertaintyNotes,
    style_alignment: styleAlignment,
    reference_alignment: referenceAlignment,
    baseline_deltas: {
      baseline_run_dir: baselineRunDir,
      deltas: baselineDeltas,
      top_changes: rankedBaselineDeltas.slice(0, 4),
    },
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
            : 'The song is promising, but the evidence is mixed enough that it should stop at a human review gate.',
  };

  writeFileSync(join(runDir, 'critique.json'), `${JSON.stringify(payload, null, 2)}\n`);

  const markdown = [
    `# Critique: ${slug}`,
    '',
    `Gate: ${gate}`,
    `Summary: ${payload.summary}`,
    `Confidence: ${confidence.level} (${confidence.score})`,
    `Style alignment: ${styleAlignment.overall}`,
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
    reference_alignment: referenceAlignment,
    baseline_deltas: payload.baseline_deltas,
    runtime_blockers: runtimeBlockers,
    music_findings: musicFindings,
    uncertainty_notes: uncertaintyNotes,
    recommended_next_action: gate === 'pass' ? 'keep' : gate === 'review_gate' ? 'review_gate' : 'revise',
    approval_required: gate === 'review_gate',
    critique_path: join(runDir, 'critique.json'),
    revision_summary_path: join(runDir, 'revision.md'),
    message: `Wrote critique to ${join(runDir, 'critique.json')}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongCritique, process.argv.slice(2)));
}
