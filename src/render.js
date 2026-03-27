import * as core from '@strudel/core';
import {
  evalScope,
  repl,
} from '@strudel/core';
import { transpiler } from '@strudel/transpiler';
import {
  getSound,
  registerSynthSounds,
  registerZZFXSounds,
  samples,
} from '@strudel/webaudio';
import {
  initAudio,
  resetGlobalEffects,
  setAudioContext,
  setSuperdoughAudioController,
  superdough,
} from 'superdough';
import { Orbit, SuperdoughAudioController } from 'superdough/superdoughoutput.mjs';

import {
  buildSectionTimeline,
  extractSampleRoles,
  extractSynthVoices,
  parseSections,
  parseSongMetadata,
  sanitizeSlug,
} from '../lib/song-contract-browser.mjs';

const statusNode = document.querySelector('#status');
const params = new URLSearchParams(window.location.search);

window.__renderState = {
  status: 'booting',
  completed: 0,
  expected: 1,
  outputs: [],
  error: null,
  preflight: null,
  runtime_blockers: [],
};

const noopOutput = async () => {};

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

function stripEvaluationSetup(code) {
  return `${code ?? ''}`
    .split('\n')
    .filter((line) => !/^\s*samples\s*\(\s*['"]http:\/\/localhost:5432['"]\s*\)\s*$/.test(line))
    .join('\n');
}

function setBlocked(message, blockers = [], preflight = window.__renderState.preflight) {
  window.__renderState.status = 'blocked';
  window.__renderState.runtime_blockers = blockers;
  window.__renderState.preflight = preflight;
  statusNode.textContent = message;
}

function createBlocker(code, surface, message, name = null) {
  return {
    code,
    surface,
    message,
    name,
    count: 1,
    examples: [message],
  };
}

function createStereoNode(audioContext) {
  return new GainNode(audioContext, { gain: 1, channelCount: 2, channelCountMode: 'explicit' });
}

function normalizeManifestUrl(sampleBaseUrl) {
  return sampleBaseUrl.endsWith('strudel.json')
    ? sampleBaseUrl
    : `${sampleBaseUrl.replace(/\/$/, '')}/strudel.json`;
}

function normalizeBankUrls(role, bank) {
  const normalizeUrl = (rawUrl) => {
    const value = `${rawUrl ?? ''}`;
    const pathname = (() => {
      try {
        return new URL(value, window.location.href).pathname;
      } catch {
        return value;
      }
    })();
    const roleMarker = `/${role}/`;
    const markerIndex = pathname.lastIndexOf(roleMarker);
    if (markerIndex !== -1) {
      return pathname.slice(markerIndex);
    }
    return pathname.startsWith('/') ? pathname : `/${pathname}`;
  };

  if (Array.isArray(bank)) {
    return bank.map(normalizeUrl);
  }

  return Object.fromEntries(
    Object.entries(bank ?? {}).map(([note, samplesForNote]) => [
      note,
      (Array.isArray(samplesForNote) ? samplesForNote : [samplesForNote]).map(normalizeUrl),
    ]),
  );
}

function buildRuntimeSampleMap(manifest) {
  return Object.fromEntries(
    Object.entries(manifest ?? {})
      .filter(([key]) => key !== '_base')
      .map(([role, bank]) => [role, normalizeBankUrls(role, bank)]),
  );
}

let runtimeScopeReady;
let offlineFxPatchInstalled = false;

async function ensureRuntimeScope() {
  runtimeScopeReady ??= evalScope(
    core,
    import('@strudel/mini'),
    import('@strudel/tonal'),
    import('@strudel/webaudio'),
  );
  await runtimeScopeReady;
}

function installOfflineFxCompatibilityPatch() {
  if (offlineFxPatchInstalled) {
    return;
  }
  offlineFxPatchInstalled = true;

  const originalGetOrbit = SuperdoughAudioController.prototype.getOrbit;
  const originalGetBus = SuperdoughAudioController.prototype.getBus;
  const originalGetDelay = Orbit.prototype.getDelay;
  const originalGetReverb = Orbit.prototype.getReverb;
  Orbit.prototype.ensureOfflineContext = function ensureOfflineContext(audioContext) {
    if (
      this.audioContext === audioContext &&
      this.output?.context === audioContext &&
      this.summingNode?.context === audioContext
    ) {
      return;
    }

    this.disconnect?.();
    this.audioContext = audioContext;
    this.output = createStereoNode(audioContext);
    this.summingNode = createStereoNode(audioContext);
    this.summingNode.connect(this.output);
    this.delayNode = null;
    this.reverbNode = null;
    this.djfNode = null;

    if (this.__controllerOutput) {
      this.__controllerOutput.connectToDestination(this.output, this.__channels);
    }
  };

  SuperdoughAudioController.prototype.getOrbit = function patchedGetOrbit(orbitNum, channels) {
    const orbit = originalGetOrbit.call(this, orbitNum, channels);
    orbit.__channels = channels;
    orbit.__controllerOutput = this.output;
    orbit.ensureOfflineContext?.(this.audioContext);
    return orbit;
  };

  SuperdoughAudioController.prototype.getBus = function patchedGetBus(busNum) {
    const bus = this.buses[busNum];
    if (bus && bus.context !== this.audioContext) {
      bus.disconnect?.();
      delete this.buses[busNum];
    }
    return originalGetBus.call(this, busNum);
  };

  Orbit.prototype.getDelay = function patchedGetDelay(delaytime = 0, feedback = 0.5, t) {
    this.__lastDelayArgs = { delaytime, feedback, t };
    this.ensureOfflineContext?.(this.audioContext);
    if (this.delayNode && this.delayNode.context !== this.audioContext) {
      this.delayNode.disconnect?.();
      this.delayNode = null;
    }
    return originalGetDelay.call(this, delaytime, feedback, t);
  };

  Orbit.prototype.getReverb = function patchedGetReverb(duration, fade, lp, dim, ir, irspeed, irbegin) {
    this.__lastReverbArgs = { duration, fade, lp, dim, ir, irspeed, irbegin };
    this.ensureOfflineContext?.(this.audioContext);
    if (this.reverbNode && this.reverbNode.context !== this.audioContext) {
      this.reverbNode.disconnect?.();
      this.reverbNode = null;
    }
    return originalGetReverb.call(this, duration, fade, lp, dim, ir, irspeed, irbegin);
  };

  Orbit.prototype.sendDelay = function patchedSendDelay(node, amount) {
    this.ensureOfflineContext?.(node.context);
    if (!this.delayNode || this.delayNode.context !== node.context) {
      const { delaytime = 0, feedback = 0.5, t = 0 } = this.__lastDelayArgs ?? {};
      this.getDelay(delaytime, feedback, t);
    }
    const send = new GainNode(node.context, { gain: amount });
    node.connect(send);
    send.connect(this.delayNode);
    return send;
  };

  Orbit.prototype.sendReverb = function patchedSendReverb(node, amount) {
    this.ensureOfflineContext?.(node.context);
    if (!this.reverbNode || this.reverbNode.context !== node.context) {
      const { duration, fade, lp, dim, ir, irspeed, irbegin } = this.__lastReverbArgs ?? {};
      this.getReverb(duration, fade, lp, dim, ir, irspeed, irbegin);
    }
    const send = new GainNode(node.context, { gain: amount });
    node.connect(send);
    send.connect(this.reverbNode);
    return send;
  };
}

function manifestBankHasSamples(bank) {
  if (Array.isArray(bank)) {
    return bank.length > 0;
  }

  if (bank && typeof bank === 'object') {
    return Object.values(bank).some((entry) =>
      Array.isArray(entry) ? entry.length > 0 : !!entry,
    );
  }

  return false;
}

async function fetchSampleManifest(manifestUrl) {
  const response = await fetch(manifestUrl);
  if (!response.ok) {
    throw new Error(`Unable to load sample manifest: ${manifestUrl}`);
  }
  return response.json();
}

function buildPreflight({ code, manifest, sampleManifestUrl }) {
  const sampleRoles = extractSampleRoles(code);
  const synthVoices = extractSynthVoices(code);
  const preflight = {
    status: 'ready',
    sample_manifest_url: sampleManifestUrl,
    resolved_sample_roles: [],
    missing_sample_roles: [],
    resolved_synth_voices: [],
    missing_synth_voices: [],
  };
  const blockers = [];

  sampleRoles.forEach((role) => {
    const manifestHasRole = manifest && manifestBankHasSamples(manifest[role]);
    const registryHasRole = !!getSound(role);
    if (manifestHasRole && registryHasRole) {
      preflight.resolved_sample_roles.push(role);
      return;
    }

    preflight.missing_sample_roles.push(role);
    blockers.push(
      createBlocker(
        'missing_sample_role',
        manifestHasRole ? 'render_runtime' : 'sample_pack',
        manifestHasRole
          ? `Sample role "${role}" is not registered in the render runtime.`
          : `Sample role "${role}" is missing from ${sampleManifestUrl}.`,
        role,
      ),
    );
  });

  synthVoices.forEach((voice) => {
    if (getSound(voice)) {
      preflight.resolved_synth_voices.push(voice);
      return;
    }

    preflight.missing_synth_voices.push(voice);
    blockers.push(
      createBlocker(
        'missing_synth_voice',
        'synth_registry',
        `Synth voice "${voice}" is not registered in the render runtime.`,
        voice,
      ),
    );
  });

  preflight.status = blockers.length > 0 ? 'blocked' : 'ready';
  return { preflight, blockers };
}

async function initOfflineRuntime({ manifest, sampleBaseUrl, sampleRate, frameCount }) {
  installOfflineFxCompatibilityPatch();
  resetGlobalEffects();
  setSuperdoughAudioController(null);
  const audioContext = new OfflineAudioContext(2, frameCount, sampleRate);
  setAudioContext(audioContext);
  setSuperdoughAudioController(new SuperdoughAudioController(audioContext));
  await initAudio({
    maxPolyphony: 48,
    multiChannelOrbits: false,
  });
  registerSynthSounds();
  registerZZFXSounds();
  await samples(buildRuntimeSampleMap(manifest), sampleBaseUrl);
  return audioContext;
}

function audioBufferToWav(buffer, opt = {}) {
  const numChannels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const format = opt.float32 ? 3 : 1;
  const bitDepth = format === 3 ? 32 : 16;
  const result =
    numChannels === 2
      ? interleave(buffer.getChannelData(0), buffer.getChannelData(1))
      : buffer.getChannelData(0);
  return encodeWAV(result, format, sampleRate, numChannels, bitDepth);
}

function encodeWAV(samplesData, format, sampleRate, numChannels, bitDepth) {
  const bytesPerSample = bitDepth / 8;
  const blockAlign = numChannels * bytesPerSample;
  const buffer = new ArrayBuffer(44 + samplesData.length * bytesPerSample);
  const view = new DataView(buffer);
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samplesData.length * bytesPerSample, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samplesData.length * bytesPerSample, true);
  if (format === 1) {
    floatTo16BitPCM(view, 44, samplesData);
  } else {
    writeFloat32(view, 44, samplesData);
  }
  return buffer;
}

function interleave(left, right) {
  const result = new Float32Array(left.length + right.length);
  let index = 0;
  let inputIndex = 0;
  while (index < result.length) {
    result[index++] = left[inputIndex];
    result[index++] = right[inputIndex];
    inputIndex += 1;
  }
  return result;
}

function writeString(view, offset, string) {
  for (let index = 0; index < string.length; index += 1) {
    view.setUint8(offset + index, string.charCodeAt(index));
  }
}

function floatTo16BitPCM(view, offset, input) {
  for (let index = 0; index < input.length; index += 1, offset += 2) {
    const sample = Math.max(-1, Math.min(1, input[index]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
}

function writeFloat32(view, offset, input) {
  for (let index = 0; index < input.length; index += 1, offset += 4) {
    view.setFloat32(offset, input[index], true);
  }
}

async function downloadRenderedBuffer(renderedBuffer, outputName) {
  const wavBuffer = audioBufferToWav(renderedBuffer);
  const blob = new Blob([wavBuffer], { type: 'audio/wav' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${outputName}.wav`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function hapToValue(hap) {
  hap.ensureObjectValue?.();
  return hap.value;
}

async function renderPatternAudioStable({ pattern, cps, begin, end, outputName, audioContext }) {
  const haps = pattern
    .queryArc(begin, end, { _cps: cps })
    .sort((left, right) => left.whole.begin.valueOf() - right.whole.begin.valueOf());

  for (const hap of haps) {
    if (!hap.hasOnset()) {
      continue;
    }

    try {
      await superdough(
        hapToValue(hap),
        (hap.whole.begin.valueOf() - begin) / cps,
        hap.duration / cps,
        cps,
        (hap.whole?.begin.valueOf() - begin) / cps,
      );
    } catch (error) {
      console.error(error);
    }
  }

  const renderedBuffer = await audioContext.startRendering();
  await downloadRenderedBuffer(renderedBuffer, outputName);
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
  const begin = Number.parseFloat(params.get('begin') ?? '0');
  const end = Number.parseFloat(params.get('end') ?? `${totalCycles}`);
  const outputName = params.get('output') ?? 'mix';
  const sampleBaseUrl = 'http://localhost:5432';
  const sampleManifestUrl = normalizeManifestUrl(sampleBaseUrl);

  await ensureRuntimeScope();
  const evaluationCode = stripEvaluationSetup(code);
  const runtimeRepl = repl({
    defaultOutput: noopOutput,
    getTime: () => 0,
    transpiler,
    setInterval: window.setInterval.bind(window),
    clearInterval: window.clearInterval.bind(window),
  });
  await runtimeRepl.evaluate(evaluationCode, false);
  const pattern = runtimeRepl.state.pattern;
  if (!pattern) {
    throw new Error('Strudel evaluation completed without producing a pattern.');
  }

  const cps = runtimeRepl.scheduler.cps;
  const frameCount = Math.max(1, Math.ceil(((end - begin) / cps) * 44100));
  let manifest;
  try {
    manifest = await fetchSampleManifest(sampleManifestUrl);
  } catch {
    const blockers = [
      createBlocker(
        'sample_manifest_unavailable',
        'sample_pack',
        `Sample manifest is unavailable at ${sampleManifestUrl}.`,
      ),
    ];
    const preflight = {
      status: 'blocked',
      sample_manifest_url: sampleManifestUrl,
      resolved_sample_roles: [],
      missing_sample_roles: extractSampleRoles(code),
      resolved_synth_voices: [],
      missing_synth_voices: extractSynthVoices(code),
    };
    window.__renderState.preflight = preflight;
    window.__renderState.runtime_blockers = blockers;
    window.__renderState.metadata = metadata;
    window.__renderState.sections = sections;
    window.__renderState.dependencies = {
      sampleRoles: preflight.missing_sample_roles,
      synthVoices: preflight.missing_synth_voices,
    };
    runtimeRepl.stop?.();
    setBlocked(`Render preflight blocked for ${songSlug}`, blockers, preflight);
    return;
  }

  const audioContext = await initOfflineRuntime({
    manifest,
    sampleBaseUrl,
    sampleRate: 44100,
    frameCount,
  });
  const { preflight, blockers } = buildPreflight({ code, manifest, sampleManifestUrl });
  window.__renderState.preflight = preflight;
  window.__renderState.runtime_blockers = blockers;
  window.__renderState.metadata = metadata;
  window.__renderState.sections = sections;
  window.__renderState.dependencies = {
    sampleRoles: preflight.resolved_sample_roles.concat(preflight.missing_sample_roles),
    synthVoices: preflight.resolved_synth_voices.concat(preflight.missing_synth_voices),
  };

  if (blockers.length > 0) {
    runtimeRepl.stop?.();
    setBlocked(`Render preflight blocked for ${songSlug}`, blockers, preflight);
    return;
  }
  window.__renderState.cps = cps;
  window.__renderState.range = { begin, end };

  setStatus('rendering', `Rendering ${songSlug}: ${outputName}`);

  runtimeRepl.stop?.();
  await renderPatternAudioStable({ pattern, cps, begin, end, outputName, audioContext });
  window.__renderState.completed += 1;
  window.__renderState.outputs.push(outputName);

  setStatus('done', `Rendered ${window.__renderState.completed} file for ${songSlug}`);
}

renderSong().catch((error) => {
  window.__renderState.status = 'error';
  window.__renderState.error = error.message;
  statusNode.textContent = error.stack || error.message;
});
