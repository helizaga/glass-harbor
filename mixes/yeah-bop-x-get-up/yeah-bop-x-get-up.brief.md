# yeah bop x Get Up

## Goal

- kind: mashup (Bay Area rap acapella over a drum & bass drop)
- vibe: club DnB edit; Lil Bean rides the drops the way DnB MCs do, the "yeah bop" chant tees up both drops,
  beat-only intro and outro for DJs

## Sources

- `vox`: Lil Bean, "yeah bop" (YEAH BOP!, 2026, prod. P-Lo), acapella separated locally (vocal_balanced ensemble),
  gentle de-reverb
- `bed`: Amplify & Bou, "Get Up" (2026), instrumental and drums/bass/other stems separated locally (Bou's MC
  vocal removed)

## Why this pairing (sources)

- Beatport lists "yeah bop" at 90 BPM, A minor, and "Get Up" at 88 BPM (half of 176), A minor; "Get Up" was #9 on
  Beatport's Drum & Bass Top 100 on 2026-10-10.
- Apple Music ranks "yeah bop 2" and "yeah bop" among Lil Bean's top songs; he is not on kworb's US Spotify or Apple
  charts, so this is a regional record, not a national hit.
- Lil Bean has no DJ edits on Beatport and nothing found on 1001Tracklists: the pairing is not overdone, and also
  not proven.

## From analysis (library, not committed)

- Tempo: yeah bop 90.0 bpm (fixed grid). Get Up 175.0 bpm: beat_this drifted through the beatless intro and the
  breakdown; the grid now trusts the 89% of beats that sit on one constant grid. Vocal at half time: -2.8% stretch.
- Key: Get Up A minor (S-KEY 0.82); yeah bop reads C major (0.38, low), the relative major of A minor. No shift.
- yeah bop is almost all rap: no clip has enough sung notes for the bass to need to follow the vocal.
- yeah bop lyric structure (vocal bars at 90 bpm): intro line 1-2, "yeah bop" chants 3.7-5.5, verse 6-18,
  chants 18.8 / 24.8 / 30.8 between short verses (20-24, 26-30), fast flow 31.9-41.8, outro chants 42.8-45.7.
- Get Up: beatless intro 1-16, drop 17 (full by 33), breakdown 97-112, kick and bass return 113, second drop 129.

## Inferences (mine, needs ears)

- Rap at 90 sits in DnB's half-time pocket; one vocal bar spans two DnB bars.
- The verse landing on the full drop at 33 hits harder than starting it on the first kick at 17.
- Get Up's melodic layer at -6 dB under verses (not stripped): DnB drops lose their identity without it.

## Decisions

- Bed: Get Up 1-96, bars 81-88 repeated at 97-104 so the fast flow ends on the drop, 89-160, then 177-195 (161-176
  cut). Total 195 bars, 4:27.
- Vocal: intro and chants 23-32, song order from bar 33 through the outro chants (105-112), breakdown 113-120,
  yeah/bop chop build 121-128, chant reprise at 145, tag at 177.
- Drops built at 17 and 129 (riser, impact, one beat of silence). Crashes only on the drops; reverse swells into
  the chants.
- Chants +4 dB, melodic layer ducks 8 dB and drums 6 dB under the vocal (Get Up is mastered at -4.7 LUFS and
  dense in 1-4 kHz).

## v2 (production pass)

- Every vocal: gate between words (separation bleed from P-Lo's beat, 14 dB), groove lock (onsets 40% onto the
  flow's 16th grid, ~9 ms average move), density (parallel compression + presence exciter).
- Half-time switch on bars 61-80: verse 2, chant 2, and verse 3 over a half-time beat played on Get Up's own kick,
  snare, and hats (3 dB under its drums), snare roll and impact back into the full beat at 81, bass and melody out
  on bar 80.
- Get Up's own vocal answers Lil Bean: its shout before drop 1 (bar 16), its breakdown chant (113), its shout
  traded with the yeah/bop chops in the build (121-124), its hook every 4 bars after the reprise (160-176).
- Drums clipped 3 dB; master -6.2 LUFS (Get Up is -4.7; v1 was -7.3).
- QA still reads bar 81 at 2.3 dB of contrast (the full drums returning mid-drop, not a breakdown drop) and flags
  the vocal at entry and FX bars (57, 80-81, 105, 129, 166, 178). Needs ears.

## v3 and the set test

- Verse 1's last 8 bars (vocal bars 10-18) return on drop 2 at 129 and run into the chant reprise at 145, as in
  the original song: vocals now on 41 of the last 67 bars (was 26).
- DJ import test: the rendered edit analyzes as a fixed 175.0 bpm grid with bar 1 at 0.0 s and drops at 17, 81,
  129 (after two analyzer fixes: a tempo search for the steady-majority fit, and keeping a first beat that fits a
  few ms before 0 s).
- Set test (`mixes/ybgu-set`): Get Up -> edit -> Get Up, intros over outros with bass swaps on each incoming drop;
  QA finds no beat-alignment problems through either transition.
- The edit's drops sit 1.9 dB under Get Up's (-5.9 vs -4.0 LUFS): a DJ trims that, or the master can push harder
  at the cost of more limiting on the vocal.
