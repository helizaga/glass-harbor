---
name: taste-example-ingestor
description: Turn a song the user likes into a private Glass Harbor taste example under examples/<slug>/, then ingest it into a committed profile plus local analysis. Use when the user wants to teach the system their taste from a real song example.
---

# Taste Example Ingestor

Use this skill when the job is to capture a liked-song example for the critic.

## What To Read First

1. `examples/README.md`
2. `examples/example-template.md`
3. [AGENTS.md](/Users/tommy/Documents/GitHub/song/AGENTS.md)

## Output Contract

Committed:

- `examples/<slug>/example.md`
- `examples/<slug>/profile.json`

Local only:

- `examples/<slug>/clips/*.wav`
- `examples/<slug>/analysis.json`

## Workflow

1. Structure the user’s notes into `example.md`.
2. Tell the user or calling agent to place local clips under `examples/<slug>/clips/`.
3. Prefer clip names that carry section intent:
   - `anchor.wav`
   - `groove.wav`
   - `lift.wav`
   - `breath.wav`
   - `return.wav`
   - `outro.wav`
4. Run:

```sh
node ./bin/glass-harbor.mjs taste ingest <slug> --json
```

5. Surface the resulting `profile.json` and `analysis.json` summary back to the thread.

## Quality Bar

Good examples:

- capture why the user likes the song, not just what genre it is
- list preserve traits and anti-goals clearly
- use short private clips that make section intent obvious
- produce a profile the critic can compare against later
