import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { assertInsideRoot } from '../lib/pack-overlay.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const args = process.argv.slice(2);

function readArg(name, fallback) {
  const index = args.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return args[index + 1] ?? fallback;
}

function ffprobeDuration(filePath) {
  return Number.parseFloat(
    execFileSync(
      'ffprobe',
      ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1', filePath],
      { encoding: 'utf8' },
    ).trim(),
  );
}

const sourceRoot = resolve(root, readArg('--source', 'private-packs/vendor-sources/local-drums/raw'));
const planPath = resolve(root, readArg('--plan', 'private-packs/vendor-sources/local-drums/prep-plan.json'));
const reportPath = resolve(root, readArg('--report', 'private-packs/vendor-sources/local-drums/prep-report.json'));

if (!existsSync(sourceRoot)) {
  throw new Error(`Missing source root at ${sourceRoot}. Run npm run drums:init first.`);
}

if (!existsSync(planPath)) {
  throw new Error(`Missing prep plan at ${planPath}.`);
}

const plan = JSON.parse(readFileSync(planPath, 'utf8'));
const defaults = plan.defaults ?? {};
const assets = plan.assets ?? [];
if (!Array.isArray(assets) || assets.length === 0) {
  throw new Error(`Prep plan ${planPath} does not define any assets.`);
}

const report = {
  generated_at: new Date().toISOString(),
  source_root: sourceRoot,
  plan_path: planPath,
  assets: [],
};

for (const asset of assets) {
  const sourcePath = resolve(sourceRoot, asset.source);
  const targetPath = resolve(sourceRoot, asset.target);
  assertInsideRoot(sourceRoot, sourcePath, `Prep source for ${asset.id ?? asset.target}`);
  assertInsideRoot(sourceRoot, targetPath, `Prep target for ${asset.id ?? asset.target}`);

  if (!existsSync(sourcePath)) {
    throw new Error(`Prep source does not exist: ${asset.source}`);
  }

  mkdirSync(dirname(targetPath), { recursive: true });

  const trimStart = asset.trim_start ?? defaults.trim_start ?? 0;
  const trimDuration = asset.trim_duration ?? defaults.trim_duration ?? null;
  const fadeInDuration = asset.fade_in_duration ?? defaults.fade_in_duration ?? 0;
  const fadeOutStart = asset.fade_out_start ?? defaults.fade_out_start ?? null;
  const fadeOutDuration = asset.fade_out_duration ?? defaults.fade_out_duration ?? null;
  const lowpassHz = asset.lowpass_hz ?? defaults.lowpass_hz ?? null;
  const highpassHz = asset.highpass_hz ?? defaults.highpass_hz ?? null;
  const gainDb = asset.gain_db ?? defaults.gain_db ?? null;
  const loudnorm = asset.loudnorm ?? defaults.loudnorm ?? null;

  const filters = [];
  if (highpassHz) {
    filters.push(`highpass=f=${highpassHz}`);
  }
  if (lowpassHz) {
    filters.push(`lowpass=f=${lowpassHz}`);
  }
  if (gainDb) {
    filters.push(`volume=${gainDb}dB`);
  }
  if (loudnorm && loudnorm.enabled !== false) {
    filters.push(
      `loudnorm=I=${loudnorm.i ?? -16}:TP=${loudnorm.tp ?? -1.5}:LRA=${loudnorm.lra ?? 11}`,
    );
  }
  if (fadeInDuration && fadeInDuration > 0) {
    filters.push(`afade=t=in:st=0:d=${fadeInDuration}`);
  }
  if (fadeOutStart !== null && fadeOutDuration !== null) {
    filters.push(`afade=t=out:st=${fadeOutStart}:d=${fadeOutDuration}`);
  }

  const ffmpegArgs = ['-y'];
  if (trimStart && trimStart > 0) {
    ffmpegArgs.push('-ss', `${trimStart}`);
  }
  ffmpegArgs.push('-i', sourcePath);
  if (trimDuration && trimDuration > 0) {
    ffmpegArgs.push('-t', `${trimDuration}`);
  }
  if (filters.length > 0) {
    ffmpegArgs.push('-af', filters.join(','));
  }
  ffmpegArgs.push(targetPath);

  execFileSync('ffmpeg', ffmpegArgs, { stdio: 'ignore' });

  report.assets.push({
    id: asset.id ?? asset.target,
    source: asset.source,
    target: asset.target,
    family: asset.family ?? null,
    duration_in: ffprobeDuration(sourcePath),
    duration_out: ffprobeDuration(targetPath),
    filters,
    source_file: relative(sourceRoot, sourcePath),
    target_file: relative(sourceRoot, targetPath),
  });
}

writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);

console.log('Prepared local pack source assets:');
console.log(`- source root: ${sourceRoot}`);
console.log(`- prep plan: ${planPath}`);
console.log(`- prep report: ${reportPath}`);
console.log(`- generated assets: ${report.assets.length}`);
