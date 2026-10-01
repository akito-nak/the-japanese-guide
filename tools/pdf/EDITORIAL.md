# House Style Sheet

The editorial standard for every guide. Each guide is written as a book: the
Markdown is the manuscript, read on GitHub, and the PDF is the published edition.
There is one text; both must read like a professionally edited book.

The standard has a **core** that applies to every guide and two **profiles**:

- **Technical** (Programming, Software Engineering, Computer Science, Artificial
  Intelligence): code listings, companion code, exercises.
- **General** (Career, Product Management, Personal Finance, Business, History,
  Psychology, Education, Language): no code apparatus; questions to consider and
  cited sources. Books that teach a language add the language-learning rules at
  the end of Part 3 (practice and answers instead of questions to consider).

A guide declares its category (and so its profile) in `guide.toml`.
`build_guide_pdf.py --check` enforces everything marked **[checked]**.

---

## Part 1 — Core

### 1. Voice

- Warm, direct and confident. Second person ("you"); "we" when working through
  something together. Encouraging, never condescending or cute.
- Explain **why** before **how**. Build from first principles. Show where things
  go wrong in real life.
- **No scaffolding sentences.** Don't announce what a section will do or has
  done ("In this section we'll…", "Now that we've covered…", "Let's dive in").
  Start with the substance. **[checked]** for the common forms.
- One idea per paragraph; paragraphs of two to six sentences. Vary sentence
  length. Cut filler: "basically", "simply", "just", "very", "really", "of
  course", "it's important to note that".
- Say each thing once, in the place it matters. Summaries and chapter-end
  material restate the essentials; they don't repeat callouts word for word.
- Be precise and honest. No invented facts, figures, quotes or benchmarks. Date
  anything that will change ("as of September 2026"). When evidence is mixed,
  say so.
- Anonymous: never the author's name, handle, email, employer, location or
  personal projects. Neutral examples (`example.com`, "a job-search app").

### 2. Terms and mechanics

- The book is "this book"; its parts are **chapters** and **sections**. Never
  "guide", "lesson", "module" or "tutorial" for the book's own structure.
  **[checked]**
- Cross-references: "chapter 5", "section 5.3" in running text (lowercase unless
  starting a sentence). Link the words to the target page. Never "the previous
  section", "the next lesson", "below" or "above" for anything in another
  section. **[checked]**
- US spelling. Serial comma: **no** (write "V8, libuv and a standard library"),
  unless needed for clarity.
- Numbers: spell out one to nine, digits for 10 and above, and always digits
  with units (5 ms, 3 GB, 8 bits), versions and section numbers.
- Punctuation: straight quotes and apostrophes in Markdown (the PDF curls
  them). Em dashes only in titles and list glosses; in prose use commas,
  colons, parentheses or a new sentence. No emoji anywhere. **[checked]**
- Headings in title case ("Choosing a Version", "What Node Is For"). Keep them
  short; no end punctuation.
- Bold introduces a term the first time it is defined; italics for emphasis,
  sparingly. Every bolded defined term appears in the glossary.

### 3. Book structure

```text
Front matter   cover · copyright page · contents · preface
Chapter        opener · sections N.1…N.k · chapter end
Back matter    reference pages · glossary · index · back cover
```

**Preface** (the root README, as book text) contains, in order: why the book
exists (two or three paragraphs); **Who This Book Is For**; **What You Need**;
**How This Book Is Organized** (one or two sentences per chapter);
**Conventions Used in This Book**. Marketing copy goes on the back cover
(`blurb` in `guide.toml`), not in the preface.

**Chapter opener** (`NN-chapter/README.md`): `# Chapter N — Title`, two or three
paragraphs that motivate the chapter, then **In This Chapter** (four to eight
bullets of concrete outcomes), then **Before You Start** (prerequisites, one
short paragraph; omit in chapter 1 if the preface covers it). The list of
sections and any "continue to chapter N+1" navigation are repo-only.

**Section** (`NN-chapter/NN-title.md`), typically 2,000–4,000 words:

1. `# Title` (exactly one H1).
2. Opening: one to three paragraphs that start with the substance: a problem, a
   question, an example or a story.
3. The body in `##` headings, built from first principles, with figures,
   listings, callouts and sidebars as needed.
4. `## Summary`: three to six bullets, each a complete statement a reader could
   review a week later. **[checked]** (present, 3–6 bullets)

**Chapter end** (`NN-chapter/99-….md`, the chapter's last page):

- Technical profile: `# Exercises and Further Reading`, with `## Exercises`
  (grouped under `### N.k Section Title`, numbered) and `## Further Reading`.
- General profile: `# Questions and Sources`, with `## Questions to Consider`
  and `## Sources and Further Reading`.
- Further Reading: three to eight entries, each a link plus one sentence on why
  it's worth the reader's time. Primary sources first (official documentation,
  specifications, original papers, books), then talks and articles.
- End with one short paragraph that bridges to the next chapter, in prose.

**Back matter**: reference pages (the quick reference, the full further-reading
list or bibliography), then the glossary (always the last page). The PDF adds
the index and back cover automatically.

**Parts** (optional, for books of about 15 chapters or more): group chapters
into parts with a marker on the first line of the first chapter's opener,
`<!--pdf-part: Part II — Array and Search Patterns-->`. The PDF gives each part
a numbered part page and a heading in the contents. In a book with parts, the
back-matter parts (`<!--pdf-part: Reference-->`, and Hints and Solutions in a
book with problem sets) are set the same way, unnumbered.

### 4. Figures

- Diagrams are Mermaid in ```` ```mermaid ```` blocks (or a committed PNG from a
  committed script, for data charts). Use one where a picture explains faster
  than prose; don't decorate.
- Every figure is followed immediately by a caption line in italics that starts
  with `Figure:` and states the takeaway, not just the topic:

  ```markdown
  *Figure: One thread serves both requests, because it never waits idle for the database.*
  ```

  The PDF numbers it (Figure 1.2). **[checked]**
- Refer to figures in the text as "the figure above/below" or by describing
  them; the number is added in the PDF.
- No emoji or decorative icons in diagrams. Keep node labels short.

### 5. Callouts and sidebars

Callouts are short (one to four sentences) and stand apart from the flow:

| Markdown | Use for |
|---|---|
| `> **Note:** …` | A useful aside: context, history, a clarification |
| `> **Tip:** …` | A better way to do something; a shortcut |
| `> **Warning:** …` | A trap, a common mistake, something that breaks or costs money |

No other labels. **[checked]** At most three callouts per section, and never two
in a row.

**Sidebars** are longer, optional digressions (a paragraph to a page) with a
title, written as `### Going Deeper: Title` in the Markdown. Everything until
the next heading belongs to the sidebar; the PDF sets it in a box. Use them for
internals, history and edge cases a first-time reader can skip.

### 6. Tables and lists

- Tables for comparisons and reference data (options, flags, trade-offs). Keep
  cells short; introduce each table with a sentence.
- Bulleted lists for unordered sets, numbered lists for sequences. Bold lead-ins
  ("**Pin the version.** Because …") when items have a name and an explanation.
- No list with a single item; no more than about eight items without grouping.

### 7. Glossary and index

- Every term introduced in bold is in the glossary: `**Term** — definition.`,
  grouped under `### A`, `### B` …, with a link to the section that explains it.
- The index is generated from the glossary terms (every section that mentions a
  term). Adding a term to the glossary indexes it.

### 8. The repository versus the book

- Anything about the repository itself is wrapped in `<!--repo-only-->` …
  `<!--/repo-only-->`: setup, file structure, companion code, commands that run
  files in the repo, CI and release notes, section lists and navigation.
  **[checked]**
- Book text never says "companion code", "this repository" or points at repo
  paths. It says "create a file called `server.js`".

---

## Part 2 — Technical profile

### Code listings

- Every listing is complete enough to run, or clearly marked as a fragment in
  the surrounding sentence ("the handler now looks like this:").
- Show output in a comment on the same line (`// → 42`) for one-liners, or in a
  following ```` ```text ```` block for longer output. Output shown is real
  output, copied from a run on the stated version.
- When a listing is a whole file the reader should create, its first line is a
  comment with the file name, which the PDF turns into the listing's title:

  ```js
  // server.js
  import { createServer } from 'node:http';
  ```

- Code lines at most 80 characters (output blocks are exempt: they're copied verbatim). **[checked]**
- Language tags on every block: `js`, `ts`, `json`, `bash` (commands), `text`
  (output), `mermaid`, and so on. `bash` blocks contain commands only; put
  their output in a separate `text` block.

### Versions

- State the version the book targets in the preface, and the version that
  introduced any feature newer than two major releases ("since Node 22").
- Version-sensitive claims name their date or version.

### Companion code

- One runnable program per chapter plus tests; runs offline, deterministically,
  in seconds; described only in repo-only blocks.

### Problem sets

For books whose exercises are graded problems (algorithms, interview
preparation), set `problem_sets = true` in `guide.toml`. The model is the
problem book: problems at the end of each chapter, hints and solutions in parts
of their own at the back, so a reader never sees an answer by accident.
**[checked]** throughout.

- The chapter-end page is `# Problems and Further Reading`, with `## Problems`
  and `## Further Reading`. A chapter with no problems (an orientation chapter,
  say) ends with `# Further Reading` alone.
- Each problem is `### N.k Title` (a real name, "Two Sum on a Sorted Array",
  not a function name), numbered from 1 in each chapter and ordered by
  difficulty. The next line is its difficulty and target, then its signatures:

  ```markdown
  ### 5.2 Two Sum on a Sorted Array

  **Easy** · Target: O(n) time, O(1) space

  `twoSumSorted(nums, target)` · `two_sum_sorted(nums, target)`
  ```

  Difficulty is Easy, Medium or Hard. Then the statement, one ```` ```text ````
  block holding every example (each an `Input:`/`Output:`/`Note:` group,
  separated by blank lines), and `**Constraints**` with a list.
- No hints or answers on the problem page. Links from a problem to its hint and
  solution are repo-only; the PDF prints "Hint, page N · Solution, page N".
- Hints live in `hints/NN-chapter.md` and solutions in `solutions/NN-chapter.md`,
  one page per chapter titled `# Chapter N — Title`, each entry `## N.k Title`
  with the problem's exact title. `hints/README.md` and `solutions/README.md`
  open their parts (`# Hints`, `# Solutions`).
- Hints are graduated: a numbered list of one to three nudges, each more
  specific than the last. The first names the idea; none contains the code.
- A solution runs: **Brute force.** (what it costs and why it's too slow),
  **Key insight.**, **Algorithm.**, the listings, **Complexity.**, **Common
  mistakes.** Bold lead-ins end with a period. Solution code is generated from
  the tested reference code, never copied by hand.

---

## Part 3 — General profile

- No code listings; commands or formulas only where the subject needs them.
- Claims of fact carry a source: link the source in the text where it's used and
  list it under **Sources and Further Reading**. Statistics include the year.
- Chapters with legal, financial, medical or safety implications carry a short
  scope note ("This chapter describes US rules as of 2026; it isn't advice.").
- Questions to Consider are open questions that make the reader apply the
  chapter to their own situation; four to eight per chapter, grouped by section
  where helpful.

### Language-learning books

A General-profile book that teaches a language declares it in `guide.toml`
(`language = "ja"`). That loads the language's script fonts in the PDF and
switches on these rules, which take precedence over the general profile where
they differ. Today the supported language is Japanese (`ja`).

**Voice.** Learners come to a language out of passion; the book mirrors it.
Warm, lively and a little playful: a joke, a vivid image or a memorable
contrast is welcome when it makes a point stick (橋 *hashi* "bridge" and 箸
*hashi* "chopsticks"). Humor serves the learning; it never replaces an
explanation, mocks the learner or the culture, or uses emoji.

**Organization.** Build skills before applying them: the writing system and
core grammar first, then register and real usage, then culture and context, then
goal-oriented paths (media, work, exams). Group chapters into parts. Each section
teaches one coherent skill or topic.

**Example sentences** are blockquotes: the target-language sentence, its
romanization in italics, then the English translation, one per line with a
trailing backslash for the line break. A quote that opens with the target
script is set as an example in the PDF.

```markdown
> 私は寿司を食べます。\
> *Watashi wa sushi o tabemasu.*\
> I eat sushi.
```

In examples and tables, bold marks the form being taught (私**は**学生です); it
is not a defined term and needs no glossary entry. Add a literal gloss in brackets when the word order matters ("I [topic] sushi
[object] eat"). Several short examples may share one blockquote, separated by a
blank `>` line.

**Romanization.** Modified Hepburn with macrons for long vowels (*tōkyō*, *kōhī*)
in examples and glosses. English running text uses the common English spelling of
place names and loanwords (Tokyo, Osaka, sushi). Part I gives romanization for
every example; later parts give it only for new vocabulary and where a reading
is not obvious. Readings of kanji follow the word in parentheses on first use:
食べる (たべる).

**Target-language terms** in running text appear in the script, followed by
romanization and meaning on first use: 敬語 (*keigo*, honorific language). After
that, either form alone is fine. Terms the reader must learn are bolded on first
use and go in the glossary like any other term.

**Tables** carry vocabulary, conjugations, kana charts and comparisons. Columns
in the order the reader needs them: script, reading, meaning, notes.

**Chapter end.** The chapter-end page is `# Practice and Further Reading`, with
`## Practice` and `## Further Reading` **[checked]**:

- Practice is graded, active work: reading, writing, recognition, translation
  in both directions, conjugation drills and, in culture chapters, short
  comprehension or situation exercises ("What would you say when…"). Grouped by
  section under `### N.k Section Title` with numbered items, easiest first;
  10 to 30 items per chapter.
- Answers live at the back of the book: `answers/README.md` opens the part
  (`# Answers`), and `answers/NN-chapter.md`, titled `# Chapter N — Title`, has
  `## N.k Section Title` for every practice group, numbered to match. No answers
  on the practice page. **[checked]**
- Further Reading lists three to eight resources with a sentence each:
  dictionaries, graded readers, official sources (the JLPT site, NHK), books
  and well-regarded courses.

**Facts.** Culture, history and statistics follow the general profile: claims
carry a source and a date. Language usage that is changing (slang, new keigo)
is dated ("as of 2026").

---

## Checklist for an editor pass

- [ ] No scaffolding sentences; every section opens with substance
- [ ] Nothing said twice; callouts don't duplicate the summary
- [ ] Terms: book / chapter / section; cross-references by number
- [ ] Every figure captioned with its takeaway
- [ ] Callouts: only Note / Tip / Warning, at most three per section
- [ ] Summary: 3–6 standalone bullets
- [ ] Chapter end: exercises or questions, further reading, bridge paragraph
- [ ] Every bold term in the glossary
- [ ] Facts, versions and outputs verified; anything time-sensitive dated
- [ ] Repo-only material wrapped; book text reads cleanly without it
