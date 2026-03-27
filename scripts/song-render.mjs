import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { chromium } from 'playwright';

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
    args: ['vite', '--host', '127.0.0.1', '--port', '5173'],
    cwd: process.cwd(),
  });

  const browser = await chromium.launch({ headless: true });
  const pageErrors = [];
  const savedOutputs = [];
  let preflight = null;
  let runtimeBlockers = [];

  const targets = [
    {
      output: 'mix',
      begin: 0,
      end: validation.sections.at(-1)?.end ?? 32,
      targetPath: join(runDir, 'mix.wav'),
    },
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
        { waitUntil: 'networkidle' },
      );

      await page.waitForFunction(() => {
        const state = window.__renderState;
        return state && (state.status === 'done' || state.status === 'error' || state.status === 'blocked');
      }, { timeout: 300000 });

      const renderState = await page.evaluate(() => window.__renderState);
      const expectedDownloads = renderState.status === 'done' ? renderState.expected ?? 0 : 0;
      if (expectedDownloads > 0) {
        const startedAt = Date.now();
        while (downloads.length < expectedDownloads && Date.now() - startedAt < 300000) {
          await new Promise((resolve) => setTimeout(resolve, 200));
        }
      }

      if (renderState.status === 'error') {
        targetErrors.push(renderState.error);
      }

      if (expectedDownloads > 0 && downloads.length < expectedDownloads) {
        targetErrors.push(`Expected ${expectedDownloads} downloads for ${target.output}, received ${downloads.length}.`);
      }

      if (renderState.status === 'done' && downloads[0]) {
        await downloads[0].saveAs(target.targetPath);
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
          : normalizeRuntimeErrors(pageErrors, validation.dependencies);
      break;
    }

    if (runtimeBlockers.length === 0 && pageErrors.length > 0) {
      runtimeBlockers = normalizeRuntimeErrors(pageErrors, validation.dependencies);
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
        sections: validation.sections.map((section) => join(runDir, 'sections', `${section.name}.wav`)),
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
