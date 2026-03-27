# Private Overlay Workflow

This repo is designed to stay shareable while letting you work with paid commercial samples locally.

## Paths

- committed scaffold pack: `samples/edm-core`
- gitignored raw vendor source: `private-packs/vendor-sources/kshmr-vol-4/raw`
- gitignored local mapping file: `private-packs/vendor-sources/kshmr-vol-4/import-map.json`
- gitignored curated runtime pack: `private-packs/runtime/edm-core`

## Workflow

1. Run `npm run vendor:init`.
2. Copy your purchased KSHMR Vol. 4 files into `private-packs/vendor-sources/kshmr-vol-4/raw`.
3. Edit the local `import-map.json` and choose the exact files you want for each runtime family.
4. Run `npm run vendor:import`.
5. In the app, switch pack mode to `Private Overlay` or leave it on `Auto`.

## Rules

- Do not commit anything under `private-packs/`.
- Keep track code using stable runtime names only.
- Keep the runtime pack small even if the source library is huge.
- Preserve at least one solid family for each of:
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
