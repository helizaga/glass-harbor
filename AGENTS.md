# Glass Harbor Agent Guide

## Purpose
- This repo is a paste-first Strudel songwriting scaffold for human + agent collaboration.
- The primary artifact is a single pasteable `songs/<slug>/<slug>.strudel.js` file generated from a short Markdown brief.
- Do not turn this into a GUI-first product. The local app is a debug surface, not the main workflow.
- The default user experience should be thread-first: when the user describes a song in plain language, treat that as the primary intake path and hide repo ceremony unless it is needed.
- For brief-to-song generation or revision, use the repo-local skill at `skills/strudel-songwriter/SKILL.md`.
- For interpreting critique/revision artifacts, use `skills/strudel-song-critic/SKILL.md`.
- For building retrieval memory, use `skills/reference-card-author/SKILL.md`.
- For ingesting songs the user likes into private taste memory, use `skills/taste-example-ingestor/SKILL.md`.
- Keep detailed Strudel-writing heuristics in `skills/strudel-songwriter/SKILL.md`; use this file for workflow and contract defaults, not for duplicating every musical rule.

## Canonical Workflow
1. If the user gives a freeform song request in the thread, normalize it into a brief and choose a slug automatically.
2. If the request names real songs, artists, or a specific style lane, research the source material first.
3. Write or update `songs/<slug>/<slug>.brief.md`.
4. Separate:
  - source-supported traits
  - your musical inferences
  - capability gaps in the current pack/tooling
5. Resolve the intended style lane and accent before writing so different songs do not collapse into the same repo accent.
6. Generate or revise the canonical song file at `songs/<slug>/<slug>.strudel.js`.
7. Keep the song directly pasteable into `https://strudel.cc/` after `glass-harbor song serve`.
8. Always run `glass-harbor song validate <slug> --json` after writing.
9. Only run `glass-harbor song loop <slug> --max-iters 1 --json` automatically when the user explicitly wants optimization or the first draft looks risky.
10. Start thread control with `glass-harbor song next <slug>` only when the task is in review / revision mode, not for every simple generation request.
11. Use `glass-harbor song status <slug>` when you need a fuller snapshot of approved baseline, pending review, open issues, taste memory, and active style lane.
12. When exploring multiple directions from one brief, prefer `glass-harbor song explore <slug>` for the full scaffold -> loop -> compare pass. If you need finer control, use `glass-harbor song variants <slug>` and `glass-harbor song compare <slug>` directly.
13. Use `glass-harbor song approve` and `glass-harbor song reject` to resolve review gates after the user answers in the thread.
14. Use the local app only for debugging, preload checks, pack switching, or SuperDirt verification.
15. Treat `songs/<slug>/memory.json` as the local baseline-memory source of truth for approved runs, pending review candidates, structured taste memory, and preferred/avoid style lanes.
16. When a brief lists `## Example Targets`, read the committed `examples/<slug>/profile.json` files before falling back to generic references.
17. Named real-song references from the current request are prompt-only by default. Keep them in the thread and brief; do not ingest them into `examples/` unless the user explicitly asks.
18. Prompt references now create a temporary per-song style lens automatically. Use that lane guidance during retrieval and critique, but do not treat it as durable taste memory.
19. For style-heavy prompts, prefer attached examples before generic reference cards.
20. If prompt references, examples, or vibe-heavy language make the request style-heavy, silently branch two drafts, compare them quickly, and present one winner.
21. Use `songs/arrangement-archetypes.md` as a hidden macro-structure scaffold when the prompt is strong on vibe but weak on arrangement.
22. When source-material research is performed, record it in the brief and preserve the high-level truths, lane boundaries, and known capability gaps in song memory instead of re-guessing them every run.

## Song Contract
- Song files must start with:
  - `@title`
  - `@genre`
  - `@bpm`
  - `@details`
  - `@sections`
  - `@section_roles`
- `@sections` must stay machine-readable, for example:
  - `// @sections intro:8, groove:16, breakdown:16, drop:16, outro:8`
- `@section_roles` must map every section to one of:
  - `anchor`
  - `groove`
  - `lift`
  - `breath`
  - `return`
  - `outro`
- Use readable named layers and section assembly.
- Do not add repo-specific wrappers or imports to authored song files.
- Do not hardcode scaffold paths or private-pack paths in song files.

## Stable Sample Roles
- Sampled material should use only:
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
- Optional tonal sample families are allowed when they improve hook quality without making the song vendor-specific:
  - `bass_tonal`
  - `stab_tonal`
  - `pluck_tonal`
- Prefer pitch-aware tonal sample families for note-driven hooks or harmony when the runtime pack provides them:
  - `bass_pitched`
  - `stab_pitched`
  - `pluck_pitched`
- Prefer sampled tonal families and `vocal_chop` over raw browser synth voices for the audible identity of the song.
- Treat `vocal_chop` as a small family of roles, not one lane: use contrasting vocal jobs such as airy bed, hook punctuation, breakdown fragment, or return accent when vocals matter.
- If a raw synth voice is necessary, keep it buried, filtered, and supportive instead of making it the lead sound.
- Song code must not reference vendor filenames or raw private sample paths.

## Strudel-Native Writing Bias
- Use Strudel as a musical pattern system, not just a layer container.
- Prefer strong motif transforms over adding more simultaneous parts.
- Prefer one hook-first idea that can survive human listening before trusting the critic to polish it.
- Reach for these techniques early when they fit the brief:
  - `chord(...).voicing()` for smoother harmonic motion
  - `rootNotes()` and `scaleTranspose()` when support parts should follow harmony cleanly
  - `note(...).s("..._pitched")` for tonal sample hooks
  - `clip()`, `end()`, and `begin()` to shape samples
  - `seg()` or `lpenv()` when a sweep needs to feel continuous, not stepped
  - `early()`, `off()`, `euclid()`, `euclidRot()`, `stepcat()`, `swingBy()`, `late()`, and `compressSpan()` for groove displacement and controlled variation
  - `firstOf()`, `lastOf()`, `chunk()`, `sometimesBy()`, and `chooseCycles()` when a phrase should evolve across bars instead of becoming a new full-time layer
  - `layer()` when one motif needs doubled or contrasted voices
  - `slice()`, `splice()`, or `chop()` when a sampled phrase should become a hook device
  - `orbit()` when drums, hooks, and atmosphere need clearer effect separation; use `duckorbit()` only when it actually improves the mix and stays render-stable
- Prefer fewer clearer phrase constants reused across sections instead of inventing a brand-new pattern for every section.

## Review Loop
- Default review flow is:
- `render -> analyze -> critique -> revise`
- For normal thread-first generation, keep this loop in the background. Do not dump review artifacts into the user-facing answer unless they materially affect the outcome.
- Deterministic analysis comes first.
- The richer MIR path expects a local Python environment such as `.glass-harbor-venv` with `scripts/requirements-analysis.txt` installed.
- If `GLASS_HARBOR_EMBEDDING_PROVIDER=mulan` is set but the backend is unavailable, keep going with deterministic MIR style scoring and treat confidence as lower.
- Audio-model critique is optional and should be treated as advisory, not the sole judge.
- `runs/` is gitignored and holds generated artifacts like `mix.wav`, `sections/*.wav`, `analysis.json`, `critique.json`, `verdict.json`, `verdict.md`, `summary.md`, `revision.md`, `revision-request.json`, and `revision-prompt.md`.
- Review-gate behavior is:
  - `review_gate`: the run improved and should be shown to the user before promotion
  - `revise`: keep iterating without user interruption
  - `abandon`: candidate is not good enough to beat baseline
  - `escalate_to_human`: the revision regressed or damaged protected strengths

## Thread Handoff
- Default answer after song creation:
  - link the song file
  - link the brief
  - one short note on what the song is aiming for
  - one short note on whether it was only validated or also review-checked
- Only surface `summary.md`, `verdict.md`, or deeper run artifacts when:
  - the run is blocked
  - the critic found a strong issue
  - the user asks how it scored

## Reference Cards
- `references/` contains abstract retrieval cards for prompting and critique.
- Keep cards high-level:
  - section maps
  - energy curves
  - role usage
  - groove notes
  - harmonic summaries
  - transition recipes
- Do not store copyrighted lyrics, full transcriptions, or commercial audio in the repo.

## Debug App
- `src/main.js` and the Vite app are secondary.
- Preserve the current pack-switching and debug behavior.
- Prefer smaller, purpose-built additions over turning the app into the core interface.

## Commands
- `glass-harbor song new <slug>`
- `glass-harbor song variants <slug>`
- `glass-harbor song validate <slug>`
- `glass-harbor song serve`
- `glass-harbor song render <slug>`
- `glass-harbor song analyze <slug>`
- `glass-harbor song critique <slug>`
- `glass-harbor song revise <slug>`
- `glass-harbor song status <slug>`
- `glass-harbor song next <slug>`
- `glass-harbor song approve <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--preserve-technique <technique>] [--avoid <trait>] [--avoid-technique <technique>] [--tradeoff <note>]`
- `glass-harbor song reject <slug> [--run <path>] [--reason <text>] [--preserve <trait>] [--preserve-technique <technique>] [--avoid <trait>] [--avoid-technique <technique>] [--tradeoff <note>]`
- `glass-harbor taste ingest <slug>`
- `glass-harbor song loop <slug>`
- `glass-harbor song compare <slug> [<other-slug> ...]`
- `glass-harbor song explore <slug> [--count <n>] [--max-iters <n>]`
- `glass-harbor debug ui`
- `glass-harbor debug osc`
- `npm run song:*` remains available as compatibility shims
- `npm run dev`

## Working Style
- Prefer modifying repo scripts and docs over embedding workflow rules in prompts.
- If a check can be deterministic, encode it in code or scripts instead of prose.
- Keep generated music code readable enough for a human to paste, inspect, and tweak quickly.
- When you finish a long-running command, surface `summary.md` or `verdict.md` to the user instead of raw artifact spelunking.
- Prefer preserving and extending recorded taste memory over re-inventing the user’s preferences from scratch each run.
- Prefer one strong draft over exposing multiple candidates to the user unless they explicitly ask for options.
- For artist or song references, be explicit about what came from sources versus what is your inference.
- Do not imply the current pack/tooling can authentically reproduce a lane if the source-material study says otherwise.
