import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  parseBrief,
  parseSongMetadata,
  readText,
  resolveSongSlug,
  sanitizeSlug,
  songPaths,
  titleFromSlug,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';

function parseCount(argv) {
  const index = argv.indexOf('--count');
  if (index === -1 || !argv[index + 1]) {
    return 3;
  }

  const count = Number.parseInt(argv[index + 1], 10);
  return Number.isFinite(count) && count > 0 ? count : Number.NaN;
}

function replaceFirstHeading(markdown, nextTitle) {
  if (/^#\s+.+$/m.test(markdown)) {
    return markdown.replace(/^#\s+.+$/m, `# ${nextTitle}`);
  }
  return `# ${nextTitle}\n\n${markdown}`.trimEnd();
}

function upsertMetadataLine(code, key, value) {
  const pattern = new RegExp(`^//\\s*@${key}\\s+.+$`, 'm');
  if (pattern.test(code)) {
    return code.replace(pattern, `// @${key} ${value}`);
  }
  return `// @${key} ${value}\n${code}`.trimEnd();
}

function variantTitle(baseTitle, index) {
  return `${baseTitle} Variant ${index}`;
}

export async function handleSongVariants({ argv }) {
  const sourceSlug = resolveSongSlug(argv);
  if (!sourceSlug) {
    throw new CommandError('Usage: glass-harbor song variants <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const count = parseCount(argv);
  if (!Number.isFinite(count)) {
    throw new CommandError('Variant count must be a positive integer.', {
      exitCode: EXIT_CODES.USAGE,
      code: 'invalid_variant_count',
    });
  }

  const force = argv.includes('--force');
  const source = songPaths(sourceSlug);
  if (!existsSync(source.briefPath) || !existsSync(source.songPath)) {
    throw new CommandError(`Missing source brief or song file for ${sourceSlug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'source_song_missing',
      details: source,
    });
  }

  const briefTemplate = readText(source.briefPath);
  const songTemplate = readText(source.songPath);
  const brief = parseBrief(briefTemplate);
  const metadata = parseSongMetadata(songTemplate);
  const baseTitle = brief.title || metadata.title || titleFromSlug(sourceSlug);
  const manifestPath = join(source.dir, 'variants.json');
  const variants = [];

  for (let index = 1; index <= count; index += 1) {
    const slug = sanitizeSlug(`${sourceSlug}-v${index}`);
    const label = `v${index}`;
    const title = variantTitle(baseTitle, index);
    const target = songPaths(slug);

    if (existsSync(target.dir) && !force) {
      throw new CommandError(`Variant folder already exists: ${target.dir}. Use --force to overwrite.`, {
        exitCode: EXIT_CODES.USAGE,
        code: 'variant_exists',
        details: target,
      });
    }

    if (existsSync(target.dir) && force) {
      rmSync(target.dir, { recursive: true, force: true });
    }

    mkdirSync(target.dir, { recursive: true });

    let briefContent = briefTemplate;
    let songContent = songTemplate;

    briefContent = replaceFirstHeading(briefContent, title);
    songContent = upsertMetadataLine(songContent, 'title', title);
    songContent = upsertMetadataLine(
      songContent,
      'details',
      `${metadata.details ?? `Pasteable Strudel song file for ${baseTitle}.`} Variant scaffold ${index} cloned from ${sourceSlug}.`,
    );

    writeFileSync(target.briefPath, `${briefContent.trimEnd()}\n`);
    writeFileSync(target.songPath, `${songContent.trimEnd()}\n`);
    variants.push({
      slug,
      label,
      variant_index: index,
      source_slug: sourceSlug,
      title,
      brief_path: target.briefPath,
      song_path: target.songPath,
      source_song_path: source.songPath,
    });
  }

  const manifest = {
    source_slug: sourceSlug,
    source_brief_path: source.briefPath,
    source_song_path: source.songPath,
    generated_at: new Date().toISOString(),
    variants,
  };
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

  return {
    phase: 'song:variants',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: sourceSlug,
    count,
    manifest_path: manifestPath,
    variants,
    messages: [
      `Scaffolded ${count} variant${count === 1 ? '' : 's'} for ${sourceSlug}.`,
      manifestPath,
      ...variants.map((variant) => `${variant.slug}: ${variant.song_path}`),
    ],
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongVariants, process.argv.slice(2)));
}
