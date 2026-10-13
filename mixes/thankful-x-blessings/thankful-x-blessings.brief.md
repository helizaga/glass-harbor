# Thankful x Blessings

## Goal

- kind: mashup, hand-arranged over the `glass-harbor auto` draft
- idea: Kodak Black's gratitude verse told over Calvin Harris's "Blessings", with Clementine Douglas's own hook
  answering him on the drops. Club edit with 16-bar DJ edges.

## Sources (from analysis)

- `kodak-thankful`: Kodak Black - Thankful (Institution, 2015). 67.5 bpm (135 double), B minor (10A, 0.71 on the
  instrumental stem; the 808 root is B). Spotify lists C major; the measured key replaces it. One rapped verse with
  no repeated line (LRCLIB). The verse is double-tracked in the source, with both takes stacked near the centre
  (L/R correlation 0.90, side 12.7 dB under mid), so no tool here isolates a single take.
- `01-calvin-harris-blessings`: Calvin Harris & Clementine Douglas - Blessings (2025). 130 bpm, B minor (10A, 0.73;
  Wikipedia agrees). Drops at bars 17 and 41. The hook is a short sung line every 8 bars, first at bar 38.5, not
  the title word.

## Acapella choice (measured)

Whisper on the isolated acapella, share of the 430 published words recovered: balanced separation + gentle
de-reverb 72%; best separation raw 74%; best + gentle de-reverb 73%; best + de-echo 74%; best + lead-only split 40%
(the karaoke model takes most of verse 1 as "backing", so it is unusable). Best + de-echo also leaves the least
residue between words (-3.1 dB vs -2.1 to -2.7), so it is the active stem.

## Arrangement (Blessings bars; plan bar = Blessings bar + 8, after the 16-bar DJ intro)

| Blessings bars | time | what plays |
|---|---|---|
| 9-16 | 0:30 | last 8 bars of the soft intro; Kodak's opening couplet (vox 4.75-6.8) as the build, one beat of silence before the drop |
| 17-40 | 0:44 | Kodak verse 1 (vox 6.8-18.9) over drop 1 (melodic layer -6 dB) and the first breakdown (-6 dB) |
| 41-56 | 1:29 | Clementine's drop-2 hook from the record, full beat |
| 57-88 | 1:58 | Kodak verse 2 (vox 19-34.5): drums + bass in the verse, melodic layer back at -6 dB for the second breakdown (vox 27.7-30.6 land there, about 2:30), drums + bass after |
| 89-94 | 2:57 | the record's instrumental peak, left instrumental |
| 95-112 | 3:08 | Clementine to the end, then the beat-only outro |

- the spoken intro and the closing tag (both from vox bars 1.75-4.75) are out at the user's request
- **hook (v8)**: Thankful has no repeated line, the main gap in its hit-potential read. The hook is Kodak's own
  phrase "see my blessings" (vox 96.90-97.76 s, bar 28 beat 2.01 for 0.97 beats), named after the beat, untouched
  apart from a 120 Hz high-pass: twice after the DJ intro (into the couplet; 7 s into the short edit), three times on
  the instrumental peak with Clementine's "no looking back this time" answering, twice in the outro. A pitched
  one-word "thankful" chop (v7) read as no words at all (Whisper heard "Outro Music"); the chop chain's de-esser and an
  echo blurred the phrase too, so neither is used. Whisper reads the raw slice as "see my blessing" and the hook in the
  mix as "...my blessing" (the soft "s" sits under the hats)
- Kodak's verses use the `dry` chain (the rap chain's dotted-eighth echo on every line end landed under the next
  line and read as a ghost double) with a 20 dB gate between words, and a softer tone (v6): density 0.25, a -4 dB
  shelf above 4.5 kHz, a 12 kHz low-pass, room reverb 0.15. The earlier chain had tripled his 2-5 kHz share (5.3%
  on his record, 14.3% in the mix) and sibilance (1.5% to 4.5%); now 10.4% and 1.8%
- pitch correction cannot make the verse more melodic: 0.2% of his rapped frames are steady sung notes
- every Kodak clip edge sits in a measured gap between words; QA reports no cut words
- drops at 17, 41, 89: one high-passed bar, one beat of silence, impact; crashes on the drops
- beat level (user asked for a louder beat): measured as the lead-to-accompaniment ratio (vocal minus beat, K-weighted
  loudness where Kodak raps). Kodak's own record measures -3.9 LU and Blessings -4.6 LU; the clarity pass had pushed
  this mix to +6.2 LU. Gerdes & Siedenburg (2023) find hit records sit near +1 dB on their measure with rap above
  pop, and Knoll & Siedenburg (2022) find listeners prefer vocals a little above the original mix, so the target is
  his own balance plus a small lift: -2.8 LU now
- Kodak -7 dB, Clementine +3 dB; melodic layer back under the verses (-6 dB, -3 dB in the breakdowns, full on the
  drops); spectral duck 4 dB on the melodic layer and 3 dB on the drums, under Kodak only

## QA after the last render (`runs/thankful-x-blessings/20261012-221901`)

- verdict: review, -7.8 LUFS, -1.0 dBTP, 4:18
- Blessings' drums/bass/other re-split with BS-RoFormer SW (PR #10); the HT-Demucs stems are backed up outside the repo. Same QA flags and Whisper reading as the HT-Demucs render (20261012-021358)
- Kodak vs beat: -2.8 LU where he raps (v3 before this pass: +6.2 LU)
- Whisper on the finished mix: Kodak verse 1 68%, verse 2 67% with the hook (v6: 68% / 67%) after the softer tone (v4/v5: 70% / 70%; v2:
  64% / 61%; auto draft: about 45%), against a 74% ceiling on the isolated acapella
- hook presence over the beat on the phrase bars: +5.4 to +6.9 dB
- vocal presence (1-4 kHz, target about +7 dB): 4.7-7.3 dB in the verses, 17 dB in the second breakdown; QA no
  longer flags any Kodak bar as buried
- accepted: plan bars 49-52 and 105-110 are Clementine's faint background chops (-26 to -41 dB in her stem), kept
  at the record's balance; `clem-end` reads 12% of sung frames off the bass (7 of 56), but it is her own vocal over
  Calvin Harris's own bassline at the original alignment, so `mix follow` would be the wrong fix; Whisper reads 0%
  of Clementine here and on the original master alike

## Needs ears

- Does "see my blessings" work as the hook, three times into Clementine's line at the peak?

- Is Kodak clear now, and does the doubled take still bother you? (It is in the recording itself.)
- Does the shorter intro (couplet at 0:37) feel right?
- Is the beat loud enough now, or does Kodak need 1-2 dB back?
- Is Kodak smooth enough now, or still harsh? (The fully natural tone, his record's own, costs verse 1 about 6 points of clarity.)
