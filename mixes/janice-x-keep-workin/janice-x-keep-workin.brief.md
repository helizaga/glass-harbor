# Janice STFU x Keep Workin'

## Goal

- kind: mashup (rap acapella over an Afro/melodic house groove)
- vibe: club-ready edit; Drake's hooks ride the bed's full sections, chops fill the breakdowns, title line a
  cappella in the break before the last drop

## Sources

- `vox`: Drake, "Janice STFU" (Iceman, 2026), acapella separated locally (Resurrection BS-RoFormer), gentle
  de-reverb
- `bed`: Adam Ten & Yamagucci, "Keep Workin'", instrumental separated locally

## From analysis (library, not committed)

- Tempo: Janice STFU 126.0 bpm (beat_this flips to 63 bpm in the verses; grid normalized), Keep Workin' 127.0 bpm.
  Vocal stretch +0.8%.
- Key: both G# minor / 1A by S-KEY (0.81 and 0.90). Same key; no pitch shift.
- Janice STFU lyric structure: chorus at bars 10-25 and 42-57 (repeats 32 bars apart), title line at bars 40-41,
  "for real" section from bar 88.
- Keep Workin': drops (kick + bass return) at bars 5, 25, 92; breakdowns 17-24 and 65-80; near-silent break 89-91.

## Inferences (mine, needs ears)

- Chorus first over the bed's first full section lands harder than the intro verse alone.
- The 3-bar break before bar 92 is the best spotlight for the title line.
- 3 dB of mid ducking on the bed is enough for a rap vocal at this density.

## Decisions

- Hooks at output bars 25, 49, 92; verse at 41-48 ending on the title line; chops at 17-24 and 65-80.
- Drops built at 81 and 92 (`mix drop`): high-pass build, one beat of silence, riser, impact.
