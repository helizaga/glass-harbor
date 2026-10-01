# Ember Motif

## Genre

Motif-led downtempo club pop

## Style Lane

Motif-Led Club Pop

## Accent

Warm-digital, motif-first, radio-edit drop structure

## Mood

Melancholic but driving, glossy memory, night-drive release

## BPM

98

## Key / Scale

F minor

## Structure

- intro: 4
- groove: 8
- lift: 8
- return: 8
- breakdown: 4
- final-return: 8
- outro: 4

## Hook Identity

- primary hook carrier: `pluck_pitched`
- supporting answer: `vocal_chop`

## Low-End Plan

- what owns the sub / bass pocket: `bass_pitched` with a second lowered layer acting as the sub shadow
- how should kick and bass trade space: kick stays clean on the main anchor hits while bass fills the gaps and final-bar fills
- should the bass prefer `bass_pitched` or `bass_tonal`: `bass_pitched`

## What To Withhold Until Return

- save this element for the return: the brighter motif variant and the wide impact layer

## Breakdown Subtraction Plan

- remove: dense hats, main impact layer, the fullest motif brightness
- keep: motif memory, answer phrase, bass shadow, sparse kick anchors
- first thing to re-enter: main motif plus full kick

## Example Targets

- none

## Prompt References

- Song or artist: user-provided Strudel sketch
  Borrow: repeating melodic motif, answer phrase, layered bass and sub, verse/pre/drop/breakdown/final-drop shape, restrained intro with larger final payoff
  Avoid copying: exact note pattern, exact chord movement, exact drum grid

## Source Material Sources

- user-provided Strudel code snippet in thread

## Sourced Truths

- sourced trait: the lead identity comes from one repeating motif that changes filter, brightness, and section weight rather than being replaced
- sourced trait: there is a secondary answer phrase that supports the motif instead of taking over the track
- sourced trait: bass and sub are layered versions of the same pocket idea
- sourced trait: the arrangement is section-first: intro, restrained groove, lift, drop, breakdown, larger final return
- sourced trait: drums stay readable and danceable while the motif and harmony carry the memory

## Musical Inferences

- translation into composition choice: build the song around one pluck motif plus one vocal answer lane
- translation into composition choice: use `stab_pitched` for harmonic support and short brass-like punches instead of loud browser synths
- translation into composition choice: keep the intro and breakdown filtered, then open the motif and drum density at the returns
- translation into composition choice: use a final-return expansion rather than changing to a totally different hook

## Capability Gaps

- honest current limitation: the current runtime pack does not provide the exact GM-like patch palette in the reference snippet
- honest current limitation: this can capture the motif-led writing and section logic more faithfully than the exact timbre
- honest current limitation: the answer phrase is better represented with `vocal_chop` than with a true choir or ooh patch

## Sonic Goals

- primary sonic goal: make the motif instantly memorable without sounding like a default synth demo
- if using vocals, give `vocal_chop` more than one job such as airy bed, hook punctuation, breakdown fragment, or return accent
- call out whether the hook should come from `vocal_chop`, `pluck_pitched`, `stab_pitched`, or another specific carrier
- call out whether the song should prefer voicing-led harmony, chopped sample identity, displaced groove, or orbit-separated space
- call out whether groove variation should come from `euclid()`, `struct()`, `stepcat()`, or another specific Strudel transform

## Review Goals

- keep the motif as the center of gravity
- keep the final return meaningfully bigger than the first return
- keep the bass/sub relationship strong without blurring the kick

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
- keep the motif-centric composition style from the reference
- let the answer phrase support, not overpower, the motif
