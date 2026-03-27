import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { repoRoot, resolveSongSlug, songPaths, titleFromSlug } from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';

export async function handleSongNew({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song new <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const force = argv.includes('--force');
  const paths = songPaths(slug);

  if (existsSync(paths.dir) && !force) {
    throw new CommandError(`Song folder already exists: ${paths.dir}. Use --force to overwrite templates.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'song_exists',
    });
  }

  mkdirSync(paths.dir, { recursive: true });

  const briefTemplate = readFileSync(join(repoRoot, 'songs', 'song-template.brief.md'), 'utf8').replace(
    /^# Title$/m,
    `# ${titleFromSlug(slug)}`,
  );
  writeFileSync(paths.briefPath, briefTemplate);

  const songTemplate = readFileSync(join(repoRoot, 'songs', 'song-template.strudel.js'), 'utf8')
    .replace('// @title Replace Me', `// @title ${titleFromSlug(slug)}`)
    .replace('// @genre replace me', '// @genre sketch')
    .replace('// @details Pasteable Strudel song file. Run `glass-harbor song serve` before pasting into Strudel web.', `// @details Pasteable Strudel song file for ${titleFromSlug(slug)}. Run \`glass-harbor song serve\` before pasting into Strudel web.`);
  writeFileSync(paths.songPath, songTemplate);

  return {
    phase: 'song:new',
    status: 'ok',
    exitCode: EXIT_CODES.OK,
    song: slug,
    paths,
    messages: [`Scaffolded ${slug}`, paths.briefPath, paths.songPath],
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongNew, process.argv.slice(2)));
}
