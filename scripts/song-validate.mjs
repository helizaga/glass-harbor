import { existsSync } from 'node:fs';

import {
  parseBrief,
  readText,
  resolveSongSlug,
  songPaths,
  validateBrief,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';

export async function handleSongValidate({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song validate <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const paths = songPaths(slug);
  if (!existsSync(paths.briefPath) || !existsSync(paths.songPath)) {
    throw new CommandError(`Missing brief or song file for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'song_missing',
      details: paths,
    });
  }

  const brief = parseBrief(readText(paths.briefPath));
  const briefValidation = validateBrief(brief);
  const songValidation = validateSongCode(readText(paths.songPath));
  const errors = [...briefValidation.errors, ...songValidation.errors];

  return {
    phase: 'song:validate',
    status: errors.length > 0 ? 'failed' : 'ok',
    exitCode: errors.length > 0 ? EXIT_CODES.USAGE : EXIT_CODES.OK,
    song: slug,
    paths,
    metadata: songValidation.metadata,
    sections: songValidation.sections,
    errors,
    warnings: songValidation.warnings,
    message:
      errors.length > 0 ? `Song validation failed for ${slug}` : `Song validation passed for ${slug}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongValidate, process.argv.slice(2)));
}
