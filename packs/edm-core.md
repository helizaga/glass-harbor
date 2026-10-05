# EDM Core Pack Policy

This repo ships a compact sound pack with stable names so tracks survive sample upgrades.

## Current Families

- `kick_main`: hero kick family for all main drops
- `clap_main`: main clap and lift clap family
- `hat_closed`: closed hat variants for groove and drop density
- `hat_open`: open hats for lift and air
- `perc_top`: top percussion accent family
- `impact_wide`: drop impacts
- `riser_up`: long transition riser
- `shimmer_fx`: high-frequency sparkle and sweep layer
- `air_texture`: background wash and atmosphere
- `vocal_chop`: phrase punctuation and ear candy

## Optional Tonal Families

- `bass_tonal`: sampled low-end hook layer when the bass needs more character than a browser synth
- `stab_tonal`: short harmonic or synth punctuation for hook identity
- `pluck_tonal`: short melodic or arpeggiated sample hook material

## Replacement Rules

- Keep the family names stable even when you replace the audio.
- Prefer a small number of high-confidence sounds over large undifferentiated folders.
- Upgrade one family at a time and regenerate `strudel.json` after changes.
- Keep `kick_main`, `clap_main`, and `hat_closed` especially disciplined because they define the whole groove identity.
- Song code must reference these stable families only, not vendor filenames or raw private paths.
- Review and generation tooling assume these family names stay stable across pack upgrades.
- Optional tonal families are additive. They can improve hook quality, but they must never replace the required core pack families.

## Quality Bar

- `kick_main`: mono-compatible low end, short click, controlled sub tail
- `clap_main`: strong midrange crack with a short stereo tail
- `hat_closed`: bright but not brittle, with at least one slightly softer variant
- `impact_wide` and `riser_up`: wide enough to feel cinematic without masking the drop attack
