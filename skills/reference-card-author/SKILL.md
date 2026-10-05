---
name: reference-card-author
description: Create or revise Glass Harbor reference cards in references/*.md and references/*.json from listening notes or arrangement observations. Use when the task is to add reusable style memory without copying copyrighted songs, stems, or transcriptions.
---

# Reference Card Author

Use this skill to turn listening notes into reusable arrangement memory for this repo.

Primary outputs:

- `references/<slug>.md`
- `references/<slug>.json`

## What Reference Cards Are For

Reference cards are retrieval aids for:

- song generation
- critique
- compare decisions

They should capture patterns, not copies.

## What Not To Do

- do not include copyrighted lyrics
- do not write note-for-note transcriptions
- do not mention vendor sample names
- do not store audio or stems
- do not anchor the card to one exact commercial song arrangement in a way that makes it derivative

## Required Shape

The Markdown card should include:

- title
- tags
- BPM range
- mood
- section map
- energy curve
- active sound roles by section
- groove notes
- harmony summary
- transition recipes
- reusable takeaways

The JSON sidecar should include:

- `genre_tags`
- `mood_tags`
- `bpm_range`
- `section_map`
- `energy_curve`
- `roles_by_section`
- `groove_notes`
- `harmonic_summary`
- `transition_recipes`
- `anti_goals`

Match the existing cards in `references/`.

## Writing Rules

- keep each card abstract and reusable
- describe arrangement logic, not brand names
- write for retrieval, not prose beauty
- prefer compact, clear bullets
- make the JSON and Markdown agree

## Good Source Material

Use:

- listening notes
- arrangement observations
- structural patterns seen across many songs
- contrast and transition recipes

If a note feels too specific to one copyrighted track, generalize it before writing the card.

## Quality Bar

A good reference card:

- helps a songwriter choose section density and motion
- helps a critic explain what is missing or overdone
- is broad enough to reuse across multiple songs
- stays small enough to retrieve quickly
