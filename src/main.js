import '@strudel/repl';
import './style.css';

const PUBLIC_PACK_URL = '/samples/edm-core/strudel.json';
const PRIVATE_PACK_URL = '/private-packs/runtime/edm-core/strudel.json';
const AUTHORED_PACK_URL = 'http://localhost:5432';
const REQUIRED_PACK_FAMILIES = [
  'kick_main',
  'clap_main',
  'hat_closed',
  'hat_open',
  'perc_top',
  'impact_wide',
  'riser_up',
  'shimmer_fx',
  'air_texture',
  'vocal_chop',
];

const tracks = [
  {
    id: 'song',
    label: 'Glass Harbor Song',
    path: '/songs/glass-harbor/glass-harbor.strudel.js',
    description: 'Primary pasteable song artifact for Strudel web and local debugging.',
  },
  {
    id: 'superdirt',
    label: 'SuperDirt Debug',
    path: '/tracks/glass-harbor.superdirt.strudel.js',
    description: 'Optional local debug surface for OSC and SuperDirt verification.',
  },
  {
    id: 'preload',
    label: 'Pack Preload',
    path: '/tracks/edm-pack-preload.strudel.js',
    description: 'Quiet warm-up pass to load hero samples before the real take.',
  },
];

const packModes = [
  {
    id: 'auto',
    label: 'Auto',
    description: 'Use the private overlay if available, otherwise fall back to the public scaffold.',
  },
  {
    id: 'public',
    label: 'Public Scaffold',
    description: 'Force the committed placeholder pack under samples/edm-core.',
  },
  {
    id: 'private',
    label: 'Private Overlay',
    description: 'Force the gitignored imported commercial pack under private-packs/runtime.',
  },
];

const app = document.querySelector('#app');
const savedTrack = window.localStorage.getItem('glass-harbor-track');
const savedPackMode = window.localStorage.getItem('glass-harbor-pack-mode');
const defaultTrack = tracks.find((track) => track.id === savedTrack) ?? tracks[0];
const defaultPackMode = packModes.find((mode) => mode.id === savedPackMode) ?? packModes[0];

app.innerHTML = `
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">Strudel + SuperDirt</p>
      <h1>Glass Harbor</h1>
      <p class="lede">
        Paste-first songwriting scaffold for agent-generated Strudel songs. This browser app is a debug runner, not the primary workflow.
      </p>
    </section>

    <section class="toolbar">
      <div class="control-stack">
        <div>
          <p class="control-label">Track</p>
          <div class="track-picker" role="tablist" aria-label="Track selection">
            ${tracks
              .map(
                (track) => `
                  <button class="track-button" data-track="${track.id}" role="tab">
                    ${track.label}
                  </button>
                `,
              )
              .join('')}
          </div>
        </div>
        <div>
          <p class="control-label">Pack</p>
          <div class="pack-picker" role="tablist" aria-label="Pack selection">
            ${packModes
              .map(
                (mode) => `
                  <button class="pack-button" data-pack-mode="${mode.id}" role="tab">
                    ${mode.label}
                  </button>
                `,
              )
              .join('')}
          </div>
        </div>
      </div>
      <div class="status">
        <p id="track-label"></p>
        <p id="track-description"></p>
        <p id="pack-label"></p>
      </div>
    </section>

    <section class="notes">
      <div>
        <h2>Session Flow</h2>
        <p>Primary workflow: run <code>glass-harbor song serve</code>, paste a file from <code>songs/</code> into Strudel web, then use this app only when you want local debugging.</p>
      </div>
      <div>
        <h2>Review Loop</h2>
        <p>For agent review, use <code>glass-harbor song render</code>, <code>glass-harbor song analyze</code>, and <code>glass-harbor song critique</code>. They produce gitignored run artifacts under <code>runs/</code>.</p>
      </div>
      <div>
        <h2>Samples</h2>
        <p>Authored song files target <code>http://localhost:5432</code> for paste mode. This debug runner rewrites that to the active scaffold or private overlay manifest automatically.</p>
      </div>
      <div>
        <h2>Debug</h2>
        <p>Use <code>npm run osc</code> plus the <code>SuperDirt Debug</code> tab when you want to verify the external sound engine path for a generated song.</p>
      </div>
    </section>

    <section class="editor-frame">
      <div id="repl-root"></div>
    </section>
  </main>
`;

const replRoot = document.querySelector('#repl-root');
const trackLabel = document.querySelector('#track-label');
const trackDescription = document.querySelector('#track-description');
const packLabel = document.querySelector('#pack-label');
const trackButtons = [...document.querySelectorAll('.track-button')];
const packButtons = [...document.querySelectorAll('.pack-button')];
let activeLoadRequest = 0;

function renderError(error) {
  const pre = document.createElement('pre');
  pre.className = 'error';
  pre.textContent = error.message;
  replRoot.replaceChildren(pre);
}

function updateControls(track, packMode, packLabelText) {
  trackLabel.textContent = track.label;
  trackDescription.textContent = `${track.description} Source: ${track.path}`;
  packLabel.textContent = `Pack: ${packLabelText}`;

  trackButtons.forEach((button) => {
    const isActive = button.dataset.track === track.id;
    button.dataset.active = isActive ? 'true' : 'false';
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  packButtons.forEach((button) => {
    const isActive = button.dataset.packMode === packMode.id;
    button.dataset.active = isActive ? 'true' : 'false';
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
}

async function packManifestAvailable(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return false;
    }

    const manifest = await response.json();
    return REQUIRED_PACK_FAMILIES.every(
      (family) => Array.isArray(manifest[family]) && manifest[family].length > 0,
    );
  } catch {
    return false;
  }
}

async function resolvePackUrl(modeId) {
  if (modeId === 'public') {
    return { url: PUBLIC_PACK_URL, label: 'Public scaffold pack' };
  }
  if (modeId === 'private') {
    const hasPrivatePack = await packManifestAvailable(PRIVATE_PACK_URL);
    if (!hasPrivatePack) {
      throw new Error('Private overlay is unavailable or incomplete. Run npm run vendor:import or switch back to the public scaffold.');
    }
    return { url: PRIVATE_PACK_URL, label: 'Private commercial overlay' };
  }

  const hasPrivatePack = await packManifestAvailable(PRIVATE_PACK_URL);
  return hasPrivatePack
    ? { url: PRIVATE_PACK_URL, label: 'Auto: private commercial overlay' }
    : { url: PUBLIC_PACK_URL, label: 'Auto: public scaffold pack' };
}

async function loadTrack(track, packMode, requestId) {
  const response = await fetch(track.path);
  if (!response.ok) {
    throw new Error(`Unable to load ${track.path}`);
  }

  const packSelection = await resolvePackUrl(packMode.id);
  const code = (await response.text())
    .replaceAll('__SAMPLE_PACK_URL__', packSelection.url)
    .replaceAll("'http://localhost:5432'", `'${packSelection.url}'`)
    .replaceAll('"http://localhost:5432"', `"${packSelection.url}"`);
  if (requestId !== activeLoadRequest) {
    return;
  }

  const repl = document.createElement('strudel-editor');
  repl.setAttribute('code', code);
  replRoot.replaceChildren(repl);
  updateControls(track, packMode, packSelection.label);

  window.localStorage.setItem('glass-harbor-track', track.id);
  window.localStorage.setItem('glass-harbor-pack-mode', packMode.id);
}

async function applySelection(track, packMode) {
  const requestId = ++activeLoadRequest;
  try {
    await loadTrack(track, packMode, requestId);
  } catch (error) {
    if (requestId !== activeLoadRequest || error.name === 'AbortError') {
      return;
    }
    renderError(error);
  }
}

trackButtons.forEach((button) => {
  button.addEventListener('click', async () => {
    const track = tracks.find((entry) => entry.id === button.dataset.track);
    if (!track) {
      return;
    }
    const activePackMode =
      packModes.find((mode) => mode.id === window.localStorage.getItem('glass-harbor-pack-mode')) ??
      defaultPackMode;
    await applySelection(track, activePackMode);
  });
});

packButtons.forEach((button) => {
  button.addEventListener('click', async () => {
    const packMode = packModes.find((mode) => mode.id === button.dataset.packMode);
    const activeTrack =
      tracks.find((track) => track.id === window.localStorage.getItem('glass-harbor-track')) ?? defaultTrack;
    if (!packMode) {
      return;
    }
    await applySelection(activeTrack, packMode);
  });
});

applySelection(defaultTrack, defaultPackMode);
