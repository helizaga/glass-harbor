# Glass Harbor

Paste-first songwriting scaffold for LLM and agentic music generation with Strudel.

The primary workflow is:

1. write a short song brief in Markdown
2. generate one pasteable `.strudel.js` song file against stable sound-role names
3. run `glass-harbor song serve`
4. paste the song file into `https://strudel.cc/`
5. optionally scaffold multiple sibling variants from one base song with `glass-harbor song variants <slug>`
6. optionally run the local render -> analyze -> critique -> revise loop for each candidate
7. rank competing candidates with `glass-harbor song compare <slug>`
8. or let the CLI orchestrate the whole branch-and-rank pass with `glass-harbor song explore <slug>`
9. optionally use the local app for debugging or SuperDirt verification

## What This Repo Is

- an agent-first songwriting workspace built around pasteable Strudel files
- a stable sound-role contract for generated songs
- a public scaffold pack plus a private local overlay for licensed samples
- a debug-only local app and a headless render path for review
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

The local app is secondary now. Use it to audition a song locally, verify pack selection, run the preload track, or check the SuperDirt debug path.

## Headless Review Loop

The repo now supports a browser-minimal review workflow:

```sh
npm exec -- glass-harbor song render glass-harbor
npm exec -- glass-harbor song analyze glass-harbor
npm exec -- glass-harbor song critique glass-harbor
npm exec -- glass-harbor song revise glass-harbor
```

This produces a gitignored run under `runs/<slug>/<timestamp>/` with:

- `mix.wav`
- `sections/*.wav`
- `analysis.json`
- `critique.json`
- `revision.md`
- `revision-request.json`
- `revision-prompt.md`

The render path uses a local browser runtime driven by Playwright. You do not need to use a browser UI by hand, but Strudel still needs a browser engine for reliable playback and offline rendering.

## Variant Comparison

When one brief needs multiple candidate directions, scaffold sibling song folders first:

```sh
npm exec -- glass-harbor song variants glass-harbor
```

That writes normal song folders like:

- `songs/glass-harbor-v1/`
- `songs/glass-harbor-v2/`
- `songs/glass-harbor-v3/`

Then run the normal loop on each candidate and compare them:

```sh
npm exec -- glass-harbor song loop glass-harbor-v1 --max-iters 1 --json
npm exec -- glass-harbor song loop glass-harbor-v2 --max-iters 1 --json
npm exec -- glass-harbor song loop glass-harbor-v3 --max-iters 1 --json
npm exec -- glass-harbor song compare glass-harbor
```

Or let the CLI do the scaffold -> loop -> compare pass in one go:

```sh
npm exec -- glass-harbor song explore glass-harbor --count 3 --max-iters 1
```

`song compare` writes a gitignored comparison bundle under `runs/<source-slug>/comparisons/<timestamp>/` with:

- `comparison.json`
- `comparison.md`

`song explore` writes a gitignored exploration bundle under `runs/<source-slug>/explorations/<timestamp>/` with:

- `explore.json`
- `explore.md`

When you compare from a source slug with `variants.json`, the base song is included automatically as the baseline unless you pass explicit slugs instead.

You can also compare arbitrary slugs directly:

```sh
npm exec -- glass-harbor song compare open-water-signal horizon-answer
```

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

## Commands

Primary CLI:

- `glass-harbor song serve`
- `glass-harbor song new <slug>`
- `glass-harbor song variants <slug>`
- `glass-harbor song validate <slug>`
- `glass-harbor song render <slug>`
- `glass-harbor song analyze <slug>`
- `glass-harbor song critique <slug>`
- `glass-harbor song revise <slug>`
- `glass-harbor song loop <slug>`
- `glass-harbor song compare <slug> [<other-slug> ...]`
- `glass-harbor song explore <slug> [--count <n>] [--max-iters <n>]`
- `glass-harbor debug ui`
- `glass-harbor debug osc`

Compatibility and support scripts:

- `npm run song:*`: compatibility shims that forward to the CLI
- `npm run dev`, `npm run build`, `npm run preview`
- `npm run generate:samples`, `npm run pack:json`, `npm run prep`
- `npm run samples:serve`
- `npm run vendor:init`, `npm run vendor:import`, `npm run vendor:manifest`

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
