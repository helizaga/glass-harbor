# Technique Index

Use this as a fast lookup by songwriting problem.

## Make A Hook More Alive

- `slice()`, `splice()`, `chop()`
  - turn one sample phrase into identity instead of adding another lane
- `off()`
  - add a delayed answer or ghost phrase
- `layer()`
  - double a motif with octave, answer, or contrast
- `lastOf()`, `firstOf()`
  - make one phrase change shape at phrase boundaries

Best for:

- vocal hooks
- pluck hooks
- stab punctuation

## Improve Groove Without More Density

- `swingBy()`
  - add shuffle feel to hats or light percussion
- `late()`
  - pull accents behind the grid
- `early()`
  - push a hook or perc phrase forward
- `euclid()`, `euclidRot()`
  - distribute accents with more shape than a flat grid
- `struct()`
  - define a clear rhythmic gate for an existing phrase
- `degradeBy()`, `sometimesBy()`, `chooseCycles()`
  - keep repeated phrases from sounding machine-static

Best for:

- hats
- perc
- vocal punctuation
- broken-grid bass answers

## Make Harmony Smoother

- `chord(...).voicing()`
  - smoother voice-leading than hand-stacking raw notes
- `rootNotes()`
  - support parts that follow the harmony cleanly
- `scaleTranspose()`
  - move a support phrase without rewriting every note
- `note(...).s("..._pitched")`
  - keep tonal sample parts musical instead of slot-stepped

Best for:

- chord beds
- harmonic stabs
- basslines that matter melodically

## Shape Samples So They Sound Intentional

- `clip()`
  - tighten the body of a sample
- `end()`
  - shorten tails that smear the groove
- `begin()`
  - skip weak attacks or trim dead air
- `seg()`, `lpenv()`
  - make filter motion feel continuous rather than stepped per event

Best for:

- bass
- plucks
- vocal chops
- hats and perc

## Create Width Without Clutter

- `orbit()`
  - separate drums, hook lanes, and atmosphere into different spaces
- `delay()`, `room()`
  - apply width selectively after orbit separation
- `duckorbit()`
  - only when the runtime stays stable and the sidechain effect is worth the complexity

Best for:

- hook vs bed separation
- keeping atmosphere from washing over drums

## Prefer These Defaults

- one hook carrier first
- one bass identity
- one harmonic bed
- 1-2 vocal roles, not one monolithic vocal lane
- transform phrases before adding layers

## Avoid These Failure Modes

- every song using the same accent just because the pack supports it
- adding a new lane to solve every weak section
- flat tonal arrays when pitched families exist
- long untrimmed sample tails
- pushing more FX instead of fixing hook, groove, or pocket
