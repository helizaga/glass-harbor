---
name: strudel-song-critic
description: Review or revise a canonical Glass Harbor song using run artifacts such as critique.json, revision-request.json, revision-prompt.md, and comparison results. Use when the task is to interpret feedback, choose the smallest useful musical change, or compare candidate songs and decide what should happen next.
---

# Strudel Song Critic

Use this skill when the job is to evaluate or revise an existing song in this repo, not to invent a brand-new workflow.

Primary inputs:

- `runs/<slug>/<timestamp>/critique.json`
- `runs/<slug>/<timestamp>/analysis.json`
- `runs/<slug>/<timestamp>/revision-request.json`
- `runs/<slug>/<timestamp>/revision-prompt.md`
- `runs/<slug>/comparisons/<timestamp>/comparison.json`
- `runs/<slug>/explorations/<timestamp>/explore.json`

## What To Read First

Read only what you need:

1. The canonical song file
2. The latest critique and revision package
3. The brief if the intent is unclear
4. Comparison or exploration artifacts if multiple candidates are involved
5. Reference cards only when they help choose between revision directions

## Core Job

Turn feedback into the smallest useful next move.

That usually means one of:

- revise the current winner in place
- promote the winner and stop changing it
- discard a weaker branch
- fix a runtime or contract blocker before discussing music

## Decision Rules

- Treat runtime or contract blockers as higher priority than musical taste notes.
- Prefer one bounded musical change over a broad rewrite.
- If the critique changed categories, that usually means progress.
  - Example: moving from weak contrast to low-end cleanup is real improvement.
- Use comparison artifacts to decide direction, not hunches.
- If a candidate already passes and is not provisional, prefer promotion over churn.

## Revision Guidance

When revising a song:

- keep the file directly pasteable into `https://strudel.cc/`
- preserve:
  - `samples('http://localhost:5432')`
  - required metadata comments
  - stable sampled roles
- keep the smallest clean set of edits that addresses the top critique finding
- avoid rewriting every section unless the critique clearly points to a structural miss

## Compare And Explore Guidance

When reading:

- `comparison.json`
- `explore.json`

focus on:

- winner slug
- readiness
- rank bucket
- weighted score
- primary liability
- next_action

If the compare result is `partial` or `blocked`, do not over-interpret the winner as musically settled.

## Commands

Common follow-up commands:

```sh
node ./bin/glass-harbor.mjs song revise <slug> --run <path> --json
node ./bin/glass-harbor.mjs song loop <slug> --max-iters 1 --json
node ./bin/glass-harbor.mjs song compare <slug> [<other-slug> ...] --json
node ./bin/glass-harbor.mjs song explore <slug> --count 3 --max-iters 1 --json
```

## Quality Bar

Good criticism in this repo:

- is specific
- is tied to actual run artifacts
- preserves what already improved
- recommends one clear next action instead of vague “make it better”
