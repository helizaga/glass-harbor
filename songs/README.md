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

## Folder Contract

Each song lives under its own folder:

- `songs/<slug>/<slug>.brief.md`
- `songs/<slug>/<slug>.strudel.js`

## Brief Contract

A song brief should stay short and agent-friendly. Use headings like:

- title
- genre
- mood
- bpm
- key or scale if relevant
- structure
- sonic goals
- stable sound roles
- review goals
- optional references

## Song Code Contract

Generated song files should:

- be valid Strudel code with no repo-specific JS wrappers
- be pasteable into Strudel web after `glass-harbor song serve`
- use stable runtime roles like `kick_main`, `clap_main`, `hat_closed`, and `riser_up`
- avoid vendor filenames and raw private paths
- include metadata comments at the top:
  - `@title`
  - `@genre`
  - `@bpm`
  - `@details`
  - `@sections`
- use readable named sections and layer constants rather than one giant anonymous `stack(...)`

`@sections` must stay machine-readable because the render loop uses it to cut section clips:

```js
// @sections intro:8, groove:16, breakdown:16, drop:16, outro:8
```

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
