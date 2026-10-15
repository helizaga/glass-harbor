# GLOCK x SWARM

## Goal

- kind: mashup (one-command draft: `glass-harbor auto`)
- vibe: club edit on the beat's own structure; the user judges it by ear

## Sources (from analysis)

- `01-don-toliver-glock`: Don Toliver - GLOCK — 76.0 bpm (fixed grid), E major (12B, confidence 0.71), drops at [13, 21, 45]; stems: vocals, instrumental, bass
- `swarm`: elden - SWARM — 150.0 bpm (fixed grid), E minor (9A, confidence 0.69), drops at [17, 53, 77]; stems: vocals, instrumental, drums, bass, other

## Fit check

- verdict: poor (sung vocal); vocal_room 0.1345 (poor), harshness 0.0393 (risky), out_of_key 0.39 (risky)
- the beat is crowded in the 1-4 kHz vocal range (busy synths/hats will mask the vocal)
- the beat's vocal range is noisy or distorted (aggressive, gritty sound design)
- a lot of the beat's harmony sits outside the vocal's key (dark/chromatic)
- hit potential: high (72/100)
  - vocal is popular (Deezer rank 436,000); beat is niche (Deezer rank 71,023)
  - beat released 1 month ago (fresh)
  - hook: 8-word line repeated 7x, first at 28s
  - crossover: a hip-hop/R&B vocal on a club beat

## Decisions (the draft's rules; edit the plan to change them)

- fit: parallel major/minor (same home note), E major (12B) over E minor (9A), -1.3% stretch on vocals, score 0.911
- song order: GLOCK's first hook line (vocal bar 9) lands on the beat's first full section (bar 17, bar 33 in this plan)
- the beat ends before the song: GLOCK plays to its bar 44.75 of 72
- stem arrangement on bed: verses over drums + bass (melodic layer -60 dB), full beat under hooks, 0 drums-only bar before each hook, melodic layer pumps on the beat
- drop at bar 17: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 53: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- drop at bar 77: 8-bar build on bed-drums, bed-bass, bed-other, riser, snare roll, impact, 1 beat(s) of silence
- the beat's own vocal answers the acapella at bar(s) 1, 4, 9, 11 (call and response)
- fills: crash 1, crash 17, crash 53, crash 77, swell into 53
- bar numbers in the notes above (and in fill ids like riser-92) are from before the DJ intro: add 16 to find them in this plan
- DJ edges: 16-bar beat intro, 16-bar beat outro (looped from bar 17 of swarm)
- bass follows the vocal's original chords under hook4 (their sung notes sat a half-step off the beat's bassline)

## Fix rounds

- round 1: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 7 dB under the vocal (superseded by round 2's 9 dB); drop at bar 93: bed-bass out for bar 92
- round 2: vocal buried or hard to make out: +2 dB on verse1, verse2, verse4, verse6; bed-other ducks 9 dB under the vocal

## Edits after the draft

- Removed the Whitney Houston "Exhale" sample that opened `verse1` (GLOCK bars 1-9.2, "Everyone falls ... when we
  exhale, say shoop"; the published lyrics put it at 0:00-0:27, and the vocal stem is silent from 26.3 s to 27.8 s).
  Before, it played across the bar-33 drop and Don came in at bar 48.
- Re-laid the vocal with the draft's own anchoring rule: GLOCK bar 9 (Don's first line, "Hold my Glock when I'm in the
  club") lands on the bar-33 drop, and GLOCK plays in order to its bar 44.75 as `hook1`, `hook2`, `verse3`, `hook4`,
  `verse5` (the hooks are the published chorus lines). Cuts sit on beats where the vocal stem is quiet, with
  `word_safe` off: Whisper missed this chorus, so its word times there are wrong, and the word-safe edges overlapped
  the next clip by half a second.
- Every piece keeps the +4 dB rap treatment the earlier draft gave these lines. With the hook chain at 0 dB, Whisper
  made out 13% of `hook2`.
- `mix follow` puts the bass under `hook4` on the vocal's original chords (QA: 12% of its sung notes sat a half-step
  or tritone off the beat's bass). The old follow under `verse2` went with that clip.
- Whisper's readings swing run to run: `hook1` read 61% and then 38% on two renders whose audio there differs by
  -40 dB.

## QA after the last render

- verdict: review, -6.2 LUFS, -1.1 dBTP
- warning: hook4: warped clip lands -17 ms off the output grid
- warning: bed-shout-1: 1 word(s) still cut at the clip edges
- warning: bars 49: held vocal notes rub against the beat's chord (a semitone off); check harmonize notes in render.json or shift the vocal
- warning: bars 92-93: vocal is buried under the beat in the 1-4 kHz band; raise the vocal, add duck to the bed, or cut the bed's mids
- warning: sources bed + vox (bed-bass, bed-other, hook1, hook2, hook4, verse3, verse5): plan: keys 9A vs 12B are 4 steps apart on the Camelot wheel; shift semitones or keep the overlap short/percussive

## Needs ears

- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?
