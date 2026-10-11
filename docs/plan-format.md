# Mix plan format (`mixes/<slug>/<slug>.mix.json`)

A plan places **clips** (a bar range of one stem of one library track) on an output bar grid. Everything is in
bars; the renderer turns bars into seconds with each track's beat grid, so every clip lands on the beat after
time-stretching. `glass-harbor mix validate <slug>` checks all of this and applies DJ rules (bass clashes, vocal
overlaps, key clashes, audible stretch, silence).

```json
{
  "version": 1,
  "title": "Janice STFU x Keep Workin'",
  "kind": "mashup",
  "bpm": 122,
  "beats_per_bar": 4,
  "sources": {
    "vox": {"track": "janice-stfu", "semitones": -1, "tempo_ratio": 1, "downbeat_shift": 0, "gain_db": 0},
    "bed": {"track": "keep-workin"}
  },
  "clips": [
    {"id": "bed", "source": "bed", "stem": "mix", "from_bar": 1, "bars": 72, "at_bar": 1,
     "automation": {"gain_db": [[64, 0], [72, -40]]}},
    {"id": "verse", "source": "vox", "stem": "vocals", "from_bar": 9, "bars": 16, "at_bar": 17, "pre_beats": 1,
     "automation": {"highpass_hz": [[0, 110]]}, "fx": {"reverb": {"mix": 0.08}}}
  ],
  "master": {"lufs": -9, "ceiling_db": -1},
  "notes": ["free text for the next agent / human"]
}
```

## Top level

| field | meaning |
|---|---|
| `kind` | `mashup`, `transition`, or `set` (informational; the format is the same) |
| `bpm` | constant output tempo, **or** |
| `tempo` | tempo map: `[{"bar": 1, "bpm": 92}, {"bar": 33, "bpm": 128}, {"bar": 41, "bpm": 130, "ramp": true}]`. A point without `ramp` is a step change on that bar line (cuts, echo-outs); `ramp: true` ramps linearly from the previous point |
| `beats_per_bar` | 4 (or 3) |
| `master.lufs` | integrated loudness target (default -9); the limiter never applies more than 6 dB of gain reduction, QA flags a miss |
| `master.ceiling_db` | true-peak ceiling (default -1) |
| `master.match_loudness` | default `true`: every source is first matched to -14 LUFS so clip gains are relative |
| `master.glue` | default `true`: gentle bus compression (about 1 dB) before the true-peak limiter |
| `master.reference` | a library track id (or `{track, stem}`): Matchering matches tonal balance and width to that released master; without `lufs`, its loudness becomes the target (clamped to -14..-7) |
| `master.mono_bass_hz` | default `120`: everything below is folded to mono (club systems); `0` turns it off |
| `master.soft_clip` | default `true`: a soft clipper shaves the sharpest transients before the limiter |
| `master.tame_harshness` | default `true`: a dynamic cut of 2-5 kHz (max 3 dB) only when that band jumps above its usual share |
| `master.stream_version` | default `true`: also writes `mix-stream.wav/mp3` at -14 LUFS with bass harmonics for phones |
| `edits` | `[{"type": "tape_stop", "at_bar": 64.5, "beats": 2}]`: the whole mix brakes to a stop |

## Sources

| field | meaning |
|---|---|
| `track` | library track id |
| `semitones` | pitch shift for every clip from this source (formants preserved on vocals) |
| `tempo_ratio` | output beats per source beat: `2` plays a 70 bpm track in a 140 bpm mix (half-time), `0.5` the reverse |
| `downbeat_shift` | move bar 1 by N beats if the tracker picked the wrong beat as "one" |
| `gain_db` | gain for all clips from this source |

## Clips

| field | meaning |
|---|---|
| `source`, `stem` | stem is `mix` (default), `vocals`, `instrumental`, `drums`, `bass`, `other` |
| `from_bar`, `bars` | source bar range (bar 1 = the track's first downbeat; see `glass-harbor track show`) |
| `at_bar` | output bar where `from_bar` lands |
| `pre_beats` | also play N beats before `from_bar` (vocal pickups), placed before `at_bar` |
| `loop` | repeat the range N times (bed loops) |
| `gain_db`, `fade_in_beats`, `fade_out_beats` | static level and edge fades |
| `automation` | DJ-mixer channel strip, `param: [[bar_offset, value], ...]`, offsets in output bars from `at_bar` (pickup beats are negative), linear (log for Hz) interpolation |
| `fx` | `echo: {beats, feedback, mix}` (tempo-synced), `reverb: {mix, room}` |
| `tail_beats` | keep rendering N beats after the clip for fx tails (default 8 when fx are set, 4 for vocal chains) |
| `chain` | vocal processing: `rap` (default on vocal clips), `hook` (more plate + throws + detuned doubles), `dry` (default on chops: EQ, de-ess, compression only), `none` |
| `doubles` / `octave` | override the hook doubles; `octave: true` adds an octave-down layer at -15 dB |
| `tune` | light pitch correction toward the source key (0 = off, 1 = hard); only steady sung notes move |
| `nudge_ms` | shift a clip earlier (-) or later (+) by up to 60 ms to sit in the pocket |
| `semitones` | per-clip pitch shift on top of the source's (key lift: `mix edit <slug> lift --at-bar N`) |
| `punch` | `{attack_db, parallel}`: transient shaping + parallel compression below 900 Hz (kick and snare body, not the hats) |
| `word_safe` | default `true` on vocal clips: edges move so no word is cut (lyrics), or to the nearest quiet point |
| `ride` | default `true` on vocal clips: phrase-level gain riding (up to ±6 dB) to an even level |

Automation parameters: `gain_db`, `arrange_db`, `highpass_hz`, `lowpass_hz`, `eq_low_db` (shelf at 180 Hz),
`eq_mid_db` (peak at 1 kHz), `eq_high_db` (shelf at 4.5 kHz), `width` (0 = mono, 1 = as recorded, up to 2). `-40` on `eq_low_db` is a DJ bass kill; validation treats
`eq_low_db <= -15`, `highpass_hz >= 150`, or `gain <= -20` as "bass out of the way".

## Vocal chops

A clip with a `chop` object triggers short slices of one stem on a step pattern instead of playing a range:

```json
{"id": "janice-chops", "source": "vox", "stem": "vocals", "at_bar": 41, "bars": 4,
 "chop": {
   "slices": {
     "a": {"bar": 20, "beat": 1, "beats": 0.5},
     "b": {"bar": 20, "beat": 2.5, "beats": 0.25, "semitones": 5},
     "c": {"bar": 21, "beat": 1, "beats": 1, "reverse": true}
   },
   "pattern": ["a---a-b-a.--b-a-", "c-------a-a-b-b-"],
   "step": 0.25
 },
 "automation": {"highpass_hz": [[0, 200]]},
 "fx": {"echo": {"beats": 0.75, "feedback": 0.35, "mix": 0.25}}}
```

| field | meaning |
|---|---|
| `slices` | single-character names -> `bar`, `beat` (1-based, fractional ok: 2.5 = the "and" of 2), `beats` (length), optional `semitones` (on top of the source shift) and `reverse`; or `{"word": "janice", "occurrence": 1}` to cut an exact word from the lyrics (`glass-harbor track lyrics <id>` first) |
| `pattern` | one string per bar (cycled to fill `bars`): a slice name triggers it, `-` holds, `.` is a rest; spaces and `|` are ignored |
| `step` | beats per pattern character (default `0.25` = 16th notes; `0.5` = 8ths) |

Each hit is warped to the output tempo, pitched, optionally reversed, faded at the edges (no clicks), and choked by
the next hit or rest. Use per-slice `semitones` to play a melody with one syllable. Find slice positions with
`glass-harbor track show <id>` (vocal phrases) and a short `mix render --start-bar/--end-bar` preview.

## Generated FX and drops

A clip with `generate` renders synthesized FX instead of a stem (no samples needed):

```json
{"id": "riser-92", "generate": "riser", "at_bar": 84, "bars": 7.75, "gain_db": -9},
{"id": "impact-92", "generate": "impact", "at_bar": 92, "bars": 2, "gain_db": -5}
```

Types: `riser` (band-passed noise sweeping 250 Hz to 9 kHz with a rising tone, ends dead on the downbeat),
`downlifter` (the reverse, after a drop), `impact` (sub boom + noise burst). From the song's own audio (need
`source`): `snare_roll` (the beat's cleanest snare from its drum stem, 8ths to 16ths to 32nds, rising), `crash` (a
crash found in the drum stem, else synthesized), `vocal_riser` and `reverse_swell` (need `word` + `occurrence` from
the lyrics: a word stretched and pitched up an octave over the build, or its reverse reverb swelling into the word).
They take `automation`, `fx`, `duck`, and `gain_db` like any clip; macros duck every fill under the vocals.

`glass-harbor mix drop <slug> --at-bar 92 [--build-bars 8] [--silence-beats 1]` writes a whole drop into the plan:
a high-pass sweep (20 Hz to 700 Hz) on every bed clip across the build, a beat of silence before the one, a
riser that ends on the downbeat, and an impact on the drop. `track show` lists detected drops (bars where kick and
bass come back hard).

## DJ edges, fills, and edits

- `glass-harbor mix edges <slug> [--intro-bars 16 --outro-bars 16]`: a beat-only intro (drums, bass in halfway)
  and outro looped from the beat's first drop, so DJs can mix the edit; everything else moves later. New mashups
  get 16 bars by default (`taste set dj_edge_bars=0` turns it off).
- `glass-harbor mix fills <slug>`: a crash on every hook entry and drop, a one-bar reverse swell of each hook's first
  word into it. New mashups get these by default.
- `glass-harbor mix drop <slug> --at-bar N --roll --riser vocal:janice`: the drop builder can add a snare roll from
  the drum stem and use a vocal riser.
- `glass-harbor mix edit <slug> mute|stutter|tape_stop|lift --at-bar N`: the beat drops out under a punchline, a
  word stutters on 16ths (vocal muted under it), the mix brakes to a stop, or everything from bar N goes up
  `--semitones`.

## Vocal chain

Every vocal clip runs through a chain at a fixed internal level (so thresholds mean the same thing on every
acapella), then returns to its original level: high-pass 90 Hz, -3 dB at 300 Hz (mud), +2.5 dB at 4 kHz (presence),
+2 dB shelf at 10 kHz (air), a dynamic de-esser on 5.5-9 kHz, a fast 4:1 compressor and a slow 2:1 leveler, light
tanh saturation, a pre-delayed plate reverb send (high- and low-cut), and dotted-eighth delay throws on the last
word of each lyric line. QA flags any word still cut at a clip edge.

## Ducking

`"duck": {"under": "vocals", "db": 5}` on a bed clip makes room for the vocal. The default `mode: "spectral"`
works like Trackspacer: in each STFT bin of the bed's mid (centre) channel it cuts up to `db` where the vocal is as
loud as the bed (scaling to nothing 12 dB below), between 150 Hz and 8 kHz, so the low end and the stereo sides are
untouched; `level_db` (default 1) adds a small broadband dip. `mode: "band"` is the older fixed 1-4 kHz dip.
`"under"` can also be a list of clip ids.

## Stem arrangement and pumping

`glass-harbor mix arrange <slug>` (needs `track separate <bed> --stems drums,bass,other`) replaces the bed clip with
`<bed>-drums`, `<bed>-bass`, and `<bed>-other` clips and writes their `arrange_db` lanes (a second gain lane,
independent of fades): verses play over drums + bass (melodic layer at `--verse-other-db`, default -60), choruses
and any vocal entering on a drop get the full beat, and the bar before each chorus is drums only. The melodic layer
gets spectral ducking (5 dB) and pumping; the drums get a lighter spectral duck (4 dB). New mashup scaffolds do this
automatically when the bed has those stems.

`"pump": {"db": 3, "release": 0.5}` on any clip dips it on every output beat and recovers over `release` beats
(grid-locked, a short attack so it never clicks). `"groove": {"pump_fx": {"db": 5, "release": 0.6}}` at the plan
level pumps only the vocal chains' reverb and delay returns, keeping the dry vocal steady.

## Renders

`glass-harbor mix render <slug>` writes `runs/<slug>/<stamp>/`:

- `mix.wav` (24-bit) and `mix.mp3`
- `render.json`: resolved clips, stretch/pitch, measured beat-grid offsets, mastering stats
- `qa.json` / `qa.md`: deterministic QA verdict (`pass`, `review`, `fail`) and flags
- `clips/*.wav` with `--clips`: every clip as a full-length aligned WAV for finishing in a DAW (drop them all at
  bar 1 of a session at the plan tempo)

`--start-bar` / `--end-bar` render just a window (fast previews of a transition or a drop).
