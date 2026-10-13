# 1 Umbrella x Starboy

## Goal

- kind: mashup (one-command draft: `glass-harbor auto`)
- vibe: club edit on the beat's own structure; the user judges it by ear

## Sources (from analysis)

- `1-umbrella`: 1 Umbrella; Lil Bean; Lil Yee; ZayBang; AllBlack; 22nd Jim - 1 Umbrella — 95.0 bpm (fixed grid), G minor (6A, confidence 0.94), drops at [5, 19, 27, 35, 43, 51, 63]; stems: vocals, instrumental, bass
- `01-the-weeknd-starboy`: The Weeknd; Daft Punk - Starboy — 93.0 bpm (fixed grid), A minor (8A, confidence 0.81), drops at [57, 71]; stems: vocals, instrumental, drums, bass, other

## Fit check

- verdict: risky (rap vocal); vocal_room 0.0041 (good), harshness 0.0018 (good), out_of_key 0.442 (risky)
- a lot of the beat's harmony sits outside the vocal's key (dark/chromatic)
- hit potential: low (40/100)
  - vocal is niche (Deezer rank 31,773); beat is a hit (Deezer rank 975,897)
  - beat released 119 months ago
  - hook: 1-word line repeated 1x, first at 170s

## Decisions (the draft's rules; edit the plan to change them)

- fit: same key, A minor (8A) over A minor (8A), -2.1% stretch on vocals, score 0.945
- song order: verse 1 (vocal bar 2) lands on the beat's first full section (bar 23)
- stem arrangement on bed: verses over drums + bass (melodic layer -60 dB), full beat under hooks, 0 drums-only bar before each hook
- drop at bar 57: 2-bar hip-hop build (filter down) on bed-drums, bed-bass, bed-other, impact, 4 beat(s) of silence
- drop at bar 71: 2-bar hip-hop build (filter down) on bed-drums, bed-bass, bed-other, impact, 4 beat(s) of silence
- fills: crash 22, crash 57, crash 71, swell into 22
- run-up trimmed: the edit starts on bar 17 of the draft, 5 bars before the first vocal (taste run_up_bars=4); subtract 16 from bar numbers in the notes above
- no extra DJ intro: the vocal comes in within 4 bars (taste run_up_bars)
- the beat's own 2-bar fade-out is cut; the DJ outro follows on
- DJ edges: 0-bar beat intro, 16-bar beat outro (4-bar loop from bar 57 of 01-the-weeknd-starboy)

## Fix rounds

- round 1: nothing left to fix

## QA after the last render

- verdict: pass, -7.8 LUFS, -1.1 dBTP
- info: bar 41: jumps +8.2 dB (intended drop?)

## Needs ears

- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?
