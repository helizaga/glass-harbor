# Songs Workflow

This repository is designed around a code-first songwriting loop:

1. write or refine a short Markdown brief
2. generate one pasteable `.strudel.js` song file
3. run `glass-harbor song serve`
4. paste the song file into `https://strudel.cc/`
5. optionally use the local app for debugging or SuperDirt verification
6. optionally run `render -> analyze -> critique -> revise` to prepare the next agent edit pass
7. when you want multiple directions from one brief, scaffold sibling variants and compare them instead of endlessly revising one draft
8. if you want the whole branch-and-rank pass in one command, use `glass-harbor song explore <slug>`

For normal Codex thread use, this should feel simpler than the raw CLI:

1. user describes the song in plain language
2. agent turns that into a brief and chooses a slug
3. agent writes one canonical song by default
4. agent validates it automatically
5. agent only runs the full review loop when the draft is weak, risky, or explicitly needs optimization
6. user sees the song plus a short note, not the full artifact stack unless it matters

## Folder Contract

Each song lives under its own folder:

- `songs/<slug>/<slug>.brief.md`
- `songs/<slug>/<slug>.strudel.js`

## Brief Contract

A song brief should stay short and agent-friendly. Use headings like:

- title
- genre
- style lane
- accent
- mood
- bpm
- key or scale if relevant
- structure
- hook identity
- low-end plan
- what to withhold until return
- breakdown subtraction plan
- source material sources
- sourced truths
- musical inferences
- capability gaps
- example targets
- sonic goals
- stable sound roles
- review goals
- prompt references
- optional references

## Song Code Contract

Generated song files should:

- be valid Strudel code with no repo-specific JS wrappers
- be pasteable into Strudel web after `glass-harbor song serve`
- use stable runtime roles like `kick_main`, `clap_main`, `hat_closed`, and `riser_up`
- prefer `bass_tonal`, `stab_tonal`, `pluck_tonal`, `bass_pitched`, `stab_pitched`, `pluck_pitched`, and `vocal_chop` over obvious raw browser synth timbres when the song needs tonal identity
- prefer lane-specific subsets of the pack instead of reusing the same accent in every song
- prefer `bass_pitched` over `bass_tonal` when the bassline is note-driven or harmonically important; keep `bass_tonal` for simpler character-shot behavior
- when vocals matter, split `vocal_chop` into 2-3 contrasting roles such as airy bed, hook punctuation, breakdown fragment, or return accent instead of one repeating lane
- keep one lane, one job by section:
  - bass owns pocket
  - stab or pad owns the bed
  - pluck or lead owns hook articulation
  - vocal owns accent, air, or response
- avoid vendor filenames and raw private paths
- include metadata comments at the top:
  - `@title`
  - `@genre`
  - `@bpm`
  - `@details`
  - `@sections`
  - `@section_roles`
- use readable named sections and layer constants rather than one giant anonymous `stack(...)`
- prefer Strudel-native phrase shaping and transforms before adding more layers:
  - `chord(...).voicing()`
  - `rootNotes()`, `scaleTranspose()`
  - `note(...).s("..._pitched")`
  - `clip()`, `end()`, `begin()`
  - `seg()`, `lpenv()` when filter motion should feel continuous
  - `early()`, `off()`, `euclid()`, `euclidRot()`, `stepcat()`, `degradeBy()`
  - `swingBy()`, `late()`, `compressSpan()`
  - `firstOf()`, `lastOf()`, `chunk()`, `sometimesBy()`, `chooseCycles()` when one phrase should evolve across bars without becoming a permanent new lane
  - `layer()`
  - `slice()`, `splice()`, `chop()` when a sample should become rhythmic identity
  - `orbit()` when wet lanes need separation; `duckorbit()` only when it is worth the runtime cost and stays render-stable

`@sections` must stay machine-readable because the render loop uses it to cut section clips:

```js
// @sections intro:8, groove:16, breakdown:16, drop:16, outro:8
// @section_roles intro:anchor, groove:groove, breakdown:breath, drop:return, outro:outro
```

`## Example Targets` is optional, but if present it should list example slugs from `examples/` so the critic can score the song against your liked-song profiles before falling back to generic reference cards.

`## Prompt References` is also optional. Use it for named songs or artists the user cited in the current request, plus short notes for:

- what to borrow structurally or texturally
- what not to copy literally

These prompt references are ephemeral by default. They belong in the brief for this song, not in `examples/`, unless the user explicitly asks to teach that taste permanently.
The tool will turn them into a temporary per-song style lens so retrieval and critique can respond to that prompt without polluting durable taste memory.

When real artists, songs, or style lanes matter, add a source-material study to the brief:

- `## Source Material Sources`
- `## Sourced Truths`
- `## Musical Inferences`
- `## Capability Gaps`

This keeps the workflow honest about:

- what came from research
- what is your translation into a song
- what the current pack or workflow cannot yet do convincingly

If the brief has either `## Example Targets` or style-heavy `## Prompt References`, treat the draft as a likely hidden-branching case:

- write one rhythm/percussion-forward candidate
- write one harmony/melody-forward candidate
- keep the better one unless the user explicitly asked for multiple options

When revising a song, prefer:

- transforming an existing motif over adding a fresh competing part
- improving voicing or timing before widening the stack
- shaping sample tails before turning parts down globally
- changing mute choreography or density before adding a new full-time lane

## Optional Debugging

The local app under `npm run dev` is now a secondary tool. Use it for:

- local auditioning
- preload checks
- SuperDirt verification
- pack switching checks

## Review Loop

The agent review loop is:

1. render the canonical song file
2. analyze the audio with deterministic metrics
3. score the run and generate bounded revision actions
4. run `glass-harbor song revise <slug>` to write an agent-ready revision package
5. hand that revision package back to the songwriter skill or a human editor

For default thread-first song generation, do not run this loop automatically unless:

- the user asks for optimization
- the first pass clearly looks structurally shaky
- the request is vague enough that one hidden review pass materially reduces risk

## Variants And Comparison

When one idea needs several candidates:

1. run `glass-harbor song variants <slug>`
2. edit or regenerate the sibling variant songs
3. run the normal loop on each variant slug
4. run `glass-harbor song compare <slug>` to rank the latest reviewed candidates

`song compare` can also compare explicit slugs, for example:

- `glass-harbor song compare open-water-signal horizon-answer`

If you want one command to scaffold, loop, and compare:

- `glass-harbor song explore glass-harbor --count 3 --max-iters 1`
