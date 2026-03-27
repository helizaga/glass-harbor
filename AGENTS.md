# Glass Harbor Agent Guide

## Purpose
- This repo is a paste-first Strudel songwriting scaffold for human + agent collaboration.
- The primary artifact is a single pasteable `songs/<slug>/<slug>.strudel.js` file generated from a short Markdown brief.
- Do not turn this into a GUI-first product. The local app is a debug surface, not the main workflow.
- For brief-to-song generation or revision, use the repo-local skill at `skills/strudel-songwriter/SKILL.md`.
- For interpreting critique/revision artifacts, use `skills/strudel-song-critic/SKILL.md`.
- For building retrieval memory, use `skills/reference-card-author/SKILL.md`.

## Canonical Workflow
1. Read the brief at `songs/<slug>/<slug>.brief.md`.
2. Generate or revise the canonical song file at `songs/<slug>/<slug>.strudel.js`.
3. Keep the song directly pasteable into `https://strudel.cc/` after `glass-harbor song serve`.
4. Use `glass-harbor song render`, `glass-harbor song analyze`, `glass-harbor song critique`, and `glass-harbor song revise` for review passes.
5. Start thread control with `glass-harbor song next <slug>` so the agent chooses one explicit next move instead of stitching the workflow manually.
6. Use `glass-harbor song status <slug>` when you need a fuller snapshot of approved baseline, pending review, and open issues.
7. When exploring multiple directions from one brief, prefer `glass-harbor song explore <slug>` for the full scaffold -> loop -> compare pass. If you need finer control, use `glass-harbor song variants <slug>` and `glass-harbor song compare <slug>` directly. The compare command includes the base song by default when reading `variants.json`.
8. Use `glass-harbor song approve` and `glass-harbor song reject` to resolve review gates after the user answers in the thread.
9. Use the local app only for debugging, preload checks, pack switching, or SuperDirt verification.
10. Treat `songs/<slug>/memory.json` as the local baseline-memory source of truth for approved runs and pending review candidates.

## Song Contract
- Song files must start with:
  - `@title`
  - `@genre`
  - `@bpm`
  - `@details`
  - `@sections`
- `@sections` must stay machine-readable, for example:
  - `// @sections intro:8, groove:16, breakdown:16, drop:16, outro:8`
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
- Song code must not reference vendor filenames or raw private sample paths.

## Review Loop
- Default review flow is:
- `render -> analyze -> critique -> revise`
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
- `glass-harbor song approve <slug> [--run <path>] [--reason <text>]`
- `glass-harbor song reject <slug> [--run <path>] [--reason <text>]`
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
