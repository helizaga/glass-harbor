import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { chromium } from 'playwright';

import { inspectRenderedWav } from '../lib/audio-integrity.mjs';
import {
  createRunDir,
  normalizeRuntimeErrors,
  readText,
  resolveSongSlug,
  songPaths,
  validateSongCode,
} from '../lib/song-contract.mjs';
import { CommandError, EXIT_CODES, isMainModule, runCliCommand } from '../lib/command-runtime.mjs';
import { commandName, ensureService, stopService } from '../lib/process-utils.mjs';

export async function handleSongRender({ argv }) {
  const slug = resolveSongSlug(argv);
  if (!slug) {
    throw new CommandError('Usage: glass-harbor song render <slug> or --song <slug>', {
      exitCode: EXIT_CODES.USAGE,
      code: 'usage_error',
    });
  }

  const song = songPaths(slug);
  const validation = validateSongCode(readText(song.songPath));
  if (validation.errors.length > 0) {
    throw new CommandError(`Song contract errors for ${slug}.`, {
      exitCode: EXIT_CODES.USAGE,
      code: 'song_contract_error',
      details: { errors: validation.errors, warnings: validation.warnings },
    });
  }

  const runDir = createRunDir(slug);
  mkdirSync(join(runDir, 'sections'), { recursive: true });

  const sampleService = await ensureService({
    name: 'sample server',
    url: 'http://127.0.0.1:5432/strudel.json',
    command: process.execPath,
    args: ['scripts/serve-active-pack.mjs', '--quiet'],
    cwd: process.cwd(),
  });

  const viteService = await ensureService({
    name: 'render harness',
    url: 'http://127.0.0.1:5173/render.html',
    command: commandName('npx'),
    args: ['vite', '--', '--host', '127.0.0.1', '--port', '5173'],
    cwd: process.cwd(),
  });

  const browser = await chromium.launch({ headless: true });
  const pageErrors = [];
  const savedOutputs = [];
  let preflight = null;
  let runtimeBlockers = [];
  const integrityIssues = [];

  const sectionTargetPaths = validation.sections.map((section) => join(runDir, 'sections', `${section.name}.wav`));

  const targets = [
    ...validation.sections.map((section) => ({
      output: `section-${section.name}`,
      begin: section.begin,
      end: section.end,
      targetPath: join(runDir, 'sections', `${section.name}.wav`),
    })),
  ];

  async function renderTarget(target) {
    const context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    page.setDefaultTimeout(300000);
    const downloads = [];
    const targetErrors = [];

    page.on('download', (download) => {
      downloads.push(download);
    });
    page.on('console', (message) => {
      if (message.type() === 'error') {
        targetErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      targetErrors.push(error.message);
    });

    try {
      await page.goto(
        `http://127.0.0.1:5173/render.html?song=${encodeURIComponent(`/songs/${slug}/${slug}.strudel.js`)}&slug=${encodeURIComponent(slug)}&begin=${encodeURIComponent(target.begin)}&end=${encodeURIComponent(target.end)}&output=${encodeURIComponent(target.output)}`,
        { waitUntil: 'domcontentloaded' },
      );

      await page.waitForFunction(() => {
        const state = window.__renderState;
        return state && (state.status === 'done' || state.status === 'error' || state.status === 'blocked');
      }, { timeout: 300000 });

      const renderState = await page.evaluate(() => window.__renderState);
      const expectedDownloads = renderState.status === 'done' ? renderState.expected ?? 0 : 0;
      const hasInlineWav = typeof renderState.rendered_wav_base64 === 'string' && renderState.rendered_wav_base64.length > 0;
      if (expectedDownloads > 0 && !hasInlineWav) {
        const startedAt = Date.now();
        while (downloads.length < expectedDownloads && Date.now() - startedAt < 300000) {
          await new Promise((resolve) => setTimeout(resolve, 200));
        }
      }

      if (renderState.status === 'error') {
        targetErrors.push(renderState.error);
      }

      if (expectedDownloads > 0 && downloads.length < expectedDownloads && !hasInlineWav) {
        targetErrors.push(`Expected ${expectedDownloads} downloads for ${target.output}, received ${downloads.length}.`);
      }

      if (renderState.status === 'done') {
        if (downloads[0]) {
          await downloads[0].saveAs(target.targetPath);
        } else if (hasInlineWav) {
          writeFileSync(target.targetPath, Buffer.from(renderState.rendered_wav_base64, 'base64'));
        }

        if (downloads[0] || hasInlineWav) {
          const inspection = inspectRenderedWav(target.targetPath);
          if (inspection.silent) {
            targetErrors.push(`Rendered output for ${target.output} is silent.`);
            integrityIssues.push({
              code: 'silent_render_output',
              surface: 'render_output',
              message: `Rendered output for ${target.output} is silent.`,
              name: target.output,
              count: 1,
              examples: [target.targetPath],
              inspection,
            });
          }
        }
      }

      return {
        renderState,
        targetErrors,
      };
    } finally {
      await context.close();
    }
  }

  try {
    for (const target of targets) {
      const result = await renderTarget(target);
      pageErrors.push(...result.targetErrors);
      preflight = preflight ?? result.renderState.preflight ?? null;

      if (result.renderState.status === 'done') {
        savedOutputs.push(target.targetPath);
        continue;
      }

      runtimeBlockers =
        result.renderState.runtime_blockers?.length > 0
          ? result.renderState.runtime_blockers
          : [...integrityIssues, ...normalizeRuntimeErrors(pageErrors, validation.dependencies)];
      break;
    }

    if (runtimeBlockers.length === 0 && (pageErrors.length > 0 || integrityIssues.length > 0)) {
      runtimeBlockers = [...integrityIssues, ...normalizeRuntimeErrors(pageErrors, validation.dependencies)];
    }

    if (runtimeBlockers.length === 0) {
      concatenateSectionWavs(sectionTargetPaths, join(runDir, 'mix.wav'));
      const mixInspection = inspectRenderedWav(join(runDir, 'mix.wav'));
      if (mixInspection.silent) {
        runtimeBlockers = [
          {
            code: 'silent_render_output',
            surface: 'render_output',
            message: 'Rendered output for mix is silent.',
            name: 'mix',
            count: 1,
            examples: [join(runDir, 'mix.wav')],
            inspection: mixInspection,
          },
        ];
      }
    }

    const status = runtimeBlockers.length > 0 ? 'blocked' : 'ok';
    if (status === 'blocked') {
      savedOutputs.forEach((filePath) => rmSync(filePath, { force: true }));
    }

    const payload = {
      phase: 'render',
      status,
      song: slug,
      generated_at: new Date().toISOString(),
      metadata: validation.metadata,
      sections: validation.sections,
      dependencies: validation.dependencies,
      preflight,
      runtime_blockers: runtimeBlockers,
      console_errors: pageErrors,
      env: {
        node: process.version,
        sample_server_url: 'http://127.0.0.1:5432/strudel.json',
        render_harness_url: 'http://127.0.0.1:5173/render.html',
      },
      services: [
        { name: sampleService.name, url: sampleService.url, reused: sampleService.reused },
        { name: viteService.name, url: viteService.url, reused: viteService.reused },
      ],
    };
    if (status === 'ok') {
      payload.outputs = {
        mix: join(runDir, 'mix.wav'),
        sections: sectionTargetPaths,
      };
    }

    writeFileSync(join(runDir, 'run.json'), `${JSON.stringify(payload, null, 2)}\n`);

    return {
      phase: 'song:render',
      status,
      exitCode: status === 'blocked' ? EXIT_CODES.RENDER_BLOCKED : EXIT_CODES.OK,
      song: slug,
      run_dir: runDir,
      baseline_run_dir: null,
      preflight: payload.preflight,
      runtime_blockers: runtimeBlockers,
      outputs: payload.outputs ?? null,
      recommended_next_action: status === 'blocked' ? 'revise' : null,
      approval_required: false,
      message:
        status === 'blocked'
          ? `Rendered ${slug} to ${runDir}, but the run is blocked by runtime issues.`
          : `Rendered ${slug} to ${runDir}`,
    };
  } finally {
    await browser.close();
    stopService(viteService.child);
    stopService(sampleService.child);
  }
}

if (isMainModule(import.meta.url)) {
  process.exit(await runCliCommand(handleSongRender, process.argv.slice(2)));
}

function concatenateSectionWavs(sectionPaths, outputPath) {
  const chunks = sectionPaths.map((filePath) => readFileSync(filePath));
  if (chunks.length === 0) {
    throw new Error('No section WAVs were available to assemble the mix.');
  }

  const first = chunks[0];
  if (first.length < 44) {
    throw new Error(`Section WAV is invalid: ${sectionPaths[0]}`);
  }

  const audioFormat = first.readUInt16LE(20);
  const numChannels = first.readUInt16LE(22);
  const sampleRate = first.readUInt32LE(24);
  const byteRate = first.readUInt32LE(28);
  const blockAlign = first.readUInt16LE(32);
  const bitDepth = first.readUInt16LE(34);

  const pcmChunks = chunks.map((buffer, index) => {
    if (buffer.length < 44) {
      throw new Error(`Section WAV is invalid: ${sectionPaths[index]}`);
    }
    if (
      buffer.readUInt16LE(20) !== audioFormat ||
      buffer.readUInt16LE(22) !== numChannels ||
      buffer.readUInt32LE(24) !== sampleRate ||
      buffer.readUInt32LE(28) !== byteRate ||
      buffer.readUInt16LE(32) !== blockAlign ||
      buffer.readUInt16LE(34) !== bitDepth
    ) {
      throw new Error(`Section WAV format mismatch: ${sectionPaths[index]}`);
    }
    return buffer.subarray(44);
  });

  const pcmLength = pcmChunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + pcmLength, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(audioFormat, 20);
  header.writeUInt16LE(numChannels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bitDepth, 34);
  header.write('data', 36);
  header.writeUInt32LE(pcmLength, 40);

  writeFileSync(outputPath, Buffer.concat([header, ...pcmChunks]));
}
