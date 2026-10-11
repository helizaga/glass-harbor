# Glass Harbor Agent Guide

## Purpose
- This repo is an agent-first workspace for **hip hop / EDM mashups and DJ transitions** built from songs the user
  already has.
- The agent plans; the `glass-harbor` CLI analyzes, separates, renders, and checks deterministically.
- The primary artifact is a declarative plan at `mixes/<slug>/<slug>.mix.json` plus a short
  `mixes/<slug>/<slug>.brief.md`. Rendered audio lives in gitignored `runs/`.
- Use the repo-local skill `skills/mashup-dj/SKILL.md` for the workflow and the mixing craft rules.
- Plan schema: `docs/plan-format.md`.

## Ground rules
- Work only from audio files the user provides. Never download copyrighted music; ask for local file paths.
- Source audio, stems, and analysis stay in the gitignored `library/`. Never commit audio.
- Everything runs locally and free (python-audio-separator RoFormer/Demucs, beat_this, librosa, Rubber Band,
  pedalboard). Do not add paid services; the only paid tool in the loop is the user's LLM subscription.
- You cannot listen. Report what QA verified, what it cannot (groove feel, vocal pocket, whether the hook lands),
  and ask for ear feedback.
- For named songs, separate source-supported facts (library analysis, cited sources) from your inferences in the
  brief.

## Canonical workflow
1. Turn the request into a slug and a brief; list the tracks and the intended moment (energy, setting).
   Read `taste.json` (defaults, preferences, past verdicts) before planning. When suggesting songs, follow
   "Choosing songs" in the skill (Beatport + kworb first, 1001Tracklists to check a pairing is proven, not overdone).
2. `glass-harbor track add <files>` (`--sections allin1` for beds whose structure matters); check
   `glass-harbor track show <id>` (bpm half/double, key + confidence, grid notes, drops).
3. Separate only what the plan needs (`track separate <id> --stems vocals`), `track clean <id>` the acapella,
   and `track lyrics <id>` for hooks and word-level chops.
4. `glass-harbor match` / `glass-harbor set order` to confirm pairings; `glass-harbor mix new` to scaffold.
5. Edit the plan by DJ/mashup craft (skill), add drops with `glass-harbor mix drop`, then `mix validate`.
6. `glass-harbor mix render <slug>` (use `--start-bar/--end-bar` for quick previews), then read `qa.md`.
7. Hand off; the user listens in `glass-harbor mix review <slug>` and comments. Read them with
   `glass-harbor mix feedback <slug>`, revise, re-render, `glass-harbor mix resolve <slug> <ids>`.
8. When a comment states a general preference, record it with `glass-harbor taste add "..."` (or `taste set`).

## Thread handoff
- Link the rendered `mix.mp3` (or `mix.wav`), the plan, and the brief.
- One line on the musical idea, one line on what QA found, one line on what needs the user's ears.
- Only dump `render.json`/`qa.json` details when something failed or the user asks.

## Setup
```sh
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -e '.[ml,lyrics,structure,master,dev]'
brew install ffmpeg rubberband
.venv/bin/glass-harbor doctor
```
Use a Python build with SSL (Homebrew); the pyenv 3.11.3 build on this machine lacks it.

## Commands
- `glass-harbor doctor`
- `glass-harbor track add <files...> [--id] [--stem name=path] [--separate stems] [--quality fast|balanced|best] [--sections novelty|allin1]`
- `glass-harbor track analyze <ids...>|--all [--force] [--beats auto|beat_this|librosa] [--sections novelty|allin1]`
- `glass-harbor track separate <id> [--stems vocals,instrumental,drums,bass,other] [--quality ...]`
- `glass-harbor track clean <id> [--stem vocals] [--mode dereverb|dereverb-gentle|deecho|denoise]`
- `glass-harbor track lyrics <id> [--force]`
- `glass-harbor track list` / `glass-harbor track show <id>`
- `glass-harbor match <id> [--role vocals|bed|next] [--against ids...]`
- `glass-harbor set order <ids...> [--start <id>]`
- `glass-harbor mix new <slug> --kind mashup|transition|set ...`
- `glass-harbor mix drop <slug> --at-bar N [--build-bars 8] [--silence-beats 1] [--clips ids]`
- `glass-harbor mix validate <slug>`
- `glass-harbor mix render <slug> [--start-bar N --end-bar M] [--clips] [--no-mp3]`
- `glass-harbor mix check <slug> [--run <dir>]`
- `glass-harbor mix review <slug>` (local page) / `mix comment` / `mix feedback` / `mix resolve`
- `glass-harbor mix export <slug>` (DAW stems + tempo.mid) / `glass-harbor mix video <slug> [--landscape]`
- `glass-harbor taste [show|set name=value|add "preference"]`
- Every command accepts `--json` for machine-readable output.

## Working style
- If a check can be deterministic, encode it in `glass_harbor/` (validation or QA), not in prose.
- Keep plans readable: named clips, phrase-aligned bars, automation only where it does a job.
- Run `.venv/bin/python -m pytest` after code changes.
