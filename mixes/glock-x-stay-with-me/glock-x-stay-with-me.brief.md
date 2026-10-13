# GLOCK x Stay With Me

## Goal

- kind: mashup (one-command draft: `glass-harbor auto`)
- vibe: club edit on the beat's own structure; the user judges it by ear

## Sources (from analysis)

- `01-don-toliver-glock`: Don Toliver - GLOCK — 76.0 bpm (fixed grid), E major (12B, confidence 0.71), drops at [13, 21, 45]; stems: vocals, instrumental, bass
- `dabin-stay-with-me-feat-velvetears`: DABIN - Stay With Me (feat. VELVETEARS) — 150.0 bpm (fixed grid), E major (12B, confidence 0.85), drops at [17, 66, 82]; stems: vocals, instrumental, drums, bass, other

## Fit check

- verdict: risky (sung vocal); vocal_room 0.038 (risky), harshness 0.0059 (good), out_of_key 0.295 (good)
- the beat is crowded in the 1-4 kHz vocal range (busy synths/hats will mask the vocal)
- hit potential: medium (68/100)
  - vocal is popular (Deezer rank 436,000); beat is known (Deezer rank 114,549)
  - beat released 18 months ago
  - hook: a 8-word line repeated 7x, first at 28s
  - crossover: a hip-hop/R&B vocal on a club beat

## Decisions (the draft's rules; edit the plan to change them)

- fit: same key, E major (12B) over E major (12B), -1.3% stretch on vocals, score 0.996
- the second chant takes the bar-82 drop
- structure-aware draft: 3 chorus(es) on the beat's drops/full sections, 2 verse chunk(s), chops in low-energy stretches
- stem arrangement on bed: verses over drums + bass (melodic layer -60 dB), full beat under hooks, 1 drums-only bar before each hook, melodic layer pumps on the beat
- drop at bar 17: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 66: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 82: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- fills: crash 17, crash 33.5, crash 66, crash 82, swell into 33.5, swell into 82
- no extra DJ intro: the beat opens with 16 bars of its own
- the beat's own 2-bar fade-out is cut; the DJ outro follows on
- DJ edges: 0-bar beat intro, 16-bar beat outro (looped from bar 17 of dabin-stay-with-me-feat-velvetears)
- auto fix: vocal buried or hard to make out: +2 dB on hook2; bed-other ducks 7 dB under the vocal
- auto fix: vocal buried or hard to make out: +2 dB on verse1, hook2; bed-other ducks 9 dB under the vocal

## Fix rounds

- round 1: vocal buried or hard to make out: +2 dB on hook2; bed-other ducks 7 dB under the vocal
- round 2: vocal buried or hard to make out: +2 dB on verse1, hook2; bed-other ducks 9 dB under the vocal

## QA after the last render

- verdict: review, -7.5 LUFS, -1.0 dBTP
- warning: intro1: warped clip lands +29 ms off the output grid
- warning: verse1: warped clip lands +16 ms off the output grid
- warning: verse2: warped clip lands -25 ms off the output grid
- warning: chant1: warped clip lands +32 ms off the output grid
- warning: bars 29: held vocal notes rub against the beat's chord (a semitone off); check harmonize notes in render.json or shift the vocal
- warning: verse1: Whisper made out only 33% of its 40 words in the finished mix (the track's average is 51%): the beat masks it
- warning: hook2: Whisper made out only 33% of its 70 words in the finished mix (the track's average is 51%): the beat masks it
- warning: bars 16, 95, 105: vocal is buried under the beat in the 1-4 kHz band; raise the vocal, add duck to the bed, or cut the bed's mids

## Needs ears

- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?
