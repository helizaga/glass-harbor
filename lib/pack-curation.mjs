import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';

import { repoRoot } from './song-contract.mjs';
import { summarizeOverlayMap } from './pack-overlay.mjs';

const curationRoot = join(repoRoot, 'private-packs', 'curation');
const outcomesPath = join(curationRoot, 'outcomes.json');
const pairwisePath = join(curationRoot, 'pairwise.json');

function readJson(filePath, fallback) {
  if (!existsSync(filePath)) {
    return fallback;
  }

  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJson(filePath, payload) {
  mkdirSync(curationRoot, { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function loadOverlayState() {
  const candidates = [
    {
      id: 'local-drums',
      mapPath: join(repoRoot, 'private-packs', 'vendor-sources', 'local-drums', 'import-map.json'),
    },
    {
      id: 'kshmr-vol-4',
      mapPath: join(repoRoot, 'private-packs', 'vendor-sources', 'kshmr-vol-4', 'import-map.json'),
    },
  ];

  const overlays = candidates
    .map((candidate) => {
      const summary = summarizeOverlayMap(candidate.mapPath);
      if (!summary || Object.keys(summary.enabled_families).length === 0) {
        return null;
      }
      return {
        id: candidate.id,
        ...summary,
      };
    })
    .filter(Boolean);

  return overlays[0] ?? null;
}

export function recordPackOutcome({ song, runDir, baselineRunDir, verdict = {}, critique = null }) {
  const overlay = loadOverlayState();
  if (!overlay) {
    return null;
  }

  mkdirSync(curationRoot, { recursive: true });
  const outcomes = readJson(outcomesPath, []);
  const pairwise = readJson(pairwisePath, []);
  writeJson(pairwisePath, pairwise);

  const record = {
    song,
    run_dir: runDir,
    baseline_run_dir: baselineRunDir ?? null,
    recorded_at: new Date().toISOString(),
    overlay: {
      id: overlay.id,
      map_path: overlay.map_path,
      enabled_families: overlay.enabled_families,
    },
    decision: {
      verdict: verdict.verdict ?? null,
      summary: verdict.summary ?? critique?.summary ?? null,
      recommended_next_action: verdict.recommended_next_action ?? null,
      approval_required: verdict.approval_required ?? null,
    },
    scores: critique?.scores ?? null,
    change_summary: verdict.change_summary ?? null,
    regression_flags: verdict.regression_flags ?? [],
  };

  const nextOutcomes = outcomes.filter((entry) => entry.run_dir !== runDir);
  nextOutcomes.push(record);
  writeJson(outcomesPath, nextOutcomes);

  if (baselineRunDir) {
    const baselineRecord = nextOutcomes.find((entry) => entry.run_dir === baselineRunDir);
    if (baselineRecord?.overlay) {
      const changedFamilies = [];
      const allFamilies = new Set([
        ...Object.keys(baselineRecord.overlay.enabled_families ?? {}),
        ...Object.keys(record.overlay.enabled_families ?? {}),
      ]);

      for (const family of [...allFamilies].sort()) {
        const before = (baselineRecord.overlay.enabled_families?.[family] ?? []).map((entry) => entry.file).join('|');
        const after = (record.overlay.enabled_families?.[family] ?? []).map((entry) => entry.file).join('|');
        if (before !== after) {
          changedFamilies.push({
            family,
            before_files: baselineRecord.overlay.enabled_families?.[family] ?? [],
            after_files: record.overlay.enabled_families?.[family] ?? [],
          });
        }
      }

      if (changedFamilies.length > 0) {
        const weightedDelta = verdict.change_summary?.weighted_delta ?? null;
        pairwise.push({
          song,
          baseline_run_dir: baselineRunDir,
          current_run_dir: runDir,
          recorded_at: new Date().toISOString(),
          winner: weightedDelta !== null && weightedDelta > 0 ? 'current' : 'baseline',
          weighted_delta: weightedDelta,
          changed_families: changedFamilies,
          top_metric_changes: verdict.change_summary?.top_metric_changes ?? [],
          recommended_next_action: verdict.recommended_next_action ?? null,
        });
        writeJson(pairwisePath, pairwise);
      }
    }
  }

  const runOutcomePath = join(runDir, 'pack-outcome.json');
  writeJson(runOutcomePath, record);
  return {
    outcomes_path: outcomesPath,
    pairwise_path: pairwisePath,
    run_outcome_path: runOutcomePath,
    overlay_id: overlay.id,
  };
}
