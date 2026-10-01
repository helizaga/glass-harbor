export const CALIBRATION_METRICS = {
  estimated_tempo: { family: 'rhythm', deadband: 4, weight: 0.14 },
  groove_continuity: { family: 'rhythm', deadband: 0.06, weight: 0.2 },
  syncopation_proxy: { family: 'rhythm', deadband: 0.08, weight: 0.1 },
  inter_beat_loudness_consistency: { family: 'rhythm', deadband: 0.08, weight: 0.14 },
  harmonic_stability: { family: 'tonal', deadband: 0.08, weight: 0.1 },
  chord_change_proxy: { family: 'tonal', deadband: 0.08, weight: 0.08 },
  sub_energy_ratio: { family: 'timbre', deadband: 0.03, weight: 0.08 },
  bass_energy_ratio: { family: 'timbre', deadband: 0.04, weight: 0.08 },
  spectral_centroid: { family: 'timbre', deadband: 350, weight: 0.08 },
};

const EXAMPLE_CLIP_ROLES = ['anchor', 'groove', 'lift', 'breath', 'return', 'outro'];

export function round(value) {
  return Number((Number(value) || 0).toFixed(3));
}

export function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

export function average(values = []) {
  return values.length > 0 ? values.reduce((sum, value) => sum + Number(value ?? 0), 0) / values.length : 0;
}

export function confidenceLabel(score) {
  if (score >= 0.8) {
    return 'high';
  }
  if (score >= 0.6) {
    return 'medium';
  }
  return 'low';
}

export function buildSignalReliability({ analysis, anomalies = [], extraNotes = [] }) {
  const richEngine = analysis.analysis_engine === 'librosa-rich';
  const duration = Number(analysis.metrics?.duration_seconds ?? analysis.mix?.duration_seconds ?? 0);
  const beats = Number(analysis.rhythm?.beats_count ?? 0);
  const notes = [...new Set([...(analysis.confidence_notes ?? []), ...extraNotes])];

  let score = 0;
  score += richEngine ? 0.38 : 0.14;
  score += clamp(duration / 32, 0, 1) * 0.2;
  score += clamp(beats / 16, 0, 1) * 0.18;
  score += clamp((analysis.rhythm?.tempo_confidence ?? 0) * 0.14);
  score += anomalies.length === 0 ? 0.1 : 0.04;

  if (notes.length >= 3) {
    score -= 0.08;
  } else if (notes.length > 0) {
    score -= 0.04;
  }

  return {
    overall: round(clamp(score)),
    level: confidenceLabel(score),
    analysis_engine: analysis.analysis_engine ?? 'unknown',
    notes,
  };
}

export function buildMetricReliability({ analysis, signalReliability }) {
  const duration = Number(analysis.metrics?.duration_seconds ?? analysis.mix?.duration_seconds ?? 0);
  const beats = Number(analysis.rhythm?.beats_count ?? 0);
  const base = Number(signalReliability?.overall ?? 0.5);
  const rhythm = clamp(base * 0.55 + clamp(beats / 12, 0, 1) * 0.45);
  const structure = clamp(base * 0.55 + clamp(duration / 24, 0, 1) * 0.45);
  const tonal = clamp(base * 0.75 + clamp(analysis.tonal?.key_center_stability ?? 0) * 0.25);
  const timbre = clamp(base * 0.9 + 0.1);

  return {
    rhythm: { overall: round(rhythm), level: confidenceLabel(rhythm) },
    structure: { overall: round(structure), level: confidenceLabel(structure) },
    tonal: { overall: round(tonal), level: confidenceLabel(tonal) },
    timbre: { overall: round(timbre), level: confidenceLabel(timbre) },
  };
}

export function inferExampleClipRole(stem) {
  const slug = `${stem ?? ''}`.toLowerCase();
  return EXAMPLE_CLIP_ROLES.find((role) => slug.includes(role)) ?? 'reference';
}

export function parseNumericRange(text, fallbackCenter = 0) {
  const raw = `${text ?? ''}`.trim();
  const rangeMatch = raw.match(/(\d{2,3})\s*[-–]\s*(\d{2,3})/);
  if (rangeMatch) {
    return {
      min: Number(rangeMatch[1]),
      max: Number(rangeMatch[2]),
      source: 'text',
    };
  }

  const singleMatch = raw.match(/(\d{2,3})/);
  if (singleMatch) {
    const center = Number(singleMatch[1]);
    return {
      min: center - 2,
      max: center + 2,
      source: 'text',
    };
  }

  if (fallbackCenter > 0) {
    return {
      min: Math.max(0, round(fallbackCenter - 2)),
      max: round(fallbackCenter + 2),
      source: 'analysis',
    };
  }

  return null;
}

function calibrationTargetsFromProfile(profile = {}) {
  return profile.calibration_targets ?? {};
}

export function buildCalibrationProfile({ brief, exampleProfiles = [], declaredBpm = 0, promptStyleLens = null }) {
  const metricBands = {};
  if (promptStyleLens?.bpmPreference?.center) {
    metricBands.estimated_tempo = {
      center: round(promptStyleLens.bpmPreference.center),
      deadband: round(promptStyleLens.bpmPreference.deadband ?? 4),
      source_count: 0,
      family: 'rhythm',
      weight: CALIBRATION_METRICS.estimated_tempo.weight,
    };
  } else if (declaredBpm > 0) {
    metricBands.estimated_tempo = {
      center: declaredBpm,
      deadband: 4,
      source_count: 0,
      family: 'rhythm',
      weight: CALIBRATION_METRICS.estimated_tempo.weight,
    };
  }

  if (promptStyleLens?.metricTargets) {
    for (const [metric, target] of Object.entries(promptStyleLens.metricTargets)) {
      if (!CALIBRATION_METRICS[metric] || !Number.isFinite(Number(target))) {
        continue;
      }
      metricBands[metric] = {
        center: round(target),
        deadband: round(CALIBRATION_METRICS[metric].deadband * (metric === 'estimated_tempo' ? 1 : 1.25)),
        source_count: 0,
        family: CALIBRATION_METRICS[metric].family,
        weight: CALIBRATION_METRICS[metric].weight,
      };
    }
  }

  if (exampleProfiles.length === 0) {
    return {
      source: promptStyleLens ? 'prompt-references' : 'brief',
      example_targets: [],
      prompt_reference_labels: promptStyleLens?.references?.map((entry) => entry.label) ?? [],
      inferred_lanes: promptStyleLens?.inferredLanes ?? [],
      metric_bands: metricBands,
    };
  }

  for (const [metric, config] of Object.entries(CALIBRATION_METRICS)) {
    const values = exampleProfiles
      .map((entry) => Number(calibrationTargetsFromProfile(entry.profile)[metric]))
      .filter((value) => Number.isFinite(value));
    if (values.length === 0) {
      continue;
    }

    const center = average(values);
    const variance = average(values.map((value) => (value - center) ** 2));
    metricBands[metric] = {
      center: round(center),
      deadband: round(Math.max(config.deadband, Math.sqrt(variance))),
      source_count: values.length,
      family: config.family,
      weight: config.weight,
    };
  }

  return {
    source: 'examples',
    example_targets: exampleProfiles.map((entry) => entry.slug),
    prompt_reference_labels: promptStyleLens?.references?.map((entry) => entry.label) ?? [],
    inferred_lanes: promptStyleLens?.inferredLanes ?? [],
    metric_bands: metricBands,
    brief_title: brief?.title ?? null,
  };
}

export function scoreCalibrationAlignment({ analysis, calibrationProfile, metricReliability }) {
  const metricBands = calibrationProfile?.metric_bands ?? {};
  const metrics = {
    estimated_tempo: Number(analysis.rhythm?.estimated_tempo ?? 0),
    groove_continuity: Number(analysis.rhythm?.groove_continuity ?? 0),
    syncopation_proxy: Number(analysis.rhythm?.syncopation_proxy ?? 0),
    inter_beat_loudness_consistency: Number(analysis.rhythm?.inter_beat_loudness_consistency ?? 0),
    harmonic_stability: Number(analysis.tonal?.harmonic_stability ?? 0),
    chord_change_proxy: Number(analysis.tonal?.chord_change_proxy ?? 0),
    sub_energy_ratio: Number(analysis.timbre?.sub_energy_ratio ?? 0),
    bass_energy_ratio: Number(analysis.timbre?.bass_energy_ratio ?? 0),
    spectral_centroid: Number(analysis.timbre?.spectral_centroid ?? 0),
  };

  const comparisons = [];
  for (const [metric, band] of Object.entries(metricBands)) {
    const value = metrics[metric];
    if (!Number.isFinite(value)) {
      continue;
    }
    const distance = Math.abs(value - Number(band.center ?? 0));
    const familyReliability = Number(metricReliability?.[band.family]?.overall ?? 0.5);
    const fit = clamp(1 - distance / Math.max(Number(band.deadband ?? 0.1) * 2, 0.0001));
    comparisons.push({
      metric,
      family: band.family,
      value: round(value),
      center: round(band.center),
      deadband: round(band.deadband),
      fit: round(fit),
      weight: Number(band.weight ?? 0.1),
      reliability: round(familyReliability),
    });
  }

  if (comparisons.length === 0) {
    return {
      overall: 0.5,
      comparisons: [],
    };
  }

  const weighted = comparisons.reduce((sum, entry) => sum + entry.fit * entry.weight * entry.reliability, 0);
  const totalWeight = comparisons.reduce((sum, entry) => sum + entry.weight * entry.reliability, 0) || 1;
  return {
    overall: round(weighted / totalWeight),
    comparisons,
  };
}
