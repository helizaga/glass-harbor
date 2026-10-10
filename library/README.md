# Track library (local only)

`glass-harbor track add <file>` decodes audio here. Everything in this folder except this README is gitignored:
source audio and stems are private and stay on this machine.

```text
library/<track-id>/
  track.json       title, source filename, sha256, which stems exist and how they were made
  audio.flac       decoded 44.1 kHz stereo source
  stems/*.flac     vocals, instrumental, drums, bass, other (from `track separate` or `--stem`)
  analysis.json    beat grid, bpm, key/Camelot, loudness, per-bar levels, sections, vocal phrases
```
