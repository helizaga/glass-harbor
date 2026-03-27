# Songs Workflow

This repository is designed around a code-first songwriting loop:

1. write or refine a short Markdown brief
2. generate one pasteable `.strudel.js` song file
3. run `glass-harbor song serve`
4. paste the song file into `https://strudel.cc/`
5. optionally use the local app for debugging or SuperDirt verification

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
4. hand the revision brief back to the songwriter skill or a human editor
