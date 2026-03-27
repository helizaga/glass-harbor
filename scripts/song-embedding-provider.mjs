import { join } from 'node:path';

import { repoRoot } from '../lib/song-contract.mjs';
import { runPythonJson } from '../lib/python-runtime.mjs';

function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function normalizeSimilarity(value) {
  return clamp((Number(value) + 1) / 2);
}

function fallbackAlignment({ analysis, brief, references }) {
  const rhythm = analysis.rhythm ?? {};
  const structure = analysis.structure ?? {};
  const tonal = analysis.tonal ?? {};
  const overlap = references.length > 0 ? Math.min(1, (references[0].score ?? 0) / 24) : 0;
  const bpm = Number(analysis.declared_bpm ?? 0);
  const bpmFit = bpm > 0 ? clamp(1 - Math.abs(bpm - 122) / 14) : 0.5;
  const grooveFit = clamp((rhythm.groove_continuity ?? 0) * 0.6 + (rhythm.onset_to_beat_alignment ?? 0) * 0.4);
  const structureFit = clamp(
    (structure.repetition_variation_balance ?? 0) * 0.5 +
      (structure.boundary_strength_proxy ?? 0) * 0.25 +
      (tonal.harmonic_stability ?? 0) * 0.25,
  );
  const overall = round(overlap * 0.45 + bpmFit * 0.15 + grooveFit * 0.2 + structureFit * 0.2);

  return {
    provider: 'none',
    status: 'fallback',
    overall,
    audio_to_brief: overall,
    top_reference: references[0]
      ? {
          name: references[0].name,
          similarity: round(overlap),
        }
      : null,
    reference_scores: references.map((card) => ({
      name: card.name,
      similarity: round(Math.min(1, (card.score ?? 0) / 24)),
    })),
    section_scores: [],
    confidence_notes: ['Embedding provider unavailable; using deterministic style-alignment fallback.'],
  };
}

export async function computeEmbeddingAlignment({ analysis, brief, references, runDir }) {
  const provider = (process.env.GLASS_HARBOR_EMBEDDING_PROVIDER ?? 'none').trim().toLowerCase();
  const fallback = fallbackAlignment({ analysis, brief, references });
  if (!provider || provider === 'none') {
    return fallback;
  }

  if (provider !== 'mulan') {
    return {
      ...fallback,
      provider,
      status: 'unavailable',
      confidence_notes: [`Unknown embedding provider "${provider}". Falling back to deterministic style alignment.`],
    };
  }

  const request = {
    provider,
    run_dir: runDir,
    mix_path: join(runDir, 'mix.wav'),
    sections_dir: join(runDir, 'sections'),
    brief: {
      title: brief.title ?? '',
      genre: brief.genre ?? '',
      mood: brief.mood ?? '',
      structure: brief.structure ?? '',
      sonic_goals: brief['sonic-goals'] ?? '',
      review_goals: brief['review-goals'] ?? '',
      notes_for_agent: brief['notes-for-agent'] ?? '',
    },
    references: references.map((card) => ({
      name: card.name,
      text: card.content,
      metadata: card.metadata,
    })),
  };

  try {
    const response = await runPythonJson(join(repoRoot, 'scripts', 'song-embedding-mulan.py'), request);
    if (response.status !== 'ok') {
      return {
        ...fallback,
        provider: response.provider ?? 'mulan',
        status: response.status ?? 'unavailable',
        confidence_notes: [...(fallback.confidence_notes ?? []), ...(response.confidence_notes ?? [])],
      };
    }

    return {
      provider: 'mulan',
      status: 'ok',
      overall: round(normalizeSimilarity(response.audio_to_brief)),
      audio_to_brief: round(normalizeSimilarity(response.audio_to_brief)),
      top_reference: response.top_reference
        ? {
            name: response.top_reference.name,
            similarity: round(normalizeSimilarity(response.top_reference.similarity)),
          }
        : null,
      reference_scores: (response.reference_scores ?? []).map((entry) => ({
        name: entry.name,
        similarity: round(normalizeSimilarity(entry.similarity)),
      })),
      section_scores: (response.section_scores ?? []).map((entry) => ({
        section: entry.section,
        reference: entry.reference,
        similarity: round(normalizeSimilarity(entry.similarity)),
      })),
      confidence_notes: response.confidence_notes ?? [],
    };
  } catch (error) {
    return {
      ...fallback,
      provider: 'mulan',
      status: 'unavailable',
      confidence_notes: [...(fallback.confidence_notes ?? []), `MuLan provider failed: ${error.message}`],
    };
  }
}
