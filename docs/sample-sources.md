# Sample sources for Daybreak Ferry

Research checked 2026-10-03. The goal is an original melodic house instrumental with warm, moving synths and restrained percussion. These are recommendations for this project; price, sample count and vendor reputation do not establish how a sound will work in a particular mix.

## Recommended local palette

| Role | Recording selected | Reason |
| --- | --- | --- |
| Drums | Goldbaby MPC60 vs MD vs Rytm | Recorded Elektron drums through an MPC60; short kick choices and distinct hat takes |
| Pad | Goldbaby PPG Wave 2.2, Simple3 program | Stereo hardware synth recording with a different character from the mallet hook |
| Bass | Goldbaby PPG Wave 2.2, NiceA program | Separate synth program, prepared in mono for the low end |
| Hook | Goldbaby Hapi vs Xylophone | A recorded tank drum and xylophone layer supplies a percussive, organic attack |

All three libraries are available from [Goldbaby's free-pack page](https://www.goldbaby.co.nz/freestuff.html). Its [licence](https://www.goldbaby.co.nz/termsandconditio.html) permits incorporating the free sounds in musical productions, including commercial compositions, and prohibits redistributing the samples. Archives, prepared WAVs and the runtime overlay therefore stay under gitignored `private-packs/`. Only original synthesized fallback assets are committed.

This selection is a musical inference from the source material and the needs of this song. It is not a claim that the band uses these packs. In their [Tape Notes interview](https://tapenotes.co.uk/project/tn150-rufus-du-sol), RÜFÜS DU SOL describe layered choir/synth pads, a Scarbo patch, and subtle swung gating. They also discuss browsing Splice for inspiration.

## Other sources researched

| Source | What it offers | Fit for this workflow |
| --- | --- | --- |
| [Wave Alchemy 909 Tape](https://www.wavealchemy.co.uk/product/909-tape/) | Free TR-909 recordings through Studer and Ampex tape machines | A useful alternative drum palette; not installed for this render. Its [FAQ](https://www.wavealchemy.co.uk/support/faq/) confirms commercial music use of free packs. |
| [Samples From Mars Analog Tape Synths](https://samplesfrommars.com/pages/free-analog-tape-synths) | Free multisampled analog synths in WAV format | Attractive for DAW music production; the [FAQ](https://samplesfrommars.com/pages/faq) excludes use in websites, applications or software without a separate licence, so not selected for this browser sampler. |
| [Scarbo](https://teletoneaudio.com/collections/frontpage/products/scarbo) | Paid Kontakt instrument named by the band in the interview | A particularly relevant future DAW instrument, rather than a drop-in Strudel WAV pack. No purchase made. |
| [Splice melodic house](https://splice.com/sounds/genres/melodic-house/samples?sort=popularity) | A searchable catalogue of samples, one-shots and presets | Useful for auditioning individual sounds with an existing subscription; not used for this render. |

## Install the recorded palette locally

Download these archives through the links on Goldbaby's official free-pack page:

- `MPC60vsMDvsRytm.zip`
- `PPG_Wave2_Free.zip`
- `GB_Hapi_vs_Xylophone.zip`

Put them in `private-packs/vendor-sources/goldbaby/archives/`. Install the optional Python analysis requirements described in the README, then run:

```sh
npm run install:goldbaby-pack
```

An alternative archive location can be passed with `-- --archives /path/to/archives`. The command itself is offline. It reads the included EXS root and fine-tuning fields, repitches the nearest recorded notes into explicit roots for this song, prepares sustained pads with overlapping loops, retains instrument/clap stereo, and imports 40 assets into the existing private overlay. It does not reproduce the full Kontakt or EXS preset processing. Source filenames, tuning adjustments and archive hashes are recorded locally in `prep-report.json`.

`glass-harbor song serve` automatically selects this overlay. When the overlay is absent, the public synthetic pack remains available. Its pad, FM pluck and sub bass have distinct synthesis models, all the notes used by Daybreak Ferry have native root samples, and noise generation is deterministic. Public regenerated WAVs have a peak ceiling of 0.85.

Sample integrity, tuning and render continuity can be measured locally. Those checks and the rule-based critique do not establish musical quality; listener feedback decides whether to approve a baseline.
