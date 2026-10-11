# Set test: Get Up -> edit -> Get Up

## Goal

- kind: set (a DJ test of the yeah bop x Get Up edit's intro and outro, not a release)
- vibe: drum & bass, mixed the way a DJ would: intros over outros, bass swaps on each incoming drop

## Sources

- `t1`: get-up (Amplify & Bou, "Get Up"), its last 51 bars (from bar 145)
- `t2`: ybgu-edit (the rendered yeah bop x Get Up v3 edit, imported and analyzed like any record)
- `t3`: get-up again (stand-in for a different DnB track)

## Decisions

- The edit enters at output bar 33: its beatless intro rides Get Up's last section, and its drop lands on Get Up's
  outro at output bar 49, where Get Up's low end cuts (bass swap).
- The next track enters at output bar 211 over the edit's outro; its drop lands at output bar 227, where the edit's
  low end cuts.
- QA found no beat-alignment problems through either transition. The edit's drops sit 1.9 dB under Get Up's
  (-5.9 vs -4.0 LUFS); a DJ trims that.
