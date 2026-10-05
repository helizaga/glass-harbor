import { existsSync } from 'node:fs';

import {
  buildStyleRolePlan,
  buildPromptStyleLens,
  deriveGenerationStrategy,
  evaluateStyleProfileUsage,
  parseBrief,
  parsePromptReferences,
  readText,
  resolveStyleProfile,
  resolveSongSlug,
  selectExampleProfiles,
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
  const promptReferences = parsePromptReferences(brief);
  const promptStyleLens = buildPromptStyleLens(brief);
  const exampleProfiles = selectExampleProfiles(brief);
  const styleProfile = resolveStyleProfile(brief, { styleLens: promptStyleLens, exampleProfiles });
  const generationStrategy = deriveGenerationStrategy(brief, {
    exampleProfiles,
    styleLens: promptStyleLens,
    styleProfile,
  });
  const briefValidation = validateBrief(brief);
  const songValidation = validateSongCode(readText(paths.songPath));
  const styleProfileUsage = evaluateStyleProfileUsage({
    dependencies: songValidation.dependencies,
    strudelTechniques: songValidation.strudelTechniques,
    styleProfile,
  });
  const styleRolePlan = buildStyleRolePlan({
    styleProfile,
    dependencies: songValidation.dependencies,
    strudelTechniques: songValidation.strudelTechniques,
  });
  const errors = [...briefValidation.errors, ...songValidation.errors];
  const warnings = [...songValidation.warnings, ...(styleProfileUsage?.warnings ?? []), ...(styleRolePlan?.warnings ?? [])];

  return {
    phase: 'song:validate',
    status: errors.length > 0 ? 'failed' : 'ok',
    exitCode: errors.length > 0 ? EXIT_CODES.USAGE : EXIT_CODES.OK,
    song: slug,
    paths,
    metadata: songValidation.metadata,
    sections: songValidation.sections,
    section_roles: songValidation.sectionRoles,
    section_role_map: songValidation.sectionRoleMap,
    prompt_references: promptReferences,
    prompt_style_lens: promptStyleLens,
    style_profile: styleProfile,
    style_profile_usage: styleProfileUsage,
    style_role_plan: styleRolePlan,
    generation_strategy: generationStrategy,
    example_targets: exampleProfiles.map((entry) => entry.slug),
    dependencies: songValidation.dependencies,
    strudel_techniques: songValidation.strudelTechniques,
    technique_strengths: songValidation.strudelTechniques?.strengths ?? [],
    technique_opportunities: songValidation.strudelTechniques?.opportunities ?? [],
    errors,
    warnings,
    message:
      errors.length > 0 ? `Song validation failed for ${slug}` : `Song validation passed for ${slug}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongValidate, process.argv.slice(2)));
}
