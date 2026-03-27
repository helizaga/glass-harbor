---
name: strudel-songwriter
description: Generate or revise a pasteable Strudel song from a Markdown brief in the Glass Harbor repo. Use when the task is to create a new song under songs/<slug>/, rewrite an existing canonical song file, or turn a critique/revision package into updated Strudel code that follows the repo's metadata, stable sound-role, and paste-mode contracts.
---

# Strudel Songwriter

Use this skill when working on canonical song files in this repo:

- `songs/<slug>/<slug>.brief.md`
- `songs/<slug>/<slug>.strudel.js`

Do not use this skill for render-harness debugging, sample-pack plumbing, or compare/runs infrastructure.

## What To Read First

Read only what you need:

1. The target brief in `songs/<slug>/<slug>.brief.md`
2. [AGENTS.md](/Users/tommy/Documents/GitHub/song/AGENTS.md)
3. [songs/README.md](/Users/tommy/Documents/GitHub/song/songs/README.md)
4. The existing canonical song file if this is a revision
5. Relevant reference cards in `references/` only if the brief needs style guidance

If the song folder does not exist yet, scaffold it with:

```sh
node ./bin/glass-harbor.mjs song new <slug>
```

## Required Output Contract

Your output is one canonical song file:

- `songs/<slug>/<slug>.strudel.js`

It must:

- stay directly pasteable into `https://strudel.cc/`
- keep `samples('http://localhost:5432')`
- start with:
  - `@title`
  - `@genre`
  - `@bpm`
  - `@details`
  - `@sections`
- use readable named layers and `arrange(...)`-style section assembly
- use only the stable sampled roles unless the user explicitly expands the contract:
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
- avoid vendor filenames, private paths, repo-specific wrappers, or imports

## Writing Workflow

1. Read the brief and identify:
   - BPM
   - target mood/genre
   - section map
   - sonic goals
   - review goals
2. Decide whether this is:
   - a fresh song draft
   - a focused revision of an existing song
   - a rewrite from a revision package under `runs/<slug>/<timestamp>/`
3. Build the song around a few named layer roles:
   - drums
   - bass
   - pads
   - hook/lead/pluck
   - air/shimmer/riser/impact/vocal support
4. Assemble sections clearly with contrast:
   - intros should be sparse
   - breakdowns should create a real valley before the payoff
   - drops/blooms should win through density and weight, not clutter
5. Keep the file readable enough for a human to paste and tweak quickly

## Validation

Run this after writing or revising the song:

```sh
node ./bin/glass-harbor.mjs song validate <slug> --json
```

If the task is generation plus review, continue with:

```sh
node ./bin/glass-harbor.mjs song loop <slug> --max-iters 1 --json
```

If the task is branch-and-rank exploration from one base song, prefer:

```sh
node ./bin/glass-harbor.mjs song explore <slug> --count 3 --max-iters 1 --json
```

## Revision Mode

If a run already exists, prefer reading:

- `runs/<slug>/<timestamp>/critique.json`
- `runs/<slug>/<timestamp>/revision-request.json`
- `runs/<slug>/<timestamp>/revision-prompt.md`

When revising:

- make the smallest clean musical change that addresses the critique
- preserve the brief's emotional intent
- do not rewrite the whole song unless the critique indicates a structural miss

## Quality Bar

Good song files in this repo:

- are concise enough to reason about
- have a clear section identity
- use the stable runtime vocabulary consistently
- can be validated and reviewed without hand-editing for the toolchain

When deciding between elegance and cleverness, choose readability.
