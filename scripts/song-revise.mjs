import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  STABLE_SOUND_ROLES,
  parseBrief,
  readText,
  resolveRunDir,
  resolveSongSlug,
  selectReferenceCards,
  songPaths,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';

function referenceCardSummaries(critique, brief) {
  if (Array.isArray(critique.retrieval_cards) && critique.retrieval_cards.length > 0) {
    return critique.retrieval_cards.map((card) => ({
      name: card.name,
      path: card.path,
      metadata_path: card.metadata_path ?? card.metadataPath ?? null,
      matched_terms: card.matched_terms ?? card.matchedTerms ?? [],
      score: card.score ?? 0,
    }));
  }

  return selectReferenceCards(brief, 3).map((card) => ({
    name: card.name,
    path: card.path,
    metadata_path: card.metadataPath,
    matched_terms: card.matchedTerms,
    score: card.score,
  }));
}

function buildRevisionPrompt({ slug, brief, song, critique, references, runDir }) {
  const actions = critique.revision_actions ?? [];
  const scoreLines = Object.entries(critique.scores ?? {}).map(([key, value]) => `- ${key}: ${value}`);
  const referenceLines =
    references.length > 0
      ? references.map((card) => `- ${card.name}: ${card.path}`)
      : ['- none'];

  return [
    `# Revision Task: ${brief.title ?? slug}`,
    '',
    'Revise the canonical song file in place using the latest critique artifacts.',
    '',
    '## Target Files',
    `- brief: ${song.briefPath}`,
    `- song: ${song.songPath}`,
    '',
    '## Run Artifacts',
    `- run: ${join(runDir, 'run.json')}`,
    `- analysis: ${join(runDir, 'analysis.json')}`,
    `- critique: ${join(runDir, 'critique.json')}`,
    `- human summary: ${join(runDir, 'revision.md')}`,
    '',
    '## Required Constraints',
    '- keep the song directly pasteable into https://strudel.cc/ after `glass-harbor song serve`',
    '- preserve top metadata comments: @title, @genre, @bpm, @details, @sections',
    '- keep `samples(\'http://localhost:5432\')` as the runtime sample source',
    '- do not add repo-specific wrappers or imports to the song file',
    `- use only the stable sampled roles: ${STABLE_SOUND_ROLES.join(', ')}`,
    '- keep tonal parts readable and modular with named layer constants',
    '- revise the canonical song file, not a private vendor-specific copy',
    '',
    '## Critique Summary',
    `- gate: ${critique.gate ?? 'unknown'}`,
    `- blocker class: ${critique.blocker_class ?? 'none'}`,
    `- provisional: ${critique.provisional ? 'yes' : 'no'}`,
    `- summary: ${critique.summary ?? 'No summary available.'}`,
    '',
    '## Scores',
    ...(scoreLines.length > 0 ? scoreLines : ['- none']),
    '',
    '## Revision Actions',
    ...(actions.length > 0
      ? actions.map((action) => `- ${action.action}`)
      : ['- No specific revision actions were provided. Keep the current arrangement unless you find an obvious readability fix.']),
    '',
    '## Reference Cards',
    ...referenceLines,
    '',
    '## What To Do',
    '- Update only the canonical song file unless the brief itself is clearly out of sync.',
    '- Make the smallest set of changes that addresses the critique cleanly.',
    '- Preserve the emotional intent and structure unless the critique explicitly points to a structural problem.',
    '- If the critique already passes, make no musical changes and explain that the current version should stand.',
    '',
    '## After Editing',
    `- rerun: glass-harbor song loop ${slug} --max-iters 1 --json`,
    '- compare the new critique summary and scores against this run before doing another pass.',
  ].join('\n');
}

export async function handleSongRevise({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song revise <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const runDir = resolveRunDir(argv, slug) ?? '';
  const critiquePath = runDir ? join(runDir, 'critique.json') : '';
  if (!runDir || !existsSync(critiquePath)) {
    throw new CommandError(`No critique found for ${slug}. Run glass-harbor song critique ${slug} first.`, {
      exitCode: EXIT_CODES.ANALYSIS_BLOCKED,
      code: 'critique_missing',
    });
  }

  const song = songPaths(slug);
  if (!existsSync(song.briefPath) || !existsSync(song.songPath)) {
    throw new CommandError(`Missing brief or song file for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'song_missing',
      details: song,
    });
  }

  const brief = parseBrief(readText(song.briefPath));
  const critique = JSON.parse(readFileSync(critiquePath, 'utf8'));
  const references = referenceCardSummaries(critique, brief);
  const promptPath = join(runDir, 'revision-prompt.md');
  const requestPath = join(runDir, 'revision-request.json');
  const revisionActions = critique.revision_actions ?? [];
  const status = critique.gate === 'pass' || revisionActions.length === 0 ? 'noop' : 'ready';

  const requestPayload = {
    phase: 'revise',
    status,
    song: slug,
    run_dir: runDir,
    target: {
      brief_path: song.briefPath,
      song_path: song.songPath,
      edit_mode: 'in_place',
    },
    source: {
      brief_path: song.briefPath,
      song_path: song.songPath,
      run_path: join(runDir, 'run.json'),
      analysis_path: join(runDir, 'analysis.json'),
      critique_path: critiquePath,
      revision_summary_path: join(runDir, 'revision.md'),
    },
    critique: {
      gate: critique.gate ?? 'unknown',
      blocker_class: critique.blocker_class ?? 'none',
      provisional: critique.provisional ?? false,
      summary: critique.summary ?? null,
      scores: critique.scores ?? {},
      revision_actions: revisionActions,
    },
    constraints: {
      paste_target: 'https://strudel.cc/',
      sample_server_url: 'http://localhost:5432',
      required_metadata: ['title', 'genre', 'bpm', 'details', 'sections'],
      stable_sample_roles: STABLE_SOUND_ROLES,
      must_edit_in_place: true,
    },
    references,
    outputs: {
      prompt_path: promptPath,
      request_path: requestPath,
    },
  };

  const prompt = buildRevisionPrompt({ slug, brief, song, critique, references, runDir });
  writeFileSync(requestPath, `${JSON.stringify(requestPayload, null, 2)}\n`);
  writeFileSync(promptPath, `${prompt}\n`);

  return {
    phase: 'song:revise',
    status,
    exitCode: EXIT_CODES.OK,
    song: slug,
    run_dir: runDir,
    request_path: requestPath,
    prompt_path: promptPath,
    revision_actions: revisionActions,
    message:
      status === 'noop'
        ? `Revision package written for ${slug}; critique already passes, so no changes are currently recommended.`
        : `Prepared a revision package for ${slug} at ${requestPath}`,
  };
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongRevise, process.argv.slice(2)));
}
