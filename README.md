# Glass Harbor

Paste-first songwriting scaffold for LLM and agentic music generation with Strudel.

The primary workflow is:

1. write a short song brief in Markdown
2. generate one pasteable `.strudel.js` song file against stable sound-role names
3. run `glass-harbor song serve`
4. paste the song file into `https://strudel.cc/`
5. optionally use the local app for debugging or SuperDirt verification
6. optionally run the local render -> analyze -> critique loop for revision guidance

## What This Repo Is

- an agent-first songwriting workspace
- a stable sound-role contract for generated songs
- a public scaffold pack that always runs
- a private licensed-sample overlay that stays local
- an optional local debug UI built on `@strudel/repl`
- a headless browser render path for agent review
- a retrieval-style reference library for prompting and critique

## What The Primary Artifacts Are

Songs live under `songs/<slug>/`:

- `songs/<slug>/<slug>.brief.md`: short human/agent brief
- `songs/<slug>/<slug>.strudel.js`: the single pasteable song file

Reference cards live under `references/` and capture reusable arrangement patterns without copying copyrighted songs.

Start with:

- [songs/glass-harbor/glass-harbor.brief.md](/Users/tommy/Documents/GitHub/song/songs/glass-harbor/glass-harbor.brief.md)
- [songs/glass-harbor/glass-harbor.strudel.js](/Users/tommy/Documents/GitHub/song/songs/glass-harbor/glass-harbor.strudel.js)

## Fastest Workflow

```sh
npm install
npm exec -- glass-harbor song serve
```

Then open `https://strudel.cc/`, paste the contents of a song file from `songs/`, and press play.

`glass-harbor song serve` serves the active runtime pack on `http://localhost:5432`, which is what the authored song files expect. `npm run song:serve` remains as a compatibility shim.

## Optional Local Debug Runner

```sh
npm run dev
```

The local app is secondary now. Use it to:

- audition a song locally
- verify the public scaffold vs private overlay
- run the preload track
- verify the SuperDirt debug path

## Headless Review Loop

The repo now supports a browser-minimal review workflow:

```sh
npm exec -- glass-harbor song render glass-harbor
npm exec -- glass-harbor song analyze glass-harbor
npm exec -- glass-harbor song critique glass-harbor
```

This produces a gitignored run under `runs/<slug>/<timestamp>/` with:

- `mix.wav`
- `sections/*.wav`
- `analysis.json`
- `critique.json`
- `revision.md`

The render path uses a local browser runtime driven by Playwright. You do not need to use a browser UI by hand, but Strudel still needs a browser engine for reliable playback and offline rendering.

## Stable Sound Vocabulary

Generated songs should only target these sampled roles unless you explicitly expand the contract:

- `kick_main`
- `clap_main`
- `hat_closed`
- `hat_open`
- `perc_top`
- `impact_wide`
- `riser_up`
- `shimmer_fx`
- `air_texture`
- `vocal_chop`

This keeps song code portable across sound-pack changes.

## Song Metadata Contract

Generated songs should start with:

- `@title`
- `@genre`
- `@bpm`
- `@details`
- `@sections`

`@sections` uses cycle counts, for example:

```js
// @sections intro:8, groove:16, lift:8, breakdown:16, drop:16, outro:8
```

The render loop uses this metadata to create named section clips automatically.

## Public Scaffold vs Private Overlay

The committed repo stays public-safe:

- `samples/edm-core` contains generated placeholder audio only
- licensed sample libraries never need to be committed
- private imported audio lives under `private-packs/`, which is gitignored

The app can run in three pack modes:

- `Auto`: prefer the private overlay when complete, otherwise use the public scaffold
- `Public Scaffold`: force the committed placeholder pack
- `Private Overlay`: force the imported private pack

## Private Pack Import

When you are ready to import a private library:

```sh
npm run vendor:init
```

This creates a local gitignored workspace:

- `private-packs/vendor-sources/kshmr-vol-4/raw/`
- `private-packs/vendor-sources/kshmr-vol-4/import-map.json`
- `private-packs/runtime/edm-core/`

Then:

1. copy your private sample files into the raw folder
2. edit the local import map
3. run `npm run vendor:import`

The imported runtime pack keeps the same stable sound-role names, so existing songs do not need rewrites.

## Scripts

- `glass-harbor song serve`: serve the active runtime pack for Strudel web paste mode
- `glass-harbor song new <slug>`: scaffold a brief and pasteable song file
- `glass-harbor song validate <slug>`: validate the brief and canonical song contract
- `glass-harbor song render <slug>`: render the canonical song into a full mix plus section clips
- `glass-harbor song analyze <slug>`: analyze the latest rendered run with deterministic audio metrics
- `glass-harbor song critique <slug>`: score the latest run and write revision guidance
- `glass-harbor song loop <slug>`: orchestrate render -> analyze -> critique for one review pass
- `glass-harbor debug ui`: run the optional local debug app
- `glass-harbor debug osc`: run the Strudel OSC bridge
- `npm run song:*`: compatibility shims that forward to the CLI
- `npm run dev`: run the optional local debug app
- `npm run build`: build the local debug app and copy runtime assets into `dist/`
- `npm run preview`: preview the built app
- `npm run generate:samples`: regenerate the committed placeholder pack
- `npm run pack:json`: regenerate `samples/edm-core/strudel.json`
- `npm run prep`: regenerate scaffold audio plus manifest
- `npm run osc`: run the Strudel OSC bridge
- `npm run osc:debug`: run the OSC bridge with verbose logging
- `npm run samples:serve`: serve the committed scaffold pack only
- `npm run vendor:init`: create the local gitignored import workspace
- `npm run vendor:import`: import a private library into the runtime pack
- `npm run vendor:manifest`: regenerate only the private runtime manifest

## Repo Layout

- `songs/`: primary song briefs and pasteable song files
- `samples/edm-core/`: committed scaffold pack
- `private-packs/`: gitignored private overlay
- `tracks/`: optional local debug surfaces such as preload and SuperDirt debug
- `packs/`: sound policy and import templates
- `references/`: retrieval-style song/reference cards
- `presets/`: preload and naming conventions
- `scripts/`: pack serving, generation, import, and copy helpers
- `src/`: optional local debug app

## Notes

- The included audio is generated placeholder material so the repo works immediately and stays license-safe.
- The local app is intentionally no longer the center of the workflow.
- The project is most valuable as workflow infrastructure on top of Strudel, not as a replacement for Strudel itself.
- The review loop is deterministic first: MIR-style analysis runs every pass, while future audio-model critique can layer on top through a provider hook.
