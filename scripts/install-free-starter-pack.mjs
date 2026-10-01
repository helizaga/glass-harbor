import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const packRoot = join(root, 'samples', 'edm-core');

const curatedAssets = [
  {
    role: 'impact_wide',
    index: 1,
    title: 'Movie trailer epic impact',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/2908/2908.wav',
    page: 'https://mixkit.co/free-sound-effects/impact/',
    license: 'Mixkit License',
  },
  {
    role: 'impact_wide',
    index: 2,
    title: 'Cinematic whoosh deep impact',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/1143/1143.mp3',
    page: 'https://mixkit.co/free-sound-effects/impact/',
    license: 'Mixkit License',
  },
  {
    role: 'riser_up',
    index: 1,
    title: 'Cinematic wind swoosh',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/1471/1471.wav',
    page: 'https://mixkit.co/free-sound-effects/wind/',
    license: 'Mixkit License',
  },
  {
    role: 'shimmer_fx',
    index: 1,
    title: 'Fairy magic sparkle',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/871/871.wav',
    page: 'https://mixkit.co/free-sound-effects/sparkle/',
    license: 'Mixkit License',
  },
  {
    role: 'air_texture',
    index: 1,
    title: 'Ambient sound in the desert',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/2488/2488.wav',
    page: 'https://mixkit.co/free-sound-effects/ambient/',
    license: 'Mixkit License',
  },
  {
    role: 'vocal_chop',
    index: 1,
    title: 'Futuristic glitch robot',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/1039/1039.wav',
    page: 'https://mixkit.co/free-sound-effects/glitch/',
    license: 'Mixkit License',
  },
  {
    role: 'perc_top',
    index: 2,
    title: 'Drum and percussion',
    source: 'Mixkit',
    url: 'https://assets.mixkit.co/active_storage/sfx/545/545.wav',
    page: 'https://mixkit.co/free-sound-effects/percussion/',
    license: 'Mixkit License',
  },
];

function ensureDir(dirPath) {
  mkdirSync(dirPath, { recursive: true });
}

async function downloadFile(url, destination) {
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0',
      Referer: 'https://mixkit.co/',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to download ${url}: ${response.status} ${response.statusText}`);
  }

  const data = Buffer.from(await response.arrayBuffer());
  writeFileSync(destination, data);
}

function convertAudio(inputPath, outputPath) {
  const result = spawnSync(
    'ffmpeg',
    ['-y', '-i', inputPath, '-ar', '44100', '-ac', '1', '-af', 'loudnorm=I=-18:TP=-1.5:LRA=11', outputPath],
    { stdio: 'pipe' },
  );

  if (result.status !== 0) {
    throw new Error(`ffmpeg failed for ${inputPath}: ${result.stderr?.toString() ?? 'unknown error'}`);
  }
}

async function main() {
  const tempRoot = mkdtempSync(join(tmpdir(), 'glass-harbor-free-pack-'));
  const manifest = {
    generated_at: new Date().toISOString(),
    note: 'Curated free starter-pack additions. Synthetic drum core is preserved; curated free assets are added as alternates.',
    roles: {},
  };

  try {
    for (const asset of curatedAssets) {
      const roleDir = join(packRoot, asset.role);
      const outputPath = join(roleDir, `${asset.index}.wav`);
      const tempPath = join(tempRoot, `${asset.role}-${asset.index}${asset.url.endsWith('.mp3') ? '.mp3' : '.wav'}`);

      ensureDir(roleDir);
      await downloadFile(asset.url, tempPath);
      convertAudio(tempPath, outputPath);

      if (!manifest.roles[asset.role]) {
        manifest.roles[asset.role] = [];
      }
      manifest.roles[asset.role].push({
        index: asset.index,
        title: asset.title,
        source: asset.source,
        page: asset.page,
        url: asset.url,
        license: asset.license,
        path: `samples/edm-core/${asset.role}/${asset.index}.wav`,
      });
    }

    writeFileSync(join(packRoot, 'free-starter-pack.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
}

await main();
