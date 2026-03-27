# Glass Harbor EDM Lab

Local-first Strudel setup for modern EDM sketching with:

- a pinned browser REPL running inside this repo
- a curated custom sample pack under `samples/edm-core`
- a gitignored private commercial-pack overlay under `private-packs/`
- a preload ritual to warm critical one-shots
- three track targets:
  - `tracks/glass-harbor.local.strudel.js` for browser-only preview
  - `tracks/glass-harbor.superdirt.strudel.js` for hybrid local samples + OSC to SuperDirt
  - `tracks/edm-pack-preload.strudel.js` for sample warm-up before a real take

## Quick Start

```sh
npm install
npm run dev
```

Open the local URL from Vite. The app loads the local preview track by default.

## Public Scaffold vs Private Overlay

The committed repo stays public-safe:

- `samples/edm-core` contains generated placeholder audio only
- paid sample packs never need to be committed
- private imported audio lives under `private-packs/`, which is gitignored

The app can run in three pack modes:

- `Auto`: use your private overlay if present, otherwise use the public scaffold
- `Public Scaffold`: force the committed placeholder pack
- `Private Overlay`: force your imported commercial pack

## Pure Live-Coding Workflow

### 1. Browser-only sketch mode

```sh
npm run dev
```

Use the `Local Preview` track in the app. This path stays inside Strudel's browser audio engine and is useful for arranging, sample selection, and quick iteration.

### 2. Preload the pack

Switch to the `Pack Preload` track and press play once before a real session. This triggers the mission-critical sounds quietly so first-hit lazy loading does not weaken the intro or drop.

### 3. SuperDirt performance mode

In a second terminal, start the OSC bridge:

```sh
npm run osc
```

Then start SuperCollider / SuperDirt locally. After that, switch to the `SuperDirt Performance` track in the app.

This hybrid track keeps drums, FX, textures, and vocal chops on the local custom pack while routing basses, pads, plucks, arps, and leads to SuperDirt over OSC.

## Future KSHMR Vol. 4 Import

When you are ready to import your private library:

```sh
npm run vendor:init
```

This creates a gitignored local workspace:

- `private-packs/vendor-sources/kshmr-vol-4/raw/`
- `private-packs/vendor-sources/kshmr-vol-4/import-map.json`
- `private-packs/runtime/edm-core/`

Copy your purchased KSHMR Vol. 4 files into `private-packs/vendor-sources/kshmr-vol-4/raw/`, edit the local `import-map.json`, then run:

```sh
npm run vendor:import
```

That command:

- copies your chosen vendor files into the stable runtime family names
- writes a private `strudel.json`
- keeps all track code pointing at stable names like `kick_main`, `clap_main`, and `riser_up`

The public repo keeps working even if you never import the private pack.

## Scripts

- `npm run dev`: run the local REPL app
- `npm run build`: build the app and copy sample assets into `dist/`
- `npm run preview`: preview the built app
- `npm run generate:samples`: regenerate the placeholder EDM pack audio
- `npm run pack:json`: regenerate `samples/edm-core/strudel.json`
- `npm run prep`: regenerate audio, manifest, and build-ready sample assets
- `npm run osc`: run the local Strudel OSC bridge on the default SuperDirt ports
- `npm run osc:debug`: same as above with verbose OSC logging
- `npm run samples:serve`: serve `samples/edm-core` with `@strudel/sampler`
- `npm run vendor:init`: create the local gitignored KSHMR import workspace
- `npm run vendor:import`: build a private runtime pack from your local import map
- `npm run vendor:manifest`: regenerate the private runtime manifest only

## Repo Layout

- `src/`: local app shell around `@strudel/repl`
- `tracks/`: Strudel compositions and preload ritual
- `samples/edm-core/`: custom sample pack source and generated `strudel.json`
- `private-packs/`: gitignored raw commercial sources and curated runtime overlay
- `packs/`: sound policy and replacement guidance
- `presets/`: preload and naming conventions
- `scripts/`: sample generation and packaging helpers

## Notes

- The included samples are generated placeholders so the repo is self-contained and produces no missing-file errors. Replace them with your own higher-end one-shots for release work.
- The default private-pack template is aimed at a future `KSHMR Vol. 4` import, but the overlay workflow is vendor-agnostic as long as you map into the same runtime family names.
- This repo is not a DAW replacement. It is a no-DAW live-coding rig centered on Strudel, custom samples, and SuperDirt.
