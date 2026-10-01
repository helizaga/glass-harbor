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

For normal Codex-thread use, the intended experience is simpler:

1. you describe the song you want in plain language
2. Codex turns that into a brief and picks a slug
3. Codex writes one canonical song by default
4. Codex validates it automatically
5. Codex only runs a hidden review pass when the first draft looks risky or you explicitly ask for optimization
6. you get the song file plus a short note, not the whole artifact stack unless it matters

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

Taste examples live under `examples/<slug>/`:

- committed: `example.md`, `profile.json`
- local only: `clips/*.wav`, `analysis.json`

Named-song references from normal generation requests are prompt-only by default. They should shape the generated brief and song for that request, but they should not be ingested into `examples/` unless you explicitly ask to teach that taste permanently.

Start with:

- [songs/glass-harbor/glass-harbor.brief.md](songs/glass-harbor/glass-harbor.brief.md)
- [songs/glass-harbor/glass-harbor.strudel.js](songs/glass-harbor/glass-harbor.strudel.js)

## Local Strudel Reference

The repo now includes a small local Strudel lookup layer for agents and humans:

- [docs/strudel/README.md](docs/strudel/README.md)
- [docs/strudel/technique-index.md](docs/strudel/technique-index.md)
- [docs/strudel/sound-guide.md](docs/strudel/sound-guide.md)
- [docs/strudel/style-lanes.md](docs/strudel/style-lanes.md)

These are meant to keep songwriting decisions fast and lane-aware without loading the entire Strudel documentation set every time.

## Fastest Workflow

```sh
npm install
npm exec -- glass-harbor song serve
```

Then open `https://strudel.cc/`, paste the contents of a song file from `songs/`, and press play.

`glass-harbor song serve` serves the active runtime pack on `http://localhost:5432`, which is what the authored song files expect. `npm run song:serve` remains as a compatibility shim.

## Thread-First Song Creation

If you are using Codex threads as the interface, you should not need to think in CLI steps for normal creation requests. The default behavior should be:

1. say what you want musically
2. optionally cite real songs or artists as prompt-only references
3. let Codex create the brief and song under `songs/<slug>/`
4. get back:
   - the song file
   - the brief file
   - one short note on what it is aiming for
   - one short note on whether it was only validated or also review-checked

The deeper CLI review flow is still there, but it should stay in the background unless it materially changes the answer.

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
- `verdict.json`
- `verdict.md`
- `summary.md`
- `revision.md`
- `revision-request.json`
- `revision-prompt.md`

The render path uses a local browser runtime driven by Playwright. You do not need to use a browser UI by hand, but Strudel still needs a browser engine for reliable playback and offline rendering.

Each song also keeps local agent memory in `songs/<slug>/memory.json`:

- current approved baseline run
- last attempted run
- pending review run
- current open issue
- active taste profile
- short decision history

This file is local state and is gitignored.

The analyzer now prefers a repo-local Python environment at `.glass-harbor-venv/bin/python` when present, then falls back to `GLASS_HARBOR_PYTHON`, then `python3`. For the richer MIR stack, install:

```sh
python3 -m venv .glass-harbor-venv
. .glass-harbor-venv/bin/activate
python -m pip install -r scripts/requirements-analysis.txt
```

Optional style-alignment env:

- `GLASS_HARBOR_EMBEDDING_PROVIDER=none|mulan`
- `GLASS_HARBOR_MULAN_MODEL_PATH=/path/to/local/model`

If the MuLan backend is unavailable, critique falls back to deterministic MIR and retrieval-based style scoring with lower confidence.

If you want to teach the critic from songs you like, ingest a local private example:

```sh
npm exec -- glass-harbor taste ingest <example-slug>
```

That reads `examples/<slug>/example.md` plus local `examples/<slug>/clips/*.wav`, writes a local `analysis.json`, and refreshes the committed `profile.json` used during song critique.

For thread-first generation, `song validate <slug> --json` now exposes a `generation_strategy` block. When it reports `two_candidate_hidden`, the intended behavior is to silently branch a rhythm-forward and melody-forward draft, keep the stronger one, and only surface a single winner in the thread.

If you want a better public scaffold pack than the fully synthetic default, install the curated free alternates:

```sh
npm run install:free-pack
```

That keeps the synthetic drum core intact, adds curated free alternates for FX/textures under `samples/edm-core/`, and records their sources in `samples/edm-core/free-starter-pack.json`.

## Manual Local Pack Upgrade

For better sound quality, use the local stable-pack overlay workflow:

```sh
npm run drums:init
```

That creates:

- `private-packs/vendor-sources/local-drums/raw/`
- `private-packs/vendor-sources/local-drums/import-map.json`

Drop your downloaded files into any of these folders:

- `private-packs/vendor-sources/local-drums/raw/kicks/`
- `private-packs/vendor-sources/local-drums/raw/claps/`
- `private-packs/vendor-sources/local-drums/raw/hats/`
- `private-packs/vendor-sources/local-drums/raw/perc/`
- `private-packs/vendor-sources/local-drums/raw/bass/`
- `private-packs/vendor-sources/local-drums/raw/stabs/`
- `private-packs/vendor-sources/local-drums/raw/leads/`
- `private-packs/vendor-sources/local-drums/raw/textures/`
- `private-packs/vendor-sources/local-drums/raw/vocals/`
- `private-packs/vendor-sources/local-drums/raw/risers/`
- `private-packs/vendor-sources/local-drums/raw/impacts/`
- `private-packs/vendor-sources/local-drums/raw/shimmer/`

Then edit `import-map.json` so it points at the files you want to use for:

- `kick_main`
- `clap_main`
- `hat_closed`
- `hat_open`
- optional `perc_top`
- optional `air_texture`
- optional `shimmer_fx`
- optional `riser_up`
- optional `impact_wide`
- optional `vocal_chop`
- optional `bass_tonal`
- optional `stab_tonal`
- optional `pluck_tonal`
- optional pitch-aware `bass_pitched`
- optional pitch-aware `stab_pitched`
- optional pitch-aware `pluck_pitched`

Example mapping:

```json
{
  "families": {
    "kick_main": ["kicks/main-kick.wav", "kicks/warm-kick.wav"],
    "clap_main": ["claps/main-clap.wav"],
    "hat_closed": ["hats/tight-hat.wav", "hats/soft-hat.wav"],
    "hat_open": ["hats/open-hat.wav"],
    "perc_top": [],
    "air_texture": ["textures/air-texture.wav"],
    "shimmer_fx": ["shimmer/shimmer.wav"],
    "riser_up": ["risers/riser.wav"],
    "impact_wide": ["impacts/impact.wav"],
    "vocal_chop": ["vocals/chop.wav"],
    "bass_tonal": ["bass/bass-shot.wav"],
    "stab_tonal": ["stabs/stab-shot.wav"],
    "pluck_tonal": ["leads/pluck-shot.wav"],
    "stab_pitched": {
      "a3": ["stabs/stab-a3.wav"],
      "c4": ["stabs/stab-c4.wav"]
    },
    "pluck_pitched": {
      "a3": ["leads/pluck-a3.wav"],
      "c4": ["leads/pluck-c4.wav"]
    }
  }
}
```

Import the overlay with:

```sh
npm run drums:prep
npm run drums:import
```

`drums:prep` reads `private-packs/vendor-sources/local-drums/prep-plan.json` and writes trimmed / filtered working assets back into the local workspace before import.

`drums:import` writes a merged runtime pack to `private-packs/runtime/edm-core/` and keeps any untouched families falling back to the public scaffold pack.

After `song loop`, the repo now records local pack evidence under:

- `private-packs/curation/outcomes.json`
- `private-packs/curation/pairwise.json`

Those records tie active kick / bass / vocal choices to real song outcomes instead of relying on filenames alone.

When a brief includes `## Example Targets`, the tool prefers those attached example profiles before falling back to generic reference cards. This is the main quality lever for artist-adjacent prompts.

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
- `verdict.json`
- `verdict.md`
- `summary.md`

`song explore` writes a gitignored exploration bundle under `runs/<source-slug>/explorations/<timestamp>/` with:

- `explore.json`
- `explore.md`
- `verdict.json`
- `verdict.md`
- `summary.md`

When you compare from a source slug with `variants.json`, the base song is included automatically as the baseline unless you pass explicit slugs instead.

You can also compare arbitrary slugs directly:

```sh
npm exec -- glass-harbor song compare open-water-signal horizon-answer
```

## Thread Workflow

If you want Codex threads to be the interface, use these commands as the control surface:

- `glass-harbor song status <slug>`
- `glass-harbor song next <slug>`
- `glass-harbor song approve <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--avoid <trait>]`
- `glass-harbor song reject <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--avoid <trait>]`

The intended loop is:

1. agent runs `song next <slug>` to choose the best next move
2. if needed, agent runs `song loop`, `song compare`, or `song explore`
3. agent summarizes `summary.md` or `verdict.md` in the thread
4. you reply with approval or rejection
5. agent calls `song approve` or `song reject` and continues

`song approve` and `song reject` also accept optional taste-teaching flags:

- `--preserve <trait>`
- `--avoid <trait>`
- `--tradeoff <note>`
- `--reason <text>`

These are recorded into local song memory so future drafts preserve what you liked instead of only updating the baseline pointer.

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

Optional tonal sample families are available when they materially improve hook quality:

- `bass_tonal`
- `stab_tonal`
- `pluck_tonal`

This keeps song code portable across sound-pack changes.

## Song Metadata Contract

Generated songs should start with:

- `@title`
- `@genre`
- `@bpm`
- `@details`
- `@sections`
- `@section_roles`

`@sections` uses cycle counts, for example:

```js
// @sections intro:8, groove:16, lift:8, breakdown:16, drop:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, drop:return, outro:outro
```

The render loop uses this metadata to create named section clips automatically, and the critic uses `@section_roles` to judge section intent without guessing from section names alone.

## Brief References

Briefs may include:

- `## Example Targets`
  Use this only for committed taste-memory examples under `examples/`.
- `## Prompt References`
  Use this for real songs or artists cited in the current request, plus short notes about what to borrow and what not to copy.

`Prompt References` are ephemeral by default and should not automatically become durable taste memory.
They create a temporary per-song style lens for reference retrieval, calibration, and critique without writing anything into `examples/` or long-term taste memory.

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
- `glass-harbor song status <slug>`
- `glass-harbor song next <slug>`
- `glass-harbor song approve <slug> [--run <path>] [--reason <text>]`
- `glass-harbor song reject <slug> [--run <path>] [--reason <text>]`
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
- The recommended human-in-the-loop pattern is: agent runs the CLI, you read `summary.md` or `verdict.md`, then you approve or redirect.
- The project is most valuable as workflow infrastructure on top of Strudel, not as a replacement for Strudel itself.
- The review loop is deterministic first: MIR-style analysis runs every pass, while future audio-model critique can layer on top through a provider hook.
