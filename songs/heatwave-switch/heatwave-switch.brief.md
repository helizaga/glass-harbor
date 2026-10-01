# Heatwave Switch

## Genre

Global club / moombahton-pop

## Style Lane

Moombahton Club

## Accent

DJ Snake-adjacent, vocal-puncture, chest-forward club bounce

## Mood

Hot-night tension, swagger, stripped confidence, blunt payoff

## BPM

102

## Key / Scale

F minor

## Structure

- intro: 8
- groove: 16
- lift: 8
- breakdown: 8
- return: 16
- outro: 8

## Hook Identity

- primary hook carrier: `vocal_chop`
- supporting answer: `bass_pitched`

## Low-End Plan

- what owns the sub / bass pocket: `bass_pitched` answers the kick with short phrases, not a constant sustained sub
- how should kick and bass trade space: leave holes after the kick and let the bass answer on displaced entries
- should the bass prefer `bass_pitched` or `bass_tonal`: `bass_pitched`

## What To Withhold Until Return

- save this element for the return: the loudest vocal-hook lane plus the widest `impact_wide` hit

## Breakdown Subtraction Plan

- remove: full kick pattern, clap body, busiest perc motion
- keep: filtered vocal fragments, one sparse bass answer, low-level tension
- first thing to re-enter: kick plus one hook vocal answer

## Example Targets

- none

## Prompt References

- Song or artist: DJ Snake
  Borrow: chest-forward percussion, sparse but hard bass answers, treated vocal punctuation, cross-cultural club energy, staged return payoff
  Avoid copying: exact topline, exact drum pattern, exact signature sound design

## Source Material Sources

- Firstpost interview, March 30 2021: DJ Snake says he has been making music with more organic sounds and feelings
- Puremix production breakdown of "Lean On", October 29 2015: broken kick patterns, lean punchy kick over sub support, slight swing, drums and vocal treatments create section contrast
- DJMag Top 100 DJs 2016 profile: mix of pop-leaning vocals, shiny bass, and crisp trap-inspired production

## Sourced Truths

- sourced trait: DJ Snake explicitly talks about wanting more organic sounds and feelings in his music
- sourced trait: one successful Snake-associated hit structure uses the same harmonic loop while drums and vocal treatments create the movement
- sourced trait: lean kick plus separate sub support leaves room for non-four-on-the-floor bass drum patterns
- sourced trait: slight swing and small drum-detail changes matter a lot to the pocket
- sourced trait: pop-facing vocals and crisp hard-edged drums are a recurring part of the lane

## Musical Inferences

- translation into composition choice: keep harmony minimal and let drums, bass, and vocal chops carry the identity
- translation into composition choice: avoid deep-house air beds and big melodic pads
- translation into composition choice: use `struct()`, `chooseCycles()`, `slice()`, and slight displacement for vocal and perc movement
- translation into composition choice: keep the return hard and simple instead of emotional or lush

## Capability Gaps

- honest current limitation: the runtime vocal chops can suggest attitude, but they do not have the same bespoke topline identity as a real DJ Snake record
- honest current limitation: the pack can support the drum grammar and sparse arrangement better than signature artist-level sound design
- honest current limitation: this should capture pacing and pocket, not pretend to be an authentic DJ Snake production clone

## Sonic Goals

- primary sonic goal: make the groove feel heavy and blunt without turning into festival EDM or airy house
- if using vocals, give `vocal_chop` more than one job such as airy bed, hook punctuation, breakdown fragment, or return accent
- call out whether the hook should come from `vocal_chop`, `pluck_pitched`, `stab_pitched`, or another specific carrier
- call out whether the song should prefer voicing-led harmony, chopped sample identity, displaced groove, or orbit-separated space
- call out whether groove variation should come from `euclid()`, `struct()`, `stepcat()`, or another specific Strudel transform

## Review Goals

- keep the lane focused on `vocal_chop` and `bass_pitched`
- prune `air_texture`, `shimmer_fx`, and extra harmonic layers before they soften the accent
- preserve low-end holes so the kick still reads as the anchor

## Stable Sound Roles

- `kick_main`
- `clap_main`
- `hat_closed`
- `hat_open`
- `perc_top`
- `impact_wide`
- `riser_up`
- `shimmer_fx`
- `air_texture`
- `vocal_chop`

## Optional Tonal Sample Roles

- `bass_tonal`
- `stab_tonal`
- `pluck_tonal`
- `bass_pitched`
- `stab_pitched`
- `pluck_pitched`

## Notes For Agent

- keep the output as one pasteable `.strudel.js` file
- named-song references are prompt-only by default unless I explicitly ask to ingest them into taste memory
- do not reference vendor filenames
- prefer readable named layers and clear section arrangement
- avoid loud default browser synths unless I explicitly ask for them; prefer tonal samples and vocal chops for the song's identity
- if pitch-aware sample roles are available, prefer them for note-driven hooks and harmony
- dominant roles first: `vocal_chop`, `perc_top`
- support roles second: `bass_pitched`, `impact_wide`
- prune first if the lane drifts: `air_texture`, `shimmer_fx`, `hat_open`
