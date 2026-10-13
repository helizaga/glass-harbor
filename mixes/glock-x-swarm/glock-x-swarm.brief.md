# GLOCK x SWARM

## Goal

- kind: mashup (one-command draft: `glass-harbor auto`)
- vibe: club edit on the beat's own structure; the user judges it by ear

## Sources (from analysis)

- `01-don-toliver-glock`: 01 - Don Toliver - GLOCK — 76.0 bpm (fixed grid), E major (12B, confidence 0.71), drops at [13, 21, 45]; stems: vocals, instrumental, bass
- `swarm`: SWARM — 150.0 bpm (fixed grid), E minor (9A, confidence 0.69), drops at [17, 53, 77]; stems: vocals, instrumental, drums, bass, other

## Decisions (the draft's rules; edit the plan to change them)

- fit: parallel major/minor (same home note), E major (12B) over E minor (9A), -1.3% stretch on vocals, score 0.911
- song order: verse 1 (vocal bar 2) lands on the beat's first full section (bar 17)
- the beat ends before the song: the draft keeps 6 of 12 vocal pieces (extend the beat or pick a longer one to use the rest)
- stem arrangement on bed: verses over drums + bass (melodic layer -60 dB), full beat under hooks, 0 drums-only bar before each hook, melodic layer pumps on the beat
- drop at bar 17: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 53: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 77: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- the beat's own vocal answers the acapella at bar(s) 1, 4, 9, 11 (call and response)
- fills: crash 1, crash 17, crash 53, crash 77, swell into 53
- bar numbers in the notes above (and in fill ids like riser-92) are from before the DJ intro: add 16 to find them in this plan
- DJ edges: 16-bar beat intro, 16-bar beat outro (looped from bar 17 of swarm)
- bass follows the vocal's original chords under verse2 (their sung notes sat a half-step off the beat's bassline)
- auto fix: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 7 dB under the vocal; drop at bar 93: bed-bass out for bar 92
- auto fix: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 9 dB under the vocal

## Fix rounds

- round 1: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 7 dB under the vocal; drop at bar 93: bed-bass out for bar 92
- round 2: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 9 dB under the vocal

## QA after the last render

- verdict: review, -6.2 LUFS, -1.0 dBTP
- warning: verse1: warped clip lands +18 ms off the output grid
- warning: bar 93: the drop has only 3.4 dB of contrast with the 8 bars before it; strip or filter more in the build
- warning: bed-shout-1: 1 word(s) still cut at the clip edges
- warning: bars 32, 41, 51: held vocal notes rub against the beat's chord (a semitone off); check harmonize notes in render.json or shift the vocal
- warning: verse1: Whisper made out only 46% of its 28 words in the finished mix (the track's average is 50%): the beat masks it
- warning: verse2: Whisper made out only 43% of its 14 words in the finished mix (the track's average is 50%): the beat masks it
- warning: verse4: Whisper made out only 46% of its 26 words in the finished mix (the track's average is 50%): the beat masks it
- warning: bars 17-18, 22, 26, 28, 31-34, 39, 41, 43, 45-46, 68, 103: vocal is buried under the beat in the 1-4 kHz band; raise the vocal, add duck to the bed, or cut the bed's mids
- warning: sources bed + vox (bed-bass, bed-other, hook3, hook5, verse1, verse2, verse4, verse6): plan: keys 9A vs 12B are 4 steps apart on the Camelot wheel; shift semitones or keep the overlap short/percussive

## Needs ears

- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?
