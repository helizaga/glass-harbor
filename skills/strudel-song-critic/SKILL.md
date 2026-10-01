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
3. `songs/<slug>/memory.json` if it exists
4. Attached example profiles in `examples/<slug>/profile.json` when the brief lists `## Example Targets`
5. The brief if the intent is unclear
6. [docs/strudel/technique-index.md](/Users/tommy/Documents/GitHub/song/docs/strudel/technique-index.md) when you need a fast Strudel-technique judgment
7. [docs/strudel/style-lanes.md](/Users/tommy/Documents/GitHub/song/docs/strudel/style-lanes.md) when deciding whether a song drifted into the wrong accent
8. Any source-material study in the brief when the song references a real artist, song, or style lane
9. Comparison or exploration artifacts if multiple candidates are involved
10. Reference cards only when they help choose between revision directions after examples/memory

## Core Job

Turn feedback into the smallest useful next move.

That usually means one of:

- revise the current winner in place
- promote the winner and stop changing it
- discard a weaker branch
- fix a runtime or contract blocker before discussing music

For thread-first generation, hidden review passes should collapse down to:

- strongest trait
- top weakness
- ready as-is, or one follow-up revision is still warranted

Do not default to surfacing the entire run artifact stack when a short conclusion is enough.

## Decision Rules

- Treat runtime or contract blockers as higher priority than musical taste notes.
- Prefer example-relative judgments over generic genre assumptions when example targets exist.
- If the brief contains `## Prompt References`, treat the temporary prompt style lens as the first style target before generic references.
- If the brief contains source-material study sections, judge against `Sourced Truths` first, then use `Musical Inferences` as the intended translation layer.
- Prefer one bounded musical change over a broad rewrite.
- Do not treat two medium-confidence heuristic findings as musical truth on their own; prefer review-gate over forced revision unless there is clear regression or a high-confidence issue.
- If the critique changed categories, that usually means progress.
  - Example: moving from weak contrast to low-end cleanup is real improvement.
- Use comparison artifacts to decide direction, not hunches.
- If a candidate already passes and is not provisional, prefer promotion over churn.
- Read the Strudel technique profile when present and judge whether the song is getting musical mileage from the language itself:
  - pitched sample roles vs flat sample slots
  - voicing-aware harmony vs static stacks
  - timing displacement vs rigid quantized hooks
  - groove transforms like `struct()`, `euclid()`, `stepcat()`, or `degradeBy()` vs layer accretion
  - clip/end/begin shaping vs full-length sample smear
  - motif transforms, `slice()` / `chop()`, and `layer()` / `off()` / `echoWith()` vs adding more layers
  - orbit or ducking discipline vs washing every lane through the same effect space

## Revision Guidance

When revising a song:

- keep the file directly pasteable into `https://strudel.cc/`
- preserve:
  - `samples('http://localhost:5432')`
  - required metadata comments
  - stable sampled roles
- keep the smallest clean set of edits that addresses the top critique finding
- avoid rewriting every section unless the critique clearly points to a structural miss
- when possible, solve a problem by improving the existing motif with Strudel techniques before adding another part

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
- cites example profiles or taste memory when they exist
- can explain the issue in Strudel terms, not just abstract taste language
- distinguishes sourced mismatch from inference mismatch
- preserves what already improved
- recommends one clear next action instead of vague “make it better”
- can be compressed into one short thread-facing note when the user did not ask for full scoring detail
