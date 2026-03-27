import '@strudel/repl';
import { renderPatternAudio } from '@strudel/webaudio';

import {
  buildSectionTimeline,
  parseSections,
  parseSongMetadata,
  sanitizeSlug,
} from '../lib/song-contract-browser.mjs';

const statusNode = document.querySelector('#status');
const params = new URLSearchParams(window.location.search);

window.__renderState = {
  status: 'booting',
  completed: 0,
  expected: 0,
  outputs: [],
  error: null,
};

function setStatus(status, message) {
  window.__renderState.status = status;
  statusNode.textContent = message;
}

async function fetchSongCode(songPath) {
  const response = await fetch(songPath);
  if (!response.ok) {
    throw new Error(`Unable to load song file: ${songPath}`);
  }
  return response.text();
}

async function waitForEditor(host) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 30000) {
    if (host.editor) {
      return host.editor;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error('Timed out waiting for Strudel editor to initialize.');
}

async function renderSong() {
  const songPath = params.get('song');
  if (!songPath) {
    throw new Error('Missing ?song=/songs/<slug>/<slug>.strudel.js query parameter.');
  }

  const songSlug = sanitizeSlug(params.get('slug') || songPath.split('/').at(-1)?.replace(/\.strudel\.js$/, ''));
  const code = await fetchSongCode(songPath);
  const metadata = parseSongMetadata(code);
  const sections = buildSectionTimeline(parseSections(metadata.sections));
  const totalCycles = sections.at(-1)?.end ?? 32;

  const replHost = document.createElement('strudel-editor');
  replHost.style.display = 'none';
  replHost.setAttribute('code', code);
  document.body.appendChild(replHost);

  const editor = await waitForEditor(replHost);
  await editor.evaluate(false);

  const pattern = editor.repl.state.pattern;
  if (!pattern) {
    throw new Error('Strudel evaluation completed without producing a pattern.');
  }

  const cps = editor.repl.scheduler.cps;
  window.__renderState.expected = sections.length + 1;
  window.__renderState.metadata = metadata;
  window.__renderState.sections = sections;
  window.__renderState.cps = cps;

  setStatus('rendering', `Rendering ${songSlug}: mix + ${sections.length} sections`);

  await renderPatternAudio(pattern, cps, 0, totalCycles, 44100, 48, false, 'mix');
  window.__renderState.completed += 1;
  window.__renderState.outputs.push('mix');

  for (const section of sections) {
    await renderPatternAudio(pattern, cps, section.begin, section.end, 44100, 48, false, `section-${section.name}`);
    window.__renderState.completed += 1;
    window.__renderState.outputs.push(section.name);
    setStatus('rendering', `Rendered section ${section.name} (${window.__renderState.completed}/${window.__renderState.expected})`);
  }

  await editor.stop?.();
  setStatus('done', `Rendered ${window.__renderState.completed} files for ${songSlug}`);
}

renderSong().catch((error) => {
  window.__renderState.status = 'error';
  window.__renderState.error = error.message;
  statusNode.textContent = error.stack || error.message;
});
