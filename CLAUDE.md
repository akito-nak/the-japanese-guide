# The Japanese Guide

A book for learning Japanese (subtitle *From First Kana to Real-World Fluency*,
First Edition), written as Markdown (read on GitHub) and published as a typeset
PDF on the Releases page. The Markdown is the manuscript; both must read like a
professionally edited language-learning book.

## The standard (read these first)

- `tools/pdf/EDITORIAL.md`: the house style sheet. This book follows the core,
  the general profile and the **Language-learning books** rules at the end of
  Part 3. Binding.
- `tools/pdf/STYLE.md`: the visual identity of the PDF (LANGUAGE category blue,
  plus the Japanese script fonts in `tools/pdf/fonts-ja/`).
- `guide.toml`: title, subtitle, category (LANGUAGE), `language = "ja"`,
  edition, coverage, trademarks, back-cover copy.

The canonical copy of the standard lives in the `build-guide-pdf` skill; update
this repo's copy with `python3 ~/.claude/skills/build-guide-pdf/build_guide_pdf.py --sync`.
`python3 tools/build_guide_pdf.py --check` enforces the checkable parts and must
pass before any commit.

## This book's specifics

- **Audience:** English speakers from zero Japanese to advanced. Beginners read
  Part I in order; others jump to the chapters that fit their goals.
- **Method:** the book teaches the best-supported way to learn Japanese, not
  just Japanese (EDITORIAL.md, "Method"). Chapter 1 sets out the research
  (section 1.2, "Study and Immersion: The Middle Path"); later chapters apply it
  and cross-reference section 1.2 rather than re-explaining it. Every research
  claim names its study and year and is fact-checked; experience is labeled as
  experience. The Chinese guide (`../the-chinese-guide/`) is the sister model.
- **Tone:** warm, lively, a little playful. Learners are passionate; mirror it.
  Humor must help a point stick, never replace an explanation. No emoji.
- **Examples:** blockquote with Japanese, then *romaji*, then English, one per
  line with a trailing backslash. Romaji on every example in Part I (chapters
  1–5); afterward only for new words and non-obvious readings. Modified
  Hepburn with macrons.
- **Dates:** slang, new usage, prices, JLPT details and statistics carry a date
  ("as of 2026").
- **Layout:** `NN-chapter/README.md` (chapter opener; chapters 1, 6, 8 and 12
  start Parts I–IV), `NN-chapter/NN-title.md` (sections, each ending in
  `## Summary`), `NN-chapter/99-practice-and-further-reading.md` (chapter end),
  `reference/` and `answers/` (back matter; `answers/NN-chapter.md` matches each
  practice group by number and title) and `99-glossary/` (always last).
  `SUMMARY.md` is the reading order. Run `python3 tools/build_guide_pdf.py --nav`
  after changing it; never hand-edit navigation.
- **Anonymous:** no author name, handle or personal details anywhere.
- **PDF:** never committed. Tag `vX.Y.Z` and push the tag; the release workflow
  builds and publishes it.
