---
name: mashup-dj
description: Plan, render, and iterate hip hop / EDM mashups, drops, vocal chops, and DJ transitions with the glass-harbor CLI. Use when the user asks for a mashup, acapella-over-beat, blend, transition, drop, chops, or DJ mix of specific songs.
---

# Mashup + DJ transition workflow

The agent is the planner; the CLI is the deterministic engine. You cannot hear audio, so lean on analysis and QA,
say what you could not verify, and treat the user's ears as the final judge.

## 0. Source audio

- Work only from audio files the user provides (local paths). Never download copyrighted music; ask the user to
  drop files somewhere and give you the paths.
- Official acapellas/instrumentals beat separated stems; register them with `--stem vocals=<file>` or
  `--stem instrumental=<file>`.

## 1. Ingest and sanity-check

```sh
glass-harbor track add <file> [--id <slug>]        # decode + beat grid + key + sections
glass-harbor track show <id>                        # sections, vocal phrases, grid notes
```

Check before planning:
- **bpm half/double**: hip hop often analyzes at 70-80 or 140-160; trap at 70/140; DnB at 87/174. Pairing via
  `tempo_ratio` (2 or 0.5) is normal and is not a stretch.
- **key confidence** below ~0.3 means the key is a guess (common for rap/drum-heavy tracks); trust chroma less.
- **grid** `variable` means the track drifts (live drums); keep clips short or expect QA grid notes.

Also check `drops` (bars where kick and bass return; hooks and transitions want to land there) and, for beds
where structure matters, re-run with `--sections allin1` for verse/chorus labels.

## 2. Stems, cleanup, lyrics (only what the plan needs)

```sh
glass-harbor track separate <vocal-track> --stems vocals          # acapella for a mashup
glass-harbor track separate <bed-track> --stems instrumental      # only if the bed is not already an instrumental
glass-harbor track separate <id> --stems vocals,drums,bass        # stem-swap transitions
```

`--quality balanced` (default) is one BS-RoFormer pass per stem (~3-4 min each on an M1 Pro). `--quality best` runs the
community two-model RoFormer ensembles (~10 min/track) for the final acapella. EQ blends need no stems.

```sh
glass-harbor track clean <vocal-track>     # de-reverb: drier acapellas sit tighter on dry club beats
glass-harbor track lyrics <vocal-track>    # word timings, lyric-based phrases, repeated lines = hooks
```

Plan vocal placement from the lyric lines (`track lyrics` prints each line's bar span), not from bar energy: rap
vocals run wall to wall, so only the words show where verses, hooks, and title drops are. Never copy lyrics into
committed files; refer to lines by bar.

## 3. Pick pairings

```sh
glass-harbor match <vocal-track> --role vocals    # which beds fit this acapella (key, tempo, chroma)
glass-harbor match <track> --role next            # what blends well after this track
```

## 4. Scaffold, then make it musical

```sh
glass-harbor mix new <slug> --kind mashup --vocals <a> --bed <b>
glass-harbor mix new <slug> --kind transition --tracks <a> <b> [--style blend|cut|echo|filter]
glass-harbor mix new <slug> --kind set --tracks <a> <b> <c> [--styles blend,echo] [--play-bars 32]
```

The scaffold is a starting point. Edit `mixes/<slug>/<slug>.mix.json` (format: `docs/plan-format.md`) and record
intent in `<slug>.brief.md` (what came from analysis vs your musical inference).

### Mashup craft
- The bed sets the tempo and groove; move the vocal, not the beat. Keep vocal stretch within about ±6%; beyond
  that use `tempo_ratio` or pick another bed.
- Rap verses tolerate key mismatch; sung hooks and melodic ad-libs do not. Aim for Camelot distance <= 1 on any
  melodic part; shift the acapella at most ±2 semitones.
- Land vocal phrases on the bed's phrase lines (bars 1, 9, 17, 25, ...). Put the hook over the bed's
  highest-energy section; verses over mid-energy sections. Use `pre_beats` for pickups that start before the bar.
- Give the beat room: 8 bars of bed before the first vocal, breathing bars between sections, a bed or
  vocal-tag outro.
- High-pass the acapella at 100-120 Hz to remove separation rumble. Prefer the bed's `instrumental` stem over its
  full mix unless the bed is already an instrumental.
- Never stack two lead vocals unless it is a deliberate call-and-response.
- **Vocal chops** (`chop` clips, see `docs/plan-format.md`): the EDM move for builds, drops, and fills. Pick one or
  two short, punchy syllables (the title word, an ad-lib), slice them at 1/16-1/8 note lengths, and sequence them on
  a 16th-step pattern. Keep chops off the lead vocal's bars, high-pass them (~200 Hz), add a little tempo-synced
  echo, and pitch individual hits (0, +3, +5, +7 semitones) for a melodic hook in the track's key.

### Transition craft
- **EDM -> EDM**: 16-32 bar blends starting on a section boundary; incoming bass killed (`eq_low_db -40`); swap
  basses on a downbeat at the blend midpoint; high-pass the outgoing track; never two basslines.
- **Hip hop**: shorter blends (4-8 bars) or cuts on the one; drop the incoming track on its hook or first verse.
- **Tempo gaps over ~6%** (hip hop <-> house): echo-out the last bar and step the tempo, or use half/double time.
- **Harmonic mixing**: long blends need Camelot ±1 or relative major/minor; clashing keys get short, percussive
  overlaps or cuts.
- After a blend, ramp to the incoming track's own tempo over ~8 bars (the scaffold does this).

### Drops
- Land hooks and transitions on detected drops (`track show`). To make a drop where the bed has none, or to hype
  one, `glass-harbor mix drop <slug> --at-bar N --build-bars 8`: high-pass build, a beat of silence, generated
  riser, impact on the one. A chop roll (8ths then 16ths, pitched up) in the last two bars of the build stacks well
  with it.

## 5. Validate, render, read QA

```sh
glass-harbor mix validate <slug>
glass-harbor mix render <slug> --start-bar 13 --end-bar 32    # quick preview of the critical section
glass-harbor mix render <slug> [--clips]                      # full render (+ aligned clip WAVs for a DAW)
```

Read `runs/<slug>/<stamp>/qa.md`. Fix every `error`; resolve or consciously accept each `warning`:
- `source beat grid ... off`: re-check bar 1 (`downbeat_shift`) or the track's grid notes.
- `overlap pile-up`: pull one side down 2-4 dB or cut its lows.
- `two basslines` / `two vocals`: automate `eq_low_db` / `gain_db`.
- loudness misses usually mean the sources are very dynamic; that is fine for a demo.

## 6. Hand off and iterate on ears

Link the `mix.mp3`, the plan, and the brief. Say what QA checked and what only listening can confirm (vocal
pocket, groove feel, whether the hook lands). Point the user at `glass-harbor mix review <slug>` to comment on
time ranges (or take comments from chat with `glass-harbor mix comment <slug> "..." --at 1:12`). Then:

1. `glass-harbor mix feedback <slug>`: each open comment comes with its bar range and the clips playing there.
2. Change the plan to address each one; re-render.
3. `glass-harbor mix resolve <slug> <ids> --note "what changed"`.
4. A general preference ("always 8-bar blends", "less ducking") goes into `glass-harbor taste set|add`.

For posting: `glass-harbor mix video <slug>` makes a 1080x1920 visualizer; `mix export` hands stems + tempo map to
a DAW. Mixcloud licenses DJ mixes; SoundCloud and YouTube often take down or claim mashups.
