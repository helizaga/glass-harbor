# yeah bop x Get Up (auto)

## Goal

- kind: mashup (one-command draft: `glass-harbor auto`)
- vibe: club edit on the beat's own structure; the user judges it by ear

## Sources (from analysis)

- `yeah-bop`: Lil Bean - yeah bop — 90.0 bpm (fixed grid), C major (8B, confidence 0.38), drops at [6, 14, 22, 34, 42]; stems: vocals, instrumental, bass
- `get-up`: get-up-ijetfh — 175.0 bpm (fixed grid), A minor (8A, confidence 0.82), drops at [17, 113]; stems: vocals, instrumental, drums, bass, other

## Fit check

- verdict: good (rap vocal); vocal_room 0.0214 (good), harshness 0.0094 (good), out_of_key 0.345 (good)
- hit potential: medium (56/100)
  - vocal is niche (Deezer rank 61,929); beat is unknown popularity
  - hook: 2-word line repeated 5x, first at 9s
  - crossover: a hip-hop/R&B vocal on a club beat

## Decisions (the draft's rules; edit the plan to change them)

- fit: relative major/minor, C major (8B) over A minor (8A), -2.8% stretch on vocals, score 0.946
- song order: verse 1 (vocal bar 6) lands on the beat's first full section (bar 33)
- vocal pauses for the breakdown at bar 97 and comes back on the bar-113 drop
- the chant is chopped into a build over bars 105-112
- stem arrangement on bed: verses over drums + bass (melodic layer -6 dB), full beat under hooks, 0 drums-only bar before each hook, melodic layer pumps on the beat
- drop at bar 17: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 113: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- reprise: the back of the track had vocals on 15% of its bars; the last 8 bars of verse2 come back at bar 129
- the beat's own vocal answers the acapella at bar(s) 16, 148, 152, 156, 160, 176 (call and response)
- half-time switch: bars 61-82 ride a half-time beat from the record's own kit (drums muted), bass and melody out on bar 82, snare roll and impact back into the full beat at 83
- fills: crash 17, crash 57, crash 83, crash 113, crash 148, crash 176, swell into 57
- no extra DJ intro: the beat opens with 16 bars of its own
- DJ edges: 0-bar beat intro, 16-bar beat outro (looped from bar 17 of get-up)

## Fix rounds

- round 1: vocal buried in the 1-4 kHz band: +2 dB on hook3, hook7; bed-other ducks 7 dB under the vocal (superseded by round 2's 9 dB)
- round 2: vocal buried in the 1-4 kHz band: +2 dB on hook3, hook7; bed-other ducks 9 dB under the vocal

## QA after the last render

- verdict: review, -6.1 LUFS, -1.0 dBTP
- warning: bar 193: near silence (-25.8 dB vs median -7.6 dB)
- warning: bar 194: near silence (-33.0 dB vs median -7.6 dB)
- warning: bar 195: near silence (-38.3 dB vs median -7.6 dB)
- info: bar 196: jumps +29.8 dB (intended drop?)
- warning: hook1: warped clip lands -16 ms off the output grid
- warning: bar 83: the drop has only 1.6 dB of contrast with the 8 bars before it; strip or filter more in the build
- warning: verse8: 1 word(s) still cut at the clip edges
- warning: verse10: 1 word(s) still cut at the clip edges
- warning: bars 16-18, 25, 57, 71, 81-82, 106, 108, 148-150, 152-153, 158, 161, 178: vocal is buried under the beat in the 1-4 kHz band; raise the vocal, add duck to the bed, or cut the bed's mids

## Needs ears

- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?
