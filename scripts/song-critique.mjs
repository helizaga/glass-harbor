import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  extractNamedLayers,
  parseBrief,
  readText,
  resolveRunDir,
  resolveSongSlug,
  selectReferenceCards,
  songPaths,
  normalizeRuntimeErrors,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { reviewAudioWithProvider } from './song-review-provider.mjs';

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function round(value) {
  return Number(value.toFixed(3));
}

function average(values) {
  return values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;
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
  const analysis = JSON.parse(readFileSync(analysisPath, 'utf8'));
  const runInfo = existsSync(join(runDir, 'run.json'))
    ? JSON.parse(readFileSync(join(runDir, 'run.json'), 'utf8'))
    : { runtime_blockers: [], console_errors: [] };
  const providerReview = await reviewAudioWithProvider({
    song: slug,
    runDir,
    analysis,
    brief,
  });

  const referenceCards = selectReferenceCards(brief, 3);
  const sections = analysis.sections ?? {};
  const sectionNames = Object.keys(sections);
  const grooveSection =
    sections.groove ||
    sections['groove-2'] ||
    sections[sectionNames.find((name) => name.includes('groove'))] ||
    analysis.metrics;
  const breakdownSection =
    sections.breakdown || sections[sectionNames.find((name) => name.includes('break'))] || analysis.metrics;
  const dropSection =
    sections.drop ||
    sections['second-drop'] ||
    sections[sectionNames.find((name) => name.includes('drop'))] ||
    analysis.metrics;

  const layerNames = extractNamedLayers(code);
  const melodicLayers = layerNames.filter((name) => /(lead|pluck|arp|pad|hook)/i.test(name));
  const transitionLayers = layerNames.filter((name) => /(riser|impact|shimmer|air|vocal)/i.test(name));
  const referenceOverlap = average(referenceCards.map((card) => clamp(card.score / 40) || 0));
  const silentRender = (analysis.metrics?.rms ?? 0) === 0 && (analysis.metrics?.peak ?? 0) === 0;
  const runtimeErrors =
    runInfo.runtime_blockers?.length > 0 ? runInfo.runtime_blockers : normalizeRuntimeErrors(runInfo.console_errors);

  const structureClarity = clamp(validation.errors.length === 0 ? 0.9 : 0.45);
  const grooveStrength = silentRender ? 0 : clamp(((grooveSection.onset_density ?? 0) / 9 + (analysis.metrics?.rms ?? 0) / 0.18) / 2);
  const sectionContrast = silentRender
    ? 0
    : clamp(
        Math.abs((dropSection.rms ?? 0) - (breakdownSection.rms ?? 0)) * 9 +
          Math.abs((dropSection.onset_density ?? 0) - (breakdownSection.onset_density ?? 0)) / 10,
      );
  const transitionImpact = silentRender ? 0 : clamp(sectionContrast * 0.7 + Math.min(1, transitionLayers.length / 5) * 0.3);
  const melodicMemorability = clamp(Math.min(1, melodicLayers.length / 4) * 0.6 + referenceOverlap * 0.4);
  const lowEndCleanliness = silentRender ? 0 : clamp(1 - Math.abs((analysis.metrics?.low_end_ratio ?? 0) - 0.6) / 0.35);
  const topEndHarshness = silentRender ? 0 : clamp(1 - Math.max(0, (analysis.metrics?.brightness_proxy ?? 0) - 1.8) / 2.2);
  const styleFit = silentRender
    ? clamp(referenceOverlap * 0.35 + melodicMemorability * 0.2)
    : clamp(referenceOverlap * 0.5 + clamp((Number.parseFloat(validation.metadata.bpm ?? '0') - 118) / 10) * 0.1 + melodicMemorability * 0.4);

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

  const runtimeBlockers = [];
  const musicFindings = [];
  const revisionActions = [];

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
      revision_actions: [
        'Make sure the offline render harness loads the same sample and synth environment as the interactive Strudel path.',
        'Treat musical critique as provisional until the render path resolves missing sound errors.',
        'Use the local debug app or Strudel web for ear checks while fixing the offline render environment.',
      ],
    });
  }

  if (!silentRender && sectionContrast < 0.62) {
    musicFindings.push({
      title: 'Drop contrast is too restrained',
      severity: 'high',
      evidence: [
        `Breakdown RMS ${round(breakdownSection.rms ?? 0)} vs drop RMS ${round(dropSection.rms ?? 0)}`,
        `Breakdown onset density ${round(breakdownSection.onset_density ?? 0)} vs drop onset density ${round(dropSection.onset_density ?? 0)}`,
      ],
      revision_actions: [
        'Pull hats and tops back harder in the breakdown before the main drop.',
        'Add a clearer impact or riser resolution into the first drop.',
        'Increase drop bass or clap energy slightly rather than adding more parts everywhere.',
      ],
    });
  }

  if (!silentRender && topEndHarshness < 0.6) {
    musicFindings.push({
      title: 'Top end is trending brittle',
      severity: 'medium',
      evidence: [`Brightness proxy is ${round(analysis.metrics.brightness_proxy ?? 0)}, which is high for the brief.`],
      revision_actions: [
        'Soften the busiest hat variant or reduce hat gain in the brightest sections.',
        'Use shimmer or air for lift instead of stacking extra bright percussion.',
      ],
    });
  }

  if (!silentRender && lowEndCleanliness < 0.58) {
    musicFindings.push({
      title: 'Low end needs cleaner separation',
      severity: 'medium',
      evidence: [`Low-end ratio is ${round(analysis.metrics.low_end_ratio ?? 0)} with crest factor ${round(analysis.metrics.crest_factor ?? 0)}.`],
      revision_actions: [
        'Shorten the bass sustain or simplify bass rhythm under the kick.',
        'Keep kick strong, then trim bass gain before adding more sub weight.',
      ],
    });
  }

  if (melodicMemorability < 0.6) {
    musicFindings.push({
      title: 'Melodic identity is under-defined',
      severity: 'medium',
      evidence: [`Only ${melodicLayers.length} named melodic layers were detected in the song scaffold.`],
      revision_actions: [
        'Strengthen one lead or pluck motif instead of adding another pad.',
        'Let the hook reappear in the drop with a cleaner rhythmic shape.',
      ],
    });
  }

  for (const finding of [...runtimeBlockers, ...musicFindings]) {
    revisionActions.push(...finding.revision_actions);
  }

  const gate =
    runtimeBlockers.length > 0 ? 'blocked' : musicFindings.length > 0 ? 'revise' : 'pass';
  const blockerClass =
    runtimeBlockers.length > 0
      ? 'runtime'
      : validation.errors.length > 0
        ? 'contract'
        : analysis.status === 'blocked'
          ? 'analysis'
          : 'none';
  const provisional = analysis.readiness !== 'ready_for_critique';

  const payload = {
    phase: 'critique',
    gate,
    blocker_class: blockerClass,
    provisional,
    song: slug,
    run_dir: runDir,
    scores,
    runtime_blockers: runtimeBlockers,
    music_findings: musicFindings,
    retrieval_cards: referenceCards.map((card) => ({
      name: card.name,
      path: card.path,
      metadata_path: card.metadataPath,
      score: card.score,
      matched_terms: card.matchedTerms,
      metadata: card.metadata,
    })),
    provider_reviews: [providerReview],
    revision_actions: [...new Set(revisionActions)].map((action, index) => ({
      priority: index + 1,
      scope: runtimeBlockers.length > 0 ? 'runtime' : 'music',
      depends_on_blocker_resolution: runtimeBlockers.length > 0,
      action,
    })),
    summary:
      gate === 'pass'
        ? 'The song clears the current rubric with no major structural issues.'
        : gate === 'blocked'
          ? runtimeBlockers[0]?.title ?? 'Review blocked by runtime issues.'
          : musicFindings[0]?.title ?? 'Song needs revision.',
  };

  writeFileSync(join(runDir, 'critique.json'), `${JSON.stringify(payload, null, 2)}\n`);

  const revisionLines = [
    `# Revision Brief: ${validation.metadata.title ?? slug}`,
    '',
    `Primary goal: ${payload.summary}`,
    '',
    `Gate: ${gate}`,
    `Provisional: ${provisional ? 'yes' : 'no'}`,
    '',
    '## Top Scores',
    ...Object.entries(scores).map(([key, value]) => `- ${key}: ${value}`),
    '',
    '## Reference Cards',
    ...(referenceCards.length > 0 ? referenceCards.map((card) => `- ${card.name}`) : ['- none selected']),
    '',
    '## Revision Actions',
    ...(payload.revision_actions.length > 0
      ? payload.revision_actions.map((action) => `- ${action.action}`)
      : ['- No major fixes required. Preserve the arrangement and polish by ear.']),
  ];

  writeFileSync(join(runDir, 'revision.md'), `${revisionLines.join('\n')}\n`);

  return {
    phase: 'song:critique',
    status: gate === 'pass' ? 'ok' : gate,
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    gate,
    blocker_class: blockerClass,
    provisional,
    summary: payload.summary,
    runtime_blockers: runtimeBlockers,
    revision_actions: payload.revision_actions,
    message: `Wrote critique to ${join(runDir, 'critique.json')}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongCritique, process.argv.slice(2)));
}
