# Glass Harbor

Agent-first workspace for **hip hop and EDM mashups and DJ transitions** built from songs you already have. An LLM
agent writes a short plan in bars; the `glass-harbor` CLI does the audio work locally and checks every render.

- **analysis**: beat/downbeat grid ([beat_this](https://github.com/CPJKU/beat_this)) with fixes for tempo-octave
  flips, key + Camelot ([S-KEY](https://github.com/deezer/skey), vendored), loudness, per-bar energy, drops
  (kick + bass returns), sections (novelty, or verse/chorus labels from
  [allin1](https://github.com/mir-aidj/all-in-one)), lyrics with word timings (local Whisper) and hooks
- **stems**: [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) with unwa's
  Resurrection BS-RoFormer models (default) or the community RoFormer ensembles, BS-RoFormer SW for drums/bass/other,
  RoFormer de-reverb for acapellas
- **matching**: AutoMashUpper-style fit (tempo incl. half/double time, Camelot distance, chroma; key matters less
  for rap), set ordering by key, tempo and energy flow
- **rendering**: beat-by-beat warping with the Rubber Band R3 engine (sub-millisecond beat placement), pitch shift
  with formant preservation, tempo maps (steps and ramps), a DJ-mixer channel strip (HP/LP filters, 3-band EQ,
  gain automation, tempo-synced echo, reverb), vocal chops (slices or lyric words on a 16th-step pattern), ducking
  the beat under the vocal, generated risers/downlifters/impacts and a one-command drop builder, glue compression
  and a true-peak limiter
- **QA**: plan validation (two basslines, two vocals, key clashes, audible stretch, silence) and post-render checks
  (beat alignment of every clip, buried vocals, loudness, true peak, dead air, pile-ups)
- **listener loop**: a local review page (waveform, bar grid, clip lanes, A/B) where comments pinned to time ranges
  map to bars and clips for the agent; verdicts and taste defaults feed future scaffolds
- **hand-offs**: aligned stems + tempo-map MIDI for Logic/Ableton, and a visualizer video for Shorts or YouTube

Everything except the LLM is free and runs on your machine. Audio, stems and lyrics never leave `library/` and
`runs/` (both gitignored).

## Setup

```sh
brew install ffmpeg rubberband
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -e '.[ml,lyrics,structure,master,dev]'
.venv/bin/glass-harbor doctor
```

Exact, tested versions (macOS arm64, Python 3.11) are pinned in `requirements.lock`:
`.venv/bin/pip install -r requirements.lock && .venv/bin/pip install -e . --no-deps`. On Windows/Linux the
`lyrics` extra installs faster-whisper instead of the Apple Silicon build.

First use downloads model weights into `~/.cache` (beat tracker ~80 MB, two ~200 MB BS-RoFormer models, de-reverb,
Whisper large-v3-turbo ~1.6 GB, and ~1.7 GB more for `--quality best`). On an M1 Pro: separation ~4 min per stem
pass, Whisper ~1 min, allin1 ~2 min. A full mashup render takes about a minute; clips are rendered in parallel
and cached in `runs/<slug>/.clip-cache`, so a re-render after a small edit only redoes what changed.

## One command

```sh
glass-harbor auto ~/Downloads/vocal-song.flac ~/Downloads/beat-song.flac
```

Separates both records, transcribes the vocal, drafts the mashup on the beat's structure, renders, fixes what QA
finds (up to two rounds), and prints the phone file, the full-quality file, the plan, and the brief.

## Quick start: acapella over a beat

```sh
glass-harbor track add ~/Downloads/janice-stfu.flac --id janice-stfu
glass-harbor track add ~/Downloads/keep-workin.flac --id keep-workin --sections allin1
glass-harbor track separate janice-stfu --stems vocals
glass-harbor track clean janice-stfu                  # de-reverb the acapella
glass-harbor track lyrics janice-stfu                 # word timings + hooks
glass-harbor track separate keep-workin --stems instrumental
glass-harbor match janice-stfu --role vocals
glass-harbor mix new janice-x-keep-workin --kind mashup --vocals janice-stfu --bed keep-workin
glass-harbor mix drop janice-x-keep-workin --at-bar 92
glass-harbor mix render janice-x-keep-workin
glass-harbor mix review janice-x-keep-workin          # listen, A/B, comment on time ranges
```

The agent edits `mixes/<slug>/<slug>.mix.json`, re-renders, and works through your comments
(`glass-harbor mix feedback <slug>`). Renders land in `runs/<slug>/<stamp>/` with `mix.mp3`, `mix.wav`, and `qa.md`.

## DJ transitions and sets

```sh
glass-harbor set order t1 t2 t3 t4                                         # suggested play order
glass-harbor mix new a-into-b --kind transition --tracks track-a track-b
glass-harbor mix new friday --kind set --tracks t1 t2 t3 t4 --styles blend,echo,blend --play-bars 32
glass-harbor mix render friday --start-bar 25 --end-bar 48                 # preview one transition
```

Styles: `blend` (EQ bass swap, 16 bars for EDM, 8 for hip hop), `cut` (drop the next track on its hook), `echo`
(echo-out + tempo step, for hip hop <-> house jumps), `filter` (low-pass the outgoing track, then cut).

## Hand-offs

```sh
glass-harbor mix render <slug> --clips && glass-harbor mix export <slug>   # WAVs + tempo.mid for a DAW
glass-harbor mix video <slug>                                             # 1080x1920 visualizer (--landscape)
```

## Layout

```text
glass_harbor/        CLI and engine (analysis, grid, keys, lyrics, separation, plan, scaffold, render, fx, QA,
                     review page, export); vendor/skey = S-KEY (MIT)
skills/mashup-dj/    agent workflow + mashup/transition craft rules
docs/plan-format.md  plan schema
mixes/<slug>/        plans and briefs (committed)
taste.json           your defaults, preferences, and verdict history (committed)
library/<id>/        decoded audio, stems, lyrics, analysis (local only)
runs/<slug>/<stamp>/ renders, render.json, qa.md, feedback.json, daw/, video (local only)
tests/               pytest suite on synthetic audio
```

## Tests

```sh
.venv/bin/python -m pytest
```

The repo previously generated original songs with Strudel; that code lives in git history before this pivot.
