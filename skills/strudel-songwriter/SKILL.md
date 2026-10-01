---
name: strudel-songwriter
description: Generate or revise a pasteable Strudel song from either a freeform thread prompt or a Markdown brief in the Glass Harbor repo. Use when the task is to turn a user song description into a canonical song under songs/<slug>/, rewrite an existing song file, or turn a critique/revision package into updated Strudel code that follows the repo's metadata, stable sound-role, and paste-mode contracts.
---

# Strudel Songwriter

Use this skill when working on canonical song files in this repo:

- `songs/<slug>/<slug>.brief.md`
- `songs/<slug>/<slug>.strudel.js`

Default this skill to the thread-native flow:

1. user describes a song in plain language
2. you normalize that into a brief
3. you choose a slug
4. you generate one canonical song
5. you validate it
6. you only run a hidden review pass when the draft looks weak, risky, or the user explicitly wants optimization
7. you answer with the song file, the brief file, and one short summary

Do not use this skill for render-harness debugging, sample-pack plumbing, or compare/runs infrastructure.

## What To Read First

Read only what you need:

1. The user request itself if this starts from a freeform thread prompt
2. The target brief in `songs/<slug>/<slug>.brief.md` if it already exists
3. [AGENTS.md](/Users/tommy/Documents/GitHub/song/AGENTS.md)
4. [songs/README.md](/Users/tommy/Documents/GitHub/song/songs/README.md)
5. [docs/strudel/technique-index.md](/Users/tommy/Documents/GitHub/song/docs/strudel/technique-index.md) when you need a fast Strudel-technique lookup
6. [docs/strudel/sound-guide.md](/Users/tommy/Documents/GitHub/song/docs/strudel/sound-guide.md) when choosing role subsets or hook carriers
7. [docs/strudel/style-lanes.md](/Users/tommy/Documents/GitHub/song/docs/strudel/style-lanes.md) when the lane/accent matters
8. `songs/<slug>/memory.json` if it exists
9. Attached example profiles in `examples/<slug>/profile.json` only when the brief lists `## Example Targets`
10. The existing canonical song file if this is a revision
11. Relevant reference cards in `references/` only if the brief still needs style guidance after prompt references, examples, and memory
12. [songs/arrangement-archetypes.md](/Users/tommy/Documents/GitHub/song/songs/arrangement-archetypes.md) when you need a stronger macro-structure than the prompt alone provides

If the song folder does not exist yet, scaffold it with:

```sh
node ./bin/glass-harbor.mjs song new <slug>
```

Named real-song references from the user are prompt-only by default. Capture them in the brief, use them for this song, and do not ingest them into `examples/` unless the user explicitly asks to teach that taste permanently.
The toolchain will convert those prompt references into a temporary per-song style lens for retrieval and critique automatically.

## Research-First Rule

If the request names:

- a real artist
- a real song
- a specific subgenre lane
- a production style that could be misunderstood

research the source material first.

Before writing code, establish three buckets:

- source-supported traits
- your musical inferences from those traits
- capability gaps in the current runtime pack or workflow

Record that in the brief when relevant so future revisions do not have to re-guess it.
Do not present an artist-adjacent draft as “accurate” if the current sounds or structure can only approximate the lane loosely.

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
  - `@section_roles`
- use readable named layers and `arrange(...)`-style section assembly
- use only the stable sampled roles unless the brief clearly benefits from optional tonal sample families:
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
- optional tonal families, only when they noticeably improve the hook and keep the song portable:
  - `bass_tonal`
  - `stab_tonal`
  - `pluck_tonal`
- optional pitch-aware tonal families, preferred for note-driven hooks or harmony when the pack exposes them:
  - `bass_pitched`
  - `stab_pitched`
  - `pluck_pitched`
- prefer sampled tonal families and `vocal_chop` over naked browser synths for the main hook, bass identity, and harmonic bed
- if you must use a raw synth voice, keep it quiet, filtered, short, and supportive rather than making it the signature sound
- avoid vendor filenames, private paths, repo-specific wrappers, or imports

## Writing Workflow

1. If the user gave a freeform thread prompt instead of a brief:
   - extract a title candidate
   - choose a short slug
   - write the brief for them before writing code
2. Normalize the request into a brief that captures:
   - BPM
   - target mood/genre
   - style lane and accent when they matter
   - section map
   - prompt-only references
   - source-material study when artist/song references matter
   - example targets
   - sonic goals
   - review goals
3. Read taste memory before writing:
   - preserve traits
   - avoid traits
   - approved/rejected notes
4. Treat named-song references in the request as immediate style guidance:
   - what to borrow structurally or texturally
   - what to avoid copying literally
   - what to keep original
   - what is actually supported by sources versus what is only your inference
5. If example targets exist, bias the song toward those profiles before generic reference cards.
6. Resolve the lane before writing:
   - what genre/accent family is this actually in
   - which arrangement archetypes fit that lane
   - which sound roles should dominate
   - which support roles are allowed to answer the hook without becoming co-leads
   - which roles should be pruned first if the song starts collapsing back into the repo default accent
   - which anti-patterns would make it collapse back into the repo’s default accent
7. If prompt references, example targets, or an explicit style lane make this a style-heavy request, silently branch two candidate drafts:
   - rhythm/percussion-forward
   - harmony/melody-forward
   Keep only the better one unless the result is genuinely ambiguous.
8. Decide whether this is:
   - a fresh song draft
   - a focused revision of an existing song
   - a rewrite from a revision package under `runs/<slug>/<timestamp>/`
9. Build the song around a few named layer roles:
   - drums
   - bass
   - pads
   - hook/lead/pluck
   - air/shimmer/riser/impact/vocal support
   - default to sampled bass/stab/pluck/vocal layers before reaching for `triangle`, `sawtooth`, or `square`
   - if you use `vocal_chop`, split it into at least 2 contrasting jobs such as airy bed, hook punctuation, breakdown fragment, or return accent instead of one monolithic vocal lane
10. Pick one arrangement archetype first, then adapt it to the prompt:
   - patient bloom
   - percussion reveal
   - subtractive breakdown
   - strong return
   - filter-house loop climb
11. Assemble sections clearly with contrast:
   - intros should be sparse
   - breakdowns should create a real valley before the payoff
   - drops/blooms should win through density and weight, not clutter
12. Use Strudel-native musical devices before adding more layers:
   - `chord(...).voicing()` for smoother voice leading
   - `rootNotes()` or `scaleTranspose()` when support parts should follow the harmony instead of being rewritten by hand
   - `note(...).s("..._pitched")` for tonal sample phrases
   - `clip()`, `end()`, and `begin()` to sculpt sample hits
   - `seg()` or `lpenv()` when a filter sweep should feel continuous rather than stepped per hit
   - `early()`, `off()`, `euclid()`, `stepcat()`, or `degradeBy()` to loosen hooks and hats before adding another lane
   - `swingBy()`, `late()`, `compressSpan()`, or `euclidRot()` when a groove needs feel, not more notes
   - `firstOf()`, `lastOf()`, `chunk()`, `sometimesBy()`, or `chooseCycles()` when one phrase should evolve across bars without becoming a new permanent lane
   - `layer()` only when one phrase needs a purposeful double, octave, or answer
   - `slice()` / `splice()` / `chop()` when a sampled phrase should become rhythmic identity
   - `orbit()` when drums, hooks, and atmosphere need cleaner separation; use `duckorbit()` only when the runtime really benefits from cross-orbit sidechain and it stays render-stable
13. Keep the file readable enough for a human to paste and tweak quickly

## Source-Material Study

When the brief contains a source-material study, treat it as higher-priority than generic reference cards.

Use headings like:

- `## Source Material Sources`
- `## Sourced Truths`
- `## Musical Inferences`
- `## Capability Gaps`

`Sourced Truths` should contain high-level traits you can defend from research.
`Musical Inferences` are your translation into composition choices.
`Capability Gaps` should be honest notes like:

- “current vocal chops are too generic for this lane”
- “pack fits the drum grammar better than the topline grammar”
- “this can capture pacing, not signature timbre”

These sections should make later revisions more accurate and more truthful.

## Strudel Quality Heuristics

Bias toward:

- one obvious hook carrier instead of many competing identity layers
- lane-specific role budgets: dominant roles first, support roles second, prune-first roles last
- hook-first drafts that can survive even if the critic is uncertain
- lane-specific sound choices instead of reusing the same repo accent for every genre
- motif reuse with transforms instead of section-by-section reinvention
- vocal, pluck, or stab phrases that evolve through timing, filtering, and clipping
- groove variation coming from `struct()`, `euclid()`, `stepcat()`, or light randomization before from extra layers
- bar-to-bar evolution using `firstOf()`, `lastOf()`, `chunk()`, `sometimesBy()`, or `chooseCycles()` before writing a brand-new phrase
- harmony that moves through voicing and inversion, not only root changes

## Musical Defaults

Default to these ownership rules unless the brief clearly wants something stranger:

- kick owns the downbeat and stays the clearest rhythmic anchor
- bass answers the kick instead of fighting it on every subdivision
- clap and snare accents define backbeat shape; percussion should move around them
- one lane, one job:
  - bass = pocket
  - stab or pad = harmonic bed
  - pluck or lead = hook articulation
  - vocal = accent, air, fragment, or answer
- breakdowns should subtract real weight, not just lower gain on every active lane
- returns should re-enter in stages instead of turning every part back on at once
- if the arrangement already has enough parts, prefer a phrase variant, mute pattern, filter move, or timing displacement instead of another layer

Avoid:

- solving every section by adding a new layer
- letting every song drift back toward airy house just because the pack supports it well
- using more than one primary hook carrier before the first one earns its place
- keeping discouraged or prune-first roles active just because the pack makes them easy to use
- flat tonal sample arrays for note-heavy parts when pitched families exist
- raw browser synths carrying the whole identity by default
- static sample tails that smear the groove because `clip()` / `end()` never got used
- treating every section change as an excuse for a brand-new lane instead of transforming one strong phrase

## Thread-First Defaults

When the user simply says “make me a song like ...”:

1. generate one canonical song by default
2. validate it automatically
3. do not show the full review artifact stack unless it matters
4. only run `song loop` automatically when:
   - the request explicitly asks for optimization
   - the first draft feels structurally shaky
   - the reference mix is unusually high-risk or underspecified
5. if confidence is low, you may silently branch 2 variants, choose the stronger one, and present one winner unless the result is genuinely ambiguous
6. if `song validate <slug> --json` reports `generation_strategy.mode = two_candidate_hidden`, treat hidden branching as the default, not the exception

Default user-facing closeout:

- link the song file
- link the brief
- give one short description of what it is aiming for
- mention whether it was only validated or also review-checked

## Validation

Run this after writing or revising the song:

```sh
node ./bin/glass-harbor.mjs song validate <slug> --json
```

If the user asked for optimization, or if the first pass clearly needs review, continue with:

```sh
node ./bin/glass-harbor.mjs song loop <slug> --max-iters 1 --json
```

If confidence is low and you need hidden branching, or if the user explicitly wants multiple directions, prefer:

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
