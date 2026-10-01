# The Guides — PDF Style Guide

The visual identity shared by every guide's PDF. One theme, one set of fonts and
neutrals; each guide changes only its **title, subtitle, category (which sets the
accent colour), motif and back-cover copy**, all in its `guide.toml`. The editorial
standard these components serve is in `EDITORIAL.md`. The goal: every guide reads like a professionally published
programming book, and any two guides are recognisably from the same series.

## Principles

1. **A book, not a repository.** No setup instructions, file trees of the repo,
   companion-code pointers or build notes (`<!--repo-only-->` removes them). No
   web navigation: Previous | Next links and horizontal rules are stripped.
2. **Quiet structure, generous space.** Hierarchy comes from type weight, size and
   space, not from boxes and lines. Colour is used sparingly and always means
   something.
3. **Code is first-class.** Code sits on a calm panel, never overflows, never uses
   ligatures, and is labelled by language.
4. **Consistent everywhere.** Fonts ship with the guide, so a local build and a
   CI release are identical.

## Page

| Property | Value |
|---|---|
| Trim | 7.5 × 9.25 in (a standard programming-book size), single-sided |
| Margins | 0.95 in top and bottom, 0.85 in left and right |
| Body measure | about 75 characters per line |
| Running head | Chapter (small caps, left) · lesson number and title (right), hairline below |
| Folio | Page number bottom right in the accent; guide title bottom left in grey |
| Front matter | Cover, colophon, contents and preface; roman page numbers |

## Typography

| Role | Typeface | Setting |
|---|---|---|
| Body | **Source Serif 4** | 10 pt, 1.18 line spacing, old-style figures, justified with hyphenation |
| Headings, labels, tables | **Inter** | Lesson title 23 pt Bold; section 15 pt Bold; subsection 11.5 pt SemiBold in accent |
| Display | **Inter** ExtraBold | Cover title 46 pt; chapter numbers 58 pt |
| Code | **JetBrains Mono** | 8.4 / 11.2 pt, ligatures off, long lines wrap with a ↪ marker |

All three are SIL Open Font License fonts, stored in `tools/pdf/fonts/` with their
licences.

**Script fonts (opt-in).** A language-learning book that sets `language` in
`guide.toml` also ships that script's fonts, used through xeCJK beside the Latin
faces: for Japanese (`ja`), **Noto Serif JP** in body text and **Noto Sans JP** in
headings, labels and tables (Regular and Bold, OFL, in `tools/pdf/fonts-ja/`).
Other guides don't carry them. Example sentences (a blockquote that opens with
the target script) are set as examples: a thin accent rule at the left, no
quote styling.

## Colour

Neutrals (shared by every guide):

| Token | Hex | Used for |
|---|---|---|
| Ink | `#1E2329` | Body text, headings |
| Muted | `#69707A` | Running heads, labels, captions |
| Faint | `#A7ADB5` | Secondary text on dark, output-panel edge |
| Rule | `#E3E0D8` | Hairlines, table rules, the exercise box border |
| Panel | `#F7F6F2` | Code panels, table stripes (a warm paper tone) |
| Night | `#16202E` | Cover, chapter bands, part pages |

Semantic colours (shared):

| Callout | Ink | Tint |
|---|---|---|
| Note | `#3B5B8C` | `#EEF2F8` |
| Warning | `#B45309` | `#FDF4E6` |
| Tip | the category's text shade | the category's tint |

Accent (per category, in `categories.json`): four shades per category.
**accent** for rules, bullets and code-panel edges; **bright** for the cover and
chapter bands (at least 4.5:1 on Night); **dark** for links, inline code and small
accent text (at least 5.2:1 on white); **tint** for Summary panels and Tip callouts.

| Category | Accent | Profile |
|---|---|---|
| Programming | `#3E8E41` | technical |
| Software Engineering | `#1F7FB0` | technical |
| Computer Science | `#4F55C4` | technical |
| Artificial Intelligence | `#B0388F` | technical |
| Career | `#D0573A` | general |
| Product Management | `#12887C` | general |
| Personal Finance | `#B8870F` | general |
| Business | `#B32E48` | general |
| History | `#8C5A35` | general |
| Psychology | `#7E4BB0` | general |
| Education | `#D9801F` | general |
| Language | `#2E63C4` | general |

Every book uses the same Night cover (treatment A); only the accent changes.

## Components

- **Cover**: full-bleed Night. The category (e.g. PROGRAMMING) in the bright
  accent at the top, an accent bar, the title in Inter ExtraBold, the subtitle in
  Source Serif italic, the motif in the lower right with three accent cells, and
  at the bottom the coverage line ("Covers Node.js 24 LTS") and edition line
  ("First Edition · Version 1.0.0 · September 2026"). No author.
- **Copyright page** (back of the cover): title, subtitle, edition, copyright,
  trademark notices (`trademarks` in `guide.toml`), the standard disclaimer,
  typefaces and build date.
- **Contents**: chapters in Inter SemiBold with accent numbers; sections in serif
  with `N.k` numbers and dotted leaders; chapter-end pages, glossary and index
  unnumbered.
- **Chapter opener**: a Night band across the top third with the motif,
  "CHAPTER", a large number and the title, over a thin accent stripe. The
  chapter introduction starts on the same page.
- **Section opener**: new page; `N.k` in accent, title 23 pt, a short accent rule.
- **Running heads**: chapter (small caps, left), section number and title (right).
- **Figures**: Mermaid diagrams as vector PDF in the category colours, kept on
  one page with their caption, numbered per chapter ("FIGURE 1.2" in accent small
  caps, then the caption in grey).
- **Listings**: a warm panel with a 2 pt accent edge and a language label top
  right; a whole-file listing carries its file name as a title with a hairline
  beneath. Terminal and output blocks use a grey edge. No ligatures, no
  hyphenation, long lines wrap with ↪.
- **Callouts**: Note (slate), Tip (category tint), Warning (amber): a tinted box
  with a 3 pt edge and a small-caps label, set ragged-right.
- **Sidebars** ("Going Deeper"): a bordered Panel box with a GOING DEEPER label
  and an accent title.
- **Summary**: an accent-tint panel closing every section.
- **Chapter end**: an unnumbered page with Exercises (grouped by section) and
  Further Reading; external links show their URL as a footnote.
- **Cross-references**: links to sections and chapters gain "(section 1.3)" in
  the PDF unless the link text already names the number.
- **Tables**: Inter, accent top rule, hairline bottom rule, striped rows.
- **Glossary**: large accent letters with a hairline, bold terms.
- **Index**: generated from the glossary terms, two columns, accent page numbers.
- **Part page** (e.g. "Reference"): full Night page with the motif and an accent bar.
  In a book with numbered parts, every part page shows "PART" and a large roman
  numeral (unnumbered for back-matter parts), and the contents opens each part
  with a small accent "PART II" label, the part title and a hairline.
- **Problem** (books with problem sets): a hairline, then "PROBLEM 5.2" in
  accent small caps with the difficulty as three dots (filled in the accent)
  and a label, the title in Inter Bold, the signatures in code, and the target.
  The examples sit in one neutral panel labelled EXAMPLES. The problem closes
  with right-aligned links: "Hint, page N · Solution, page N".
- **Hints and Solutions**: parts at the back. Each chapter's hints run on under a
  small "Chapter 5" heading; each chapter's solutions start a new page. Every
  entry is labelled "HINT 5.2" or "SOLUTION 5.2" and links back to its problem
  by page; a solution's bold lead-ins ("Key insight.") are set as accent run-in
  labels.
- **Back cover**: Night; category, accent bar, the blurb in white serif, title
  and coverage at the bottom.

## Writing conventions the theme relies on

See `EDITORIAL.md`; in short: one H1 per page; chapter openers titled
`# Chapter N — Title`; callouts `> **Note:**`, `> **Tip:**`, `> **Warning:**`;
sidebars `### Going Deeper: Title`; `## Summary` closing each section; figures
followed by `*Figure: …*`; whole-file listings starting with a `// file.js`
comment; glossary letters as `### A`; no emoji.

## Files

| File | Purpose |
|---|---|
| `EDITORIAL.md` | The house style sheet (core, technical and general profiles) |
| `STYLE.md` | This file: the visual identity |
| `categories.json` | Category subject lines, profiles and colours |
| `packages.tex` | LaTeX packages the theme needs |
| `theme.tex` | The shared theme: page, fonts, colours, every component |
| `guide.lua` | Pandoc filter mapping Markdown conventions to theme components |
| `highlight.theme` | Syntax-highlighting palette |
| `mermaid-config.json` | Diagram colours (filled in per category at build time) |
| `fonts/` | Source Serif 4, Inter, JetBrains Mono, with licences |

Per guide: `guide.toml` at the root. The build generates `build/brand.tex` and
`build/mermaid-config.json` from it.
