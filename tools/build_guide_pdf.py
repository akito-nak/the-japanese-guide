#!/usr/bin/env python3
"""Build a single offline PDF from a multi-chapter Markdown guide using pandoc.

Concatenates the guide's Markdown (the root README/index first, then chapter
folders in natural order) into one file and renders a PDF via pandoc + a LaTeX
engine. Cross-file `.md` links are rewritten to internal PDF anchors so the
table of contents and Previous/Next navigation work offline.

Run from the root of the guide repo (auto-discovers structure):

    python ~/.claude/skills/build-guide-pdf/build_guide_pdf.py

The house standard (EDITORIAL.md, STYLE.md, categories.json and the PDF theme)
lives next to this script in the skill's theme/ folder. A guide adopts it with a
guide.toml at its root and a copy of the theme in tools/pdf/ (`--sync` installs or
updates that copy, so the guide's CI builds stand alone).

Override anything as needed:

    python .../build_guide_pdf.py --root path/to/guide --title "My Guide" \
        --author "Me" --output my-guide.pdf

Explicit ordering: if a `pdf-order.txt` file exists at the repo root, its
non-comment lines (files or directories, relative to root, one per line) are
used as the exact order instead of auto-discovery.

Book mode (this guide's addition): the PDF reads like a printed programming
book, not a repository. Before rendering, each page is transformed:

- `<!--repo-only-->` ... `<!--/repo-only-->` blocks are removed. Use them for
  anything about the repository itself: setup, file structure, companion code,
  commands that run files in the repo, CI and release notes.
- `<!--pdf-only ... -->` comments are unwrapped. Their content is invisible on
  GitHub and appears only in the PDF.
- Previous | Next navigation blocks are removed (a book has page turns).
- Headings are shifted so each chapter folder becomes a Part and each lesson a
  chapter: a folder's README keeps its H1 (the chapter opener, with the
  chapter introduction beneath it); every other page's headings move down one
  level.
  `<!--pdf-part: Title-->` starts a new Part at that point (e.g. "Reference").

`--check` also reports repo-specific text that would leak into the book.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Directories that never contain guide content.
SKIP_DIRS = {
    ".git", "build", "dist", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "target", ".pytest_cache", ".mypy_cache", ".tox", "site",
}
PDF_ENGINES = ("xelatex", "lualatex", "tectonic", "pdflatex")
UNICODE_ENGINES = {"xelatex", "lualatex", "tectonic"}  # support mainfont/monofont


def nat_key(s: str):
    """Natural sort key so 02 < 10 (not the lexicographic 10 < 2)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def walk_dir(d: Path):
    """Yield .md files in a directory: README first, then natural order,
    recursing into subdirectories after the current level's files."""
    files = sorted(
        (p for p in d.iterdir() if p.is_file() and p.suffix == ".md"),
        key=lambda p: (p.name.lower() != "readme.md", nat_key(p.name)),
    )
    subdirs = sorted(
        (p for p in d.iterdir()
         if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_DIRS),
        key=lambda p: nat_key(p.name),
    )
    for f in files:
        yield f
    for sub in subdirs:
        yield from walk_dir(sub)


def read_order_file(root: Path):
    """Explicit reading order, if the guide defines one. `pdf-order.txt` wins;
    otherwise `SUMMARY.md` (a list of `- [Title](path.md)` entries, the
    convention gen-nav tooling uses) defines the order."""
    for name in ("pdf-order.txt", ".pdf-order"):
        p = root / name
        if p.is_file():
            return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.strip().startswith("#")]
    summary = root / "SUMMARY.md"
    if summary.is_file():
        entries = re.findall(r"^\s*[-*]\s+\[[^\]]+\]\(\s*([^)\s#]+\.md)\s*\)",
                             summary.read_text(encoding="utf-8"), re.MULTILINE)
        if entries:
            return [e.removeprefix("./") for e in entries]
    return None


def collect_files(root: Path) -> list[Path]:
    order = read_order_file(root)
    files: list[Path] = []
    if order is not None:
        for entry in order:
            p = root / entry
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(walk_dir(p))
            else:
                print(f"warning: {entry} not found, skipping", file=sys.stderr)
    else:
        # Auto-discover: root README first, then top-level dirs in natural order.
        for name in ("README.md", "readme.md", "Readme.md"):
            if (root / name).is_file():
                files.append(root / name)
                break
        dirs = sorted(
            (p for p in root.iterdir()
             if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_DIRS),
            key=lambda p: nat_key(p.name),
        )
        for d in dirs:
            files.extend(walk_dir(d))
    # De-duplicate, preserving order.
    seen, out = set(), []
    for f in files:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            out.append(f)
    return out


def make_slug(rel: Path) -> str:
    parts = list(rel.parts)
    if parts[-1].lower().endswith(".md"):
        parts[-1] = parts[-1][:-3]
    if parts[-1].lower() == "readme":
        parts.pop()
    raw = "-".join(parts) if parts else "root"
    raw = re.sub(r"[^a-zA-Z0-9-]+", "-", raw).lower()
    raw = re.sub(r"-+", "-", raw).strip("-")
    return f"s-{raw or 'root'}"


LINK_RE = re.compile(r"(\[[^\]]*\])\(\s*([^)\s#]+\.md)(#[^)\s]*)?\s*\)")
IMAGE_RE = re.compile(r"(!\[[^\]]*\])\(\s*([^)\s]+)((?:\s+\"[^\"]*\")?)\s*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def rewrite_links(content: str, source_file: Path, path_to_slug: dict[Path, str]) -> str:
    """Rewrite cross-file `.md` links to internal `#slug` anchors. Links to files
    outside the build (and external URLs) are left untouched."""
    def repl(m: re.Match) -> str:
        text, target = m.group(1), m.group(2)
        try:
            target_path = (source_file.parent / target).resolve()
        except OSError:
            return m.group(0)
        slug = path_to_slug.get(target_path)
        return f"{text}(#{slug})" if slug else m.group(0)

    return LINK_RE.sub(repl, content)


def rewrite_images(content: str, source_file: Path, missing: list[str]) -> str:
    """Rewrite relative image paths to absolute ones. The combined Markdown lives
    in build/, so a path like `images/chart.png` written relative to a chapter
    file would otherwise not resolve and pandoc would silently drop the image.
    Missing images are appended to `missing` so the build can fail loudly.
    Image syntax inside code fences is left alone."""
    def repl(m: re.Match) -> str:
        alt, target, title = m.group(1), m.group(2), m.group(3)
        if re.match(r"^(https?:|data:|/)", target):
            return m.group(0)
        resolved = (source_file.parent / target).resolve()
        if not resolved.is_file():
            missing.append(f"{source_file}: {target}")
            return m.group(0)
        return f"{alt}({resolved.as_posix()}{title})"

    out, in_fence = [], False
    for line in content.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        out.append(line if in_fence else IMAGE_RE.sub(repl, line))
    return "\n".join(out)


def nav_links(content: str, source_file: Path) -> dict[str, Path]:
    """Find the Previous/Next links in a page's footer (its last 12 lines).
    Returns {"previous": path, "next": path} for whichever are present.
    Direction comes from the words "Previous"/"Next" or from arrows, either
    inside the link text (`[← Title](…)`, `[Title →](…)`) or right beside it
    (`← [Title](…)`, `[Title](…) →`)."""
    found: dict[str, Path] = {}
    for line in content.rstrip().split("\n")[-12:]:
        for m in re.finditer(r"\[([^\]]*)\]\(\s*([^)\s#]+\.md)[^)]*\)", line):
            text = m.group(1).lower()
            before = line[max(0, m.start() - 3):m.start()]
            after = line[m.end():m.end() + 3]
            target = (source_file.parent / m.group(2)).resolve()
            # Whole words only: "Preventing" in a title isn't "prev".
            if re.search(r"\bprev(?:ious)?\b", text) or "←" in text or "←" in before:
                found["previous"] = target
            elif re.search(r"\bnext\b", text) or "→" in text or "→" in after:
                found["next"] = target
    return found


NAV_OPEN, NAV_CLOSE = "<!--nav-->", "<!--/nav-->"
NAV_BLOCK_RE = re.compile(re.escape(NAV_OPEN) + r".*?" + re.escape(NAV_CLOSE), re.DOTALL)
# Markdown files that are repo meta, not guide pages; never reported as orphans.
NON_PAGE_FILES = {"summary.md", "contributing.md", "style.md", "build.md", "claude.md",
                  "changelog.md", "license.md", "code_of_conduct.md"}


def summary_titles(root: Path) -> dict[Path, str]:
    """Page titles as written in SUMMARY.md (`- [Title](path.md)`), if present."""
    summary = root / "SUMMARY.md"
    if not summary.is_file():
        return {}
    return {(root / path).resolve(): title.strip()
            for title, path in re.findall(r"^\s*[-*]\s+\[([^\]]+)\]\(\s*([^)\s#]+\.md)\s*\)",
                                          summary.read_text(encoding="utf-8"), re.MULTILINE)}


def page_title(f: Path, titles: dict[Path, str]) -> str:
    """SUMMARY.md title if there is one, else the page's first H1, else its filename."""
    if f.resolve() in titles:
        return titles[f.resolve()]
    in_fence = False
    for line in f.read_text(encoding="utf-8").split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence and re.match(r"^#\s+\S", line):
            return re.sub(r"\s*\{[^}]*\}\s*$", "", line[1:]).strip()
    return f.stem.replace("-", " ")


def nav_block(root: Path, files: list[Path], i: int, titles: dict[Path, str]) -> str:
    """The navigation block for page i, in the standard format:
    [← Previous: Title](…) | [Contents](…) | [Next: Title →](…)
    The first page has only Next; the last has only Previous and Contents."""
    cur = files[i]

    def rel(target: Path) -> str:
        return Path(os.path.relpath(target, cur.parent)).as_posix()

    parts = []
    if i > 0:
        parts.append(f"[← Previous: {page_title(files[i - 1], titles)}]({rel(files[i - 1])})")
    readme = root / "README.md"
    previous_is_readme = i > 0 and files[i - 1].resolve() == readme.resolve()
    if readme.is_file() and cur.resolve() != readme.resolve() and not previous_is_readme:
        parts.append(f"[Contents]({rel(readme)})")
    if i < len(files) - 1:
        parts.append(f"[Next: {page_title(files[i + 1], titles)} →]({rel(files[i + 1])})")
    return f"{NAV_OPEN}\n\n{' | '.join(parts)}\n\n{NAV_CLOSE}"


def write_nav(root: Path, files: list[Path]) -> tuple[list[Path], list[Path]]:
    """Regenerate every page's navigation from the reading order. Existing
    <!--nav--> blocks are replaced wherever they are (top and/or bottom); a page
    with none gets one appended at the bottom. A page with a hand-written footer
    but no markers is skipped, so navigation is never duplicated.
    Returns (changed, skipped)."""
    titles = summary_titles(root)
    changed, skipped = [], []
    for i, f in enumerate(files):
        before = f.read_text(encoding="utf-8")
        block = nav_block(root, files, i, titles)
        if NAV_BLOCK_RE.search(before):
            after = NAV_BLOCK_RE.sub(lambda _m: block, before)
        elif nav_links(before, f):
            skipped.append(f)
            continue
        else:
            after = before.rstrip() + "\n\n---\n\n" + block + "\n"
        if after != before:
            f.write_text(after, encoding="utf-8")
            changed.append(f)
    return changed, skipped


def orphan_pages(root: Path, files: list[Path]) -> list[Path]:
    """Markdown pages on disk that are not in the reading order, and so would be
    silently left out of the PDF and the navigation."""
    included = {f.resolve() for f in files}
    # guide.toml can name repository folders that hold no book pages
    # (exclude = ["drills", "attempts"]).
    excluded = set()
    cfg = root / "guide.toml"
    if cfg.is_file():
        import tomllib
        excluded = set(tomllib.loads(cfg.read_text(encoding="utf-8")).get("exclude", []))
    orphans = []
    for p in sorted(root.rglob("*.md")):
        rel_parts = p.relative_to(root).parts
        if any(part in SKIP_DIRS or part in excluded or part.startswith(".") or part == "tools"
               for part in rel_parts[:-1]):
            continue
        if p.name.lower() in NON_PAGE_FILES or p.resolve() in included:
            continue
        orphans.append(p)
    return orphans


def check_conventions(root: Path, files: list[Path]) -> list[str]:
    """Check a guide against the standard conventions (see SKILL.md):
    a Table of Contents in the root README, Previous | Next links at the bottom of
    every page pointing at the neighbouring pages in reading order, and a
    Glossary as the final page. Returns a list of problems (empty = compliant)."""
    problems: list[str] = []
    resolved = [f.resolve() for f in files]

    first = files[0]
    if first.name.lower() != "readme.md" or first.parent.resolve() != root:
        problems.append("the first page should be the root README.md")
    elif not (root / "SUMMARY.md").is_file() and not re.search(
            r"^#{1,3}\s+(table of )?contents\s*$",
            first.read_text(encoding="utf-8"), re.IGNORECASE | re.MULTILINE):
        problems.append("root README.md has no 'Table of Contents' heading "
                        "(and there is no SUMMARY.md)")

    last = files[-1]
    last_text = last.read_text(encoding="utf-8")
    if not (re.search(r"^#\s+glossary\b", last_text, re.IGNORECASE | re.MULTILINE)
            or "glossary" in last.relative_to(root).as_posix().lower()):
        problems.append(f"the last page should be the Glossary (found {last.relative_to(root)})")

    for i, f in enumerate(files):
        rel = f.relative_to(root)
        nav = nav_links(f.read_text(encoding="utf-8"), f)
        if i > 0:
            if "previous" not in nav:
                problems.append(f"{rel}: no 'Previous' link at the bottom")
            elif nav["previous"] != resolved[i - 1]:
                problems.append(f"{rel}: 'Previous' should point to {files[i - 1].relative_to(root)}")
        if i < len(files) - 1:
            if "next" not in nav:
                problems.append(f"{rel}: no 'Next' link at the bottom")
            elif nav["next"] != resolved[i + 1]:
                problems.append(f"{rel}: 'Next' should point to {files[i + 1].relative_to(root)}")

    titles = summary_titles(root)
    for i, f in enumerate(files):
        blocks = NAV_BLOCK_RE.findall(f.read_text(encoding="utf-8"))
        if blocks and any(b != nav_block(root, files, i, titles) for b in blocks):
            problems.append(f"{f.relative_to(root)}: nav block is out of date (run --nav)")

    for p in orphan_pages(root, files):
        problems.append(f"{p.relative_to(root)}: not in the reading order, so it is "
                        "left out of the PDF and the navigation")
    return problems


def attach_anchor_to_h1(content: str, slug: str, fallback_title: str) -> str:
    """Append `{#slug}` to the first H1 (skipping code fences), or prepend one."""
    lines = content.split("\n")
    in_fence, marker = False, ""
    for i, line in enumerate(lines):
        s = line.strip()
        if not in_fence and (s.startswith("```") or s.startswith("~~~")):
            in_fence, marker = True, s[:3]
            continue
        if in_fence:
            if s.startswith(marker):
                in_fence = False
            continue
        if re.match(r"^#\s+\S", line):
            clean = re.sub(r"\s*\{[^}]*\}\s*$", "", line)
            lines[i] = f"{clean} {{#{slug}}}"
            return "\n".join(lines)
    return f"# {fallback_title} {{#{slug}}}\n\n" + content


# Markers count only at the start of a line, so prose can mention them.
REPO_ONLY = re.compile(r"^[ \t]*<!--\s*repo-only\s*-->.*?^[ \t]*<!--\s*/repo-only\s*-->[ \t]*\n?",
                       re.S | re.M)
PDF_ONLY = re.compile(r"^[ \t]*<!--\s*pdf-only\s*\n?(.*?)-->", re.S | re.M)
PDF_PART = re.compile(r"<!--\s*pdf-part:\s*(.+?)\s*-->")
NAV_BLOCK = re.compile(r"(?:\n-{3,}\s*\n)?\s*<!--nav-->.*?<!--/nav-->\s*", re.S)

# Text that belongs to the repository, not the book. Checked after the
# repo-only blocks are removed, so wrapping a passage in them fixes it.
LEAK_PATTERNS = (
    (re.compile(r"\bcompanion (?:code|file|program|test)", re.I), "mentions the companion code"),
    # "this repository" and "the repo" mean the guide's own repo; "the repository"
    # alone is too common in prose (the repository pattern) to flag.
    (re.compile(r"\bthis (?:repo|repository)\b|\bthe repo\b", re.I), "mentions the repository"),
    (re.compile(r"(?<![\w/.-])\d\d-[a-z0-9-]+/(?!\S*\.md\b)"), "contains a repo path"),
    (re.compile(r"\]\((?!https?:|#|mailto:)[^)\s]+\.(?:js|mjs|cjs|ts|json|py|go|ya?ml|sh)\)"),
     "links to a file in the repo"),
)


def is_folder_intro(root: Path, rel: Path) -> bool:
    """A chapter folder's README, which becomes a Part. Single-page folders
    (quick reference, glossary) are plain chapters."""
    if len(rel.parts) != 2 or rel.name.lower() != "readme.md":
        return False
    return len(list((root / rel.parent).glob("*.md"))) > 1


def to_book(content: str) -> str:
    """Strip repository-only content and navigation; unwrap PDF-only content."""
    content = REPO_ONLY.sub("", content)
    content = NAV_BLOCK.sub("\n", content)
    content = PDF_ONLY.sub(lambda m: m.group(1).strip("\n") + "\n", content)
    return content.rstrip() + "\n"


def map_prose_lines(content: str, fn) -> str:
    """Apply fn to every line outside fenced code blocks."""
    out, in_fence, marker = [], False, ""
    for line in content.split("\n"):
        s = line.strip()
        if not in_fence and (s.startswith("```") or s.startswith("~~~")):
            in_fence, marker = True, s[:3]
            out.append(line)
            continue
        if in_fence:
            if s.startswith(marker):
                in_fence = False
            out.append(line)
            continue
        out.append(fn(line))
    return "\n".join(out)


def shift_headings(content: str, root: Path, rel: Path) -> str:
    """Folder READMEs keep their H1 (the chapter opener); their other headings
    and every other page's headings move down one level."""
    intro = is_folder_intro(root, rel)
    # A folder with a single page (quick reference, glossary) stands outside any
    # chapter; the theme must not number it as a section.
    standalone = len(rel.parts) == 2 and rel.name.lower() == "readme.md" and not intro
    seen_h1 = False

    def fn(line: str) -> str:
        nonlocal seen_h1
        m = re.match(r"^(#{1,5})(\s+\S.*)$", line)
        if m:
            level = len(m.group(1))
            if level == 1 and not seen_h1:
                seen_h1 = True
                if intro:
                    return line
                if standalone:
                    line = re.sub(r"\{#([^}]*)\}\s*$", r"{#\1 .standalone}", line)
            return "#" + line
        part = PDF_PART.fullmatch(line.strip())
        if part:
            return f"# {part.group(1)}"
        return line

    return map_prose_lines(content, fn)


def book_leaks(root: Path, files: list[Path]) -> list[str]:
    """Repo-specific text that would appear in the PDF."""
    problems = []
    for f in files:
        rel = f.relative_to(root)
        raw = f.read_text(encoding="utf-8")
        opens = len(re.findall(r"^[ \t]*<!--\s*repo-only\s*-->", raw, re.M))
        closes = len(re.findall(r"^[ \t]*<!--\s*/repo-only\s*-->", raw, re.M))
        if opens != closes:
            problems.append(f"{rel}: unbalanced <!--repo-only--> markers "
                            f"({opens} open, {closes} close)")
            continue
        for n, line in enumerate(to_book(raw).split("\n"), 1):
            for pattern, what in LEAK_PATTERNS:
                if pattern.search(line):
                    problems.append(f"{rel}: book text {what}: {line.strip()[:90]!r} "
                                    "(wrap it in <!--repo-only--> ... <!--/repo-only-->)")
    return problems



# ── Editorial checks (EDITORIAL.md) ─────────────────────────────────────────────
# Run for guides that have adopted the standard (they have a guide.toml).

BANNED_PROSE = (
    (re.compile(r"\blessons?\b", re.I), "say 'section' or 'chapter' ('lesson' is course language)"),
    (re.compile(r"\b(?:this|the) guide\b", re.I), "say 'this book'"),
    (re.compile(r"^\s*The takeaway:"), "put the takeaway in the figure's caption"),
    (re.compile(r"\bIn this (?:section|chapter|book),? (?:we|you)(?:'ll| will)\b", re.I),
     "scaffolding sentence: start with the substance"),
    (re.compile(r"\b(?:previous|next) (?:section|chapter)\b", re.I),
     "cross-reference by number ('section 3.2')"),
    (re.compile(r"\b(?:Let's dive in|Without further ado|Now that we've covered)\b", re.I),
     "filler"),
    (re.compile(r"^#{2,}\s+(?:Key Takeaways|Try It|Common Pitfalls)\s*$"),
     "retired heading: sections end with '## Summary'; exercises go at the chapter end"),
    (re.compile("[\U0001F300-\U0001FAFF☀-⛿✀-➿]"), "emoji"),
)
CALLOUT = re.compile(r"^>\s*\*\*([^*]+?):\*\*")
CALLOUT_LABELS = {"Note", "Tip", "Warning"}
FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w-]*)")
XREF = re.compile(r"\[(section|chapter)\s+(\d+)(?:\.(\d+))?\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", re.I)
CHAPTER_END_PAGES = {
    "technical": ("Exercises and Further Reading", ("Exercises", "Further Reading")),
    "general": ("Questions and Sources", ("Questions to Consider", "Sources and Further Reading")),
    # Technical guides with `problem_sets = true` (EDITORIAL.md, "Problem Sets").
    "problems": ("Problems and Further Reading", ("Problems", "Further Reading")),
    # Language-learning books, `language = "ja"` etc. (EDITORIAL.md, "Language-learning
    # books"): graded practice, with answers in a part of their own at the back.
    "language": ("Practice and Further Reading", ("Practice", "Further Reading")),
}
PRACTICE_HEAD = re.compile(r"^### (\d+)\.(\d+) (.+?)\s*$", re.M)
ANSWERS_DIR = "answers"
PROBLEM_HEAD = re.compile(r"^### (\d+)\.(\d+) (.+?)\s*$", re.M)
ANSWER_HEAD = re.compile(r"^## (\d+)\.(\d+) (.+?)\s*$", re.M)
PROBLEM_META = re.compile(r"^\*\*(Easy|Medium|Hard)\*\* · Target: \S")
ANSWER_DIRS = ("hints", "solutions")
MAX_CODE_LINE = 80


def split_prose(text: str):
    """Yield (line_number, line, in_code, fence_lang) for every line."""
    fence, lang = None, ""
    for n, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if m and fence is None:
            fence, lang = m.group(1), m.group(2).lower()
            yield n, line, True, lang
            continue
        if fence is not None:
            if line.strip().startswith(fence[:3]) and line.strip().strip(fence[0]) == "":
                yield n, line, True, lang
                fence, lang = None, ""
                continue
            yield n, line, True, lang
            continue
        yield n, line, False, ""


def structure_numbers(root: Path, files: list[Path]) -> dict[Path, tuple[str, str]]:
    """Map each chapter introduction to ('chapter', 'N') and each section page to
    ('section', 'N.k'), in reading order. SUMMARY.md is used when present, so
    references to chapters that aren't written yet still resolve."""
    numbers: dict[Path, tuple[str, str]] = {}
    summary = root / "SUMMARY.md"
    if summary.is_file():
        entries = re.findall(r"^\s*[-*]\s+\[([^\]]+)\]\(\s*([^)\s#]+\.md)\s*\)",
                             summary.read_text(encoding="utf-8"), re.M)
        pages = [(t, (root / p.removeprefix("./")).resolve()) for t, p in entries]
    else:
        pages = [(page_title(f, {}), f.resolve()) for f in files]
    chapter, k, chapter_dir = None, 0, None
    for title, path in pages:
        rel = path.relative_to(root.resolve())
        m = re.match(r"Chapter\s+(\d+)\s+—", title)
        if len(rel.parts) == 2 and rel.name.lower() == "readme.md":
            if not m and path.is_file():
                m = re.search(r"^#\s+Chapter\s+(\d+)\s+—", path.read_text(encoding="utf-8"), re.M)
            chapter, k, chapter_dir = (m.group(1), 0, rel.parent) if m else (None, 0, None)
            if chapter:
                numbers[path] = ("chapter", chapter)
        elif chapter and rel.parent == chapter_dir and not rel.name.startswith("99-"):
            k += 1
            numbers[path] = ("section", f"{chapter}.{k}")
    return numbers


def editorial_problems(root: Path, files: list[Path]) -> list[str]:
    guide = load_guide(root) if theme_files(root) else None
    if guide is None:
        return []
    profile = guide.get("cat_profile", "technical")
    numbers = structure_numbers(root, files)
    problems: list[str] = []
    chapter_dirs = {f.parent for f in files if numbers.get(f.resolve(), ("",))[0] == "chapter"}

    for f in files:
        rel = f.relative_to(root)
        book = to_book(f.read_text(encoding="utf-8"))
        lines = list(split_prose(book))
        is_section = numbers.get(f.resolve(), ("",))[0] == "section"

        for n, line, in_code, lang in lines:
            if in_code:
                # Output is copied verbatim, so only code is held to the limit.
                if (profile == "technical" and lang not in ("mermaid", "", "text", "output")
                        and not FENCE.match(line) and len(line) > MAX_CODE_LINE):
                    problems.append(f"{rel}:{n}: code line longer than {MAX_CODE_LINE} "
                                    f"characters ({len(line)})")
                continue
            prose = re.sub(r"`[^`]*`", "", line)            # inline code is exempt
            prose = re.sub(r"\]\([^)]*\)", "]", prose)       # so are link targets
            for pattern, why in BANNED_PROSE:
                if pattern.search(prose):
                    problems.append(f"{rel}:{n}: {why}: {line.strip()[:80]!r}")
            m = CALLOUT.match(line)
            if m and m.group(1) not in CALLOUT_LABELS:
                problems.append(f"{rel}:{n}: callout label {m.group(1)!r}: use Note, Tip or Warning")
            for x in XREF.finditer(line):
                kind, a, b, target = x.group(1).lower(), x.group(2), x.group(3), x.group(4)
                want = (kind, f"{a}.{b}" if b else a)
                got = numbers.get((f.parent / target).resolve())
                if got != want:
                    shown = f"{got[0]} {got[1]}" if got else "not a numbered chapter or section"
                    problems.append(f"{rel}:{n}: '{x.group(1)} {want[1]}' links to {target}, "
                                    f"which is {shown}")

        # Every figure has a caption line: *Figure: ...*
        closing = [n for n, line, in_code, lang in lines if in_code and lang == "mermaid"]
        text_lines = book.split("\n")
        mermaid_ends = []
        inside = False
        for n, line, in_code, lang in lines:
            if in_code and lang == "mermaid" and FENCE.match(line):
                if inside:
                    mermaid_ends.append(n)
                inside = not inside
        for end in mermaid_ends:
            following = next((l for l in text_lines[end:] if l.strip()), "")
            if not following.strip().startswith("*Figure:"):
                problems.append(f"{rel}:{end}: diagram without a caption "
                                "(add a line '*Figure: …*' after it)")

        # Sections end with a Summary of 3-6 bullets.
        if is_section:
            m = re.search(r"^## Summary\s*\n(.*?)(?=^#{1,2} |\Z)", book, re.S | re.M)
            if not m:
                problems.append(f"{rel}: section has no '## Summary'")
            else:
                bullets = len(re.findall(r"^[-*] ", m.group(1), re.M))
                if not 3 <= bullets <= 6:
                    problems.append(f"{rel}: Summary has {bullets} bullets (3-6)")

    # Every chapter ends with its chapter-end page.
    kind = ("problems" if guide.get("problem_sets")
            else "language" if guide.get("language") else profile)
    title, required = CHAPTER_END_PAGES[kind]
    if guide.get("problem_sets"):
        problems += problem_set_problems(root, files, chapter_dirs, numbers)
    if guide.get("language"):
        problems += practice_problems(root, files, chapter_dirs, numbers)
        problems += method_problems(root, files, numbers, guide["language"])
    for d in sorted(chapter_dirs):
        ends = [f for f in files if f.parent == d and f.name.startswith("99-")]
        if not ends:
            problems.append(f"{d.relative_to(root)}: no chapter-end page "
                            f"(99-….md titled '{title}')")
            continue
        text = ends[0].read_text(encoding="utf-8")
        # In a problem book, a chapter with no problems (an orientation chapter,
        # say) ends with its reading list alone.
        if guide.get("problem_sets") and re.search(r"^#\s+Further Reading\s*$", text, re.M):
            continue
        if not re.search(rf"^#\s+{re.escape(title)}\s*$", text, re.M):
            problems.append(f"{ends[0].relative_to(root)}: title should be '# {title}'")
        for h in required:
            if not re.search(rf"^##\s+{re.escape(h)}\s*$", text, re.M):
                problems.append(f"{ends[0].relative_to(root)}: missing '## {h}'")
    return problems


def problem_set_problems(root: Path, files: list[Path], chapter_dirs: set[Path],
                         numbers: dict[Path, tuple[str, str]]) -> list[str]:
    """Problems on each chapter-end page are numbered N.1, N.2 … and carry a
    difficulty and a target; each has a hint and a solution with the same number
    and title, and no hint or solution is left without its problem."""
    problems: list[str] = []
    answer_pages: dict[str, dict[str, Path]] = {kind: {} for kind in ANSWER_DIRS}
    for f in files:
        rel = f.relative_to(root)
        if len(rel.parts) == 2 and rel.parts[0] in ANSWER_DIRS and rel.name.lower() != "readme.md":
            m = re.search(r"^#\s+Chapter\s+(\d+)\s+—", f.read_text(encoding="utf-8"), re.M)
            if m:
                answer_pages[rel.parts[0]][m.group(1)] = f
            else:
                problems.append(f"{rel}: title should be '# Chapter N — Title'")

    chapters: set[str] = set()
    for d in sorted(chapter_dirs):
        intro = (d / "README.md").resolve()
        chapter = numbers.get(intro, ("", ""))[1]
        ends = [f for f in files if f.parent == d and f.name.startswith("99-")]
        if not chapter or not ends:
            continue
        end = ends[0]
        text = to_book(end.read_text(encoding="utf-8"))
        if re.search(r"^#\s+Further Reading\s*$", text, re.M):
            continue
        chapters.add(chapter)
        heads = list(PROBLEM_HEAD.finditer(text))
        rel = end.relative_to(root)
        if not heads:
            problems.append(f"{rel}: no problems ('### {chapter}.1 Title' under '## Problems')")
        titles: dict[str, str] = {}
        for k, h in enumerate(heads, 1):
            number = f"{h.group(1)}.{h.group(2)}"
            if h.group(1) != chapter or int(h.group(2)) != k:
                problems.append(f"{rel}: problem {number} should be numbered {chapter}.{k}")
            titles[number] = h.group(3)
            following = next((ln for ln in text[h.end():].split("\n") if ln.strip()), "")
            if not PROBLEM_META.match(following):
                problems.append(f"{rel}: problem {number} needs '**Easy|Medium|Hard** · "
                                "Target: …' on the line after its heading")
        for kind in ANSWER_DIRS:
            page = answer_pages[kind].get(chapter)
            if page is None:
                problems.append(f"{rel}: no {kind} page for chapter {chapter} "
                                f"({kind}/NN-….md titled '# Chapter {chapter} — …')")
                continue
            found = {f"{m.group(1)}.{m.group(2)}": m.group(3)
                     for m in ANSWER_HEAD.finditer(page.read_text(encoding="utf-8"))}
            prel = page.relative_to(root)
            for number, title in titles.items():
                if number not in found:
                    problems.append(f"{prel}: no {kind[:-1]} for problem {number}")
                elif found[number] != title:
                    problems.append(f"{prel}: {kind[:-1]} {number} is titled {found[number]!r}, "
                                    f"the problem {title!r}")
            for number in found.keys() - titles.keys():
                problems.append(f"{prel}: {kind[:-1]} {number} has no problem")
    for kind in ANSWER_DIRS:
        for chapter, page in answer_pages[kind].items():
            if chapter not in chapters:
                problems.append(f"{page.relative_to(root)}: chapter {chapter} has no problems page")
    return problems


# Language-learning books teach the best-supported way to learn (EDITORIAL.md,
# "Method"): chapter 1 is "How to Learn <Language>" with the evidence in "Study and
# Immersion: The Middle Path", and research is never invoked without its source.
LANGUAGE_NAMES = {"ja": "Japanese", "zh": "Chinese", "es": "Spanish", "fr": "French"}
METHOD_SECTION = "Study and Immersion: The Middle Path"
UNSOURCED_RESEARCH = re.compile(
    r"\b(?:stud(?:y|ies)|research(?:ers)?|scientists|experiments?|evidence)\s+"
    r"(?:(?:has|have|had|consistently|clearly|also)\s+)?"
    r"(?:show(?:s|ed|n)?|suggest(?:s|ed)?|prove[sd]?|found|finds|confirm(?:s|ed)?|indicate[sd]?)\b",
    re.I)
CITED_YEAR = re.compile(r"\b(?:1[89]|20)\d{2}\b")


def method_problems(root: Path, files: list[Path], numbers: dict[Path, tuple[str, str]],
                    lang: str) -> list[str]:
    problems: list[str] = []
    name = LANGUAGE_NAMES.get(lang, lang)
    first = next((f for f, (kind, n) in numbers.items() if (kind, n) == ("chapter", "1")), None)
    if first is None or not first.is_file():
        problems.append(f"chapter 1 should be '# Chapter 1 — How to Learn {name}'")
    else:
        rel = first.relative_to(root.resolve())
        text = to_book(first.read_text(encoding="utf-8"))
        if not re.search(rf"^#\s+Chapter 1 — How to Learn {re.escape(name)}\s*$", text, re.M):
            problems.append(f"{rel}: chapter 1 should be '# Chapter 1 — How to Learn {name}'")
        sections = [f for f, (kind, n) in numbers.items()
                    if kind == "section" and n.startswith("1.") and f.is_file()]
        if not any(re.search(rf"^#\s+{re.escape(METHOD_SECTION)}\s*$",
                             f.read_text(encoding="utf-8"), re.M) for f in sections):
            problems.append(f"{rel.parent}: chapter 1 has no section '# {METHOD_SECTION}'")
    for f in files:
        rel = f.relative_to(root)
        book = to_book(f.read_text(encoding="utf-8"))
        for block in re.finditer(r"(?:[^\n]*\S[^\n]*(?:\n|$))+", book):
            para = block.group(0)
            if para.lstrip().startswith(("```", "|", "#")):
                continue
            m = UNSOURCED_RESEARCH.search(para)
            if m and not CITED_YEAR.search(para):
                n = book.count("\n", 0, block.start() + m.start()) + 1
                problems.append(f"{rel}:{n}: research claim without its source "
                                f"(name the study and year): {m.group(0)!r}")
    return problems


def practice_problems(root: Path, files: list[Path], chapter_dirs: set[Path],
                      numbers: dict[Path, tuple[str, str]]) -> list[str]:
    """In a language-learning book, each chapter's practice is grouped by section
    (`### N.k Section Title`), and answers/NN-….md (`# Chapter N — Title`) has a
    matching `## N.k Section Title` for every group, and none without one."""
    problems: list[str] = []
    answer_pages: dict[str, Path] = {}
    for f in files:
        rel = f.relative_to(root)
        if len(rel.parts) == 2 and rel.parts[0] == ANSWERS_DIR and rel.name.lower() != "readme.md":
            m = re.search(r"^#\s+Chapter\s+(\d+)\s+—", f.read_text(encoding="utf-8"), re.M)
            if m:
                answer_pages[m.group(1)] = f
            else:
                problems.append(f"{rel}: title should be '# Chapter N — Title'")
    chapters: set[str] = set()
    for d in sorted(chapter_dirs):
        chapter = numbers.get((d / "README.md").resolve(), ("", ""))[1]
        ends = [f for f in files if f.parent == d and f.name.startswith("99-")]
        if not chapter or not ends:
            continue
        rel = ends[0].relative_to(root)
        text = to_book(ends[0].read_text(encoding="utf-8"))
        groups = {f"{m.group(1)}.{m.group(2)}": m.group(3) for m in PRACTICE_HEAD.finditer(text)}
        if not groups:
            problems.append(f"{rel}: no practice ('### {chapter}.1 Section Title' under '## Practice')")
            continue
        chapters.add(chapter)
        for number in groups:
            if number.split(".")[0] != chapter:
                problems.append(f"{rel}: practice group {number} is not in chapter {chapter}")
        page = answer_pages.get(chapter)
        if page is None:
            problems.append(f"{rel}: no answers page for chapter {chapter} "
                            f"({ANSWERS_DIR}/NN-….md titled '# Chapter {chapter} — …')")
            continue
        found = {f"{m.group(1)}.{m.group(2)}": m.group(3)
                 for m in ANSWER_HEAD.finditer(page.read_text(encoding="utf-8"))}
        prel = page.relative_to(root)
        for number, title in groups.items():
            if number not in found:
                problems.append(f"{prel}: no answers for practice {number}")
            elif found[number] != title:
                problems.append(f"{prel}: answers {number} are titled {found[number]!r}, "
                                f"the practice {title!r}")
        for number in found.keys() - groups.keys():
            problems.append(f"{prel}: answers {number} have no practice group")
    for chapter, page in answer_pages.items():
        if chapter not in chapters:
            problems.append(f"{page.relative_to(root)}: chapter {chapter} has no practice page")
    return problems


def build_combined(root: Path, build_dir: Path) -> tuple[Path, int]:
    files = collect_files(root)
    if not files:
        sys.exit("error: no .md files found to build")
    path_to_slug = {f.resolve(): make_slug(f.relative_to(root)) for f in files}

    pieces, missing = [], []
    for f in files:
        rel = f.relative_to(root)
        content = to_book(f.read_text(encoding="utf-8"))
        content = rewrite_links(content, f, path_to_slug)
        content = rewrite_images(content, f, missing)
        content = attach_anchor_to_h1(content, path_to_slug[f.resolve()], rel.as_posix())
        content = shift_headings(content, root, rel)
        pieces.append(content.rstrip() + "\n")

    if missing:
        print("ERROR: images referenced but not found (they would be silently "
              "dropped from the PDF):", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(3)

    build_dir.mkdir(parents=True, exist_ok=True)
    combined = build_dir / "combined.md"
    combined.write_text("\n\n".join(pieces), encoding="utf-8")
    return combined, len(files)


def derive_title(root: Path, files_first: Path | None) -> str:
    if files_first and files_first.name.lower().startswith("readme"):
        for line in files_first.read_text(encoding="utf-8").splitlines():
            m = re.match(r"#\s+(.+)", line)
            if m:
                return re.sub(r"\s*\{#.*\}\s*$", "", m.group(1)).strip()
    return root.name


# Guides are anonymous: there is deliberately no default author. The git user name
# (a GitHub handle) must never end up on the cover or in the PDF metadata. An author
# appears only when --author is passed explicitly.


def pick_engine() -> str | None:
    return next((e for e in PDF_ENGINES if shutil.which(e)), None)


def check_prereqs() -> str:
    missing = []
    if not shutil.which("pandoc"):
        missing.append("pandoc")
    engine = pick_engine()
    if engine is None:
        missing.append("a LaTeX engine (xelatex)")
    if missing:
        print("ERROR: missing required tool(s): " + ", ".join(missing), file=sys.stderr)
        print("Install on macOS:  brew install pandoc && brew install --cask mactex-no-gui",
              file=sys.stderr)
        print("Install on Debian: sudo apt-get install pandoc texlive-xetex", file=sys.stderr)
        sys.exit(2)
    return engine


THEME_DIR = Path("tools") / "pdf"
# The skill's copy of the standard. When this script runs from inside a guide
# (tools/build_guide_pdf.py) the folder doesn't exist and the guide's copy is used.
SKILL_THEME = Path(__file__).resolve().parent / "theme"
THEME_FILES = ("EDITORIAL.md", "STYLE.md", "categories.json", "packages.tex", "theme.tex",
               "guide.lua", "highlight.theme", "mermaid-config.json")
# Languages a language-learning book can teach (guide.toml: language = "ja").
# A language with its own script ships that script's fonts; only a guide that
# declares it gets them, so other guides stay light. Each entry is (font folder
# in the theme, serif family, sans family), or None for a Latin-script language,
# which the body fonts already cover.
LANGUAGE_FONTS = {
    "ja": ("fonts-ja", "NotoSerifJP", "NotoSansJP"),
    "zh": ("fonts-zh", "NotoSerifSC", "NotoSansSC"),
    "es": None,
    "fr": None,
}


def guide_language(root: Path) -> str | None:
    """The language a language-learning book teaches (guide.toml `language`)."""
    import tomllib
    cfg = root / "guide.toml"
    if not cfg.is_file():
        return None
    lang = tomllib.loads(cfg.read_text(encoding="utf-8")).get("language")
    if lang is not None and lang not in LANGUAGE_FONTS:
        sys.exit(f"error: guide.toml language {lang!r} is not one of: {', '.join(LANGUAGE_FONTS)}")
    return lang


def theme_pairs(root: Path) -> list[tuple[Path, Path]]:
    """(skill file, guide copy) for every file of the standard the guide needs."""
    local = root / THEME_DIR
    pairs = [(SKILL_THEME / n, local / n) for n in THEME_FILES]
    pairs += [(f, local / "fonts" / f.name) for f in sorted((SKILL_THEME / "fonts").glob("*"))]
    lang = guide_language(root)
    if lang and LANGUAGE_FONTS[lang]:
        folder = LANGUAGE_FONTS[lang][0]
        pairs += [(f, local / folder / f.name) for f in sorted((SKILL_THEME / folder).glob("*"))]
    pairs.append((Path(__file__).resolve(), root / "tools" / "build_guide_pdf.py"))
    return pairs


def theme_files(root: Path) -> Path | None:
    """The guide's PDF theme: its own copy in tools/pdf/, else the skill's copy
    for a guide that has a guide.toml. None means an unthemed (legacy) build."""
    d = root / THEME_DIR
    if (d / "theme.tex").is_file():
        return d
    if (root / "guide.toml").is_file() and (SKILL_THEME / "theme.tex").is_file():
        return SKILL_THEME
    return None


def file_digest(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def theme_drift(root: Path) -> list[str]:
    """Files in the guide's copy of the standard that differ from the skill's."""
    local = root / THEME_DIR
    if not (SKILL_THEME / "theme.tex").is_file() or not (local / "theme.tex").is_file():
        return []
    pairs = theme_pairs(root)
    return [str(dst.relative_to(root)) for src, dst in pairs
            if not dst.is_file() or file_digest(src) != file_digest(dst)]


def sync_theme(root: Path) -> list[str]:
    """Install or update the guide's copy of the standard from the skill."""
    if not (SKILL_THEME / "theme.tex").is_file():
        sys.exit("error: --sync runs from the skill (~/.claude/skills/build-guide-pdf/)")
    changed = []
    for src, dst in theme_pairs(root):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or file_digest(src) != file_digest(dst):
            shutil.copyfile(src, dst)
            changed.append(str(dst.relative_to(root)))
    return changed


def guide_version(root: Path, explicit: str | None) -> str:
    """The edition shown on the cover: --edition, else the tag being released,
    else the latest git tag, else 'draft'."""
    if explicit:
        return explicit
    ref = os.environ.get("GITHUB_REF_NAME", "")
    if ref.startswith("v"):
        return ref
    try:
        tag = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=root,
                             capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        tag = ""
    return tag or "draft"


def load_guide(root: Path) -> dict | None:
    """The guide's identity (guide.toml) merged with its category's profile and
    colours (categories.json). None if the guide hasn't adopted the standard."""
    import json
    import tomllib
    cfg = root / "guide.toml"
    if not cfg.is_file():
        return None
    guide = tomllib.loads(cfg.read_text(encoding="utf-8"))
    theme = theme_files(root)
    cats = json.loads((theme / "categories.json").read_text(encoding="utf-8"))["categories"]
    cat = guide.get("category", "")
    if cat not in cats:
        sys.exit(f"error: guide.toml category {cat!r} is not one of: {', '.join(cats)}")
    return {**guide, **{f"cat_{k}": v for k, v in cats[cat].items()}}


def to_latex(markdown: str) -> str:
    """Convert a short Markdown string (title, blurb) to LaTeX with pandoc."""
    out = subprocess.run(["pandoc", "-f", "markdown", "-t", "latex", "--wrap=none"],
                         input=markdown.strip(), capture_output=True, text=True, check=True)
    return out.stdout.strip().replace("\n\n", "\\par\n")


def theme_args(root: Path, theme: Path, build_dir: Path, edition: str) -> list[str]:
    """pandoc arguments that apply the guide's theme, and the generated brand.tex
    that carries the guide's identity into it."""
    import datetime
    guide = load_guide(root)
    if guide is None:
        sys.exit("error: themed builds need guide.toml at the guide root (see tools/pdf/STYLE.md)")
    today = datetime.date.today()
    version = edition.removeprefix("v")
    line = guide.get("edition", "First Edition")
    line += " · Draft" if edition == "draft" else f" · Version {version}"
    line += f" · {today:%B %Y}"

    def color(name: str, value: str) -> str:
        return f"\\definecolor{{{name}}}{{HTML}}{{{value.lstrip('#')}}}\n"

    def cmd(name: str, value: str) -> str:
        return f"\\newcommand{{\\{name}}}{{{value}}}\n"

    brand = (
        "% Generated by build_guide_pdf.py from guide.toml and categories.json.\n"
        + cmd("GuideFontPath", (theme / "fonts").resolve().as_posix() + "/")
        + cmd("GuideTitle", to_latex(guide["title"]))
        + cmd("GuideSubtitle", to_latex(guide.get("subtitle", "")))
        + cmd("GuideCategory", guide["category"])
        + cmd("GuideCoverage", to_latex(guide.get("coverage", "")))
        + cmd("GuideEditionLine", line)
        + cmd("GuideYear", f"{today:%Y}")
        + cmd("GuideCopyright", to_latex(guide.get(
            "copyright", f"Copyright © {today:%Y}. All rights reserved.")))
        + cmd("GuideBuildDate", f"{today:%-d %B %Y}")
        + cmd("GuideMotifName", guide.get("motif", "dots"))
        + cmd("GuideTrademarks", to_latex(guide.get("trademarks", "")))
        + cmd("GuideBlurb", to_latex(guide.get("blurb", "")))
        + color("Accent", guide["cat_accent"])
        + color("AccentBright", guide["cat_bright"])
        + color("AccentDark", guide["cat_dark"])
        + color("AccentTint", guide["cat_tint"])
    )
    lang = guide_language(root)
    if lang and LANGUAGE_FONTS[lang]:
        folder, serif, sans = LANGUAGE_FONTS[lang]
        brand += (cmd("GuideCJKFontPath", (theme / folder).resolve().as_posix() + "/")
                  + cmd("GuideCJKSerif", serif) + cmd("GuideCJKSans", sans))
    brand_tex = build_dir / "brand.tex"
    brand_tex.write_text(brand, encoding="utf-8")
    args = []
    for f in (theme / "packages.tex", brand_tex, theme / "theme.tex"):
        args += ["--include-in-header", str(f.resolve())]
    args += ["-V", "classoption=table", "-V", "fontsize=10pt", "-V", "colorlinks=true",
             "-V", "linkcolor=AccentDark", "-V", "urlcolor=AccentDark",
             "-V", "toccolor=Ink", "-V", "filecolor=AccentDark",
             "--pdf-engine-opt=-shell-restricted"]
    return args


def mermaid_env(root: Path, theme: Path | None, build_dir: Path) -> dict[str, str]:
    """Render diagrams as vector PDFs in the theme's colours. Diagrams use a
    system sans-serif rather than the theme's web font: Mermaid measures labels
    before a web font loads, which clips the text."""
    env = dict(os.environ)
    if theme is None:
        return env
    env.setdefault("MERMAID_FILTER_FORMAT", "pdf")
    env.setdefault("MERMAID_FILTER_BACKGROUND", "transparent")
    template = theme / "mermaid-config.json"
    guide = load_guide(root)
    if template.is_file() and guide:
        config = template.read_text(encoding="utf-8")
        for key in ("accent", "dark", "tint"):
            config = config.replace("{" + key + "}", guide[f"cat_{key}"])
        out = build_dir / "mermaid-config.json"
        out.write_text(config, encoding="utf-8")
        env.setdefault("MERMAID_FILTER_MERMAID_CONFIG", str(out.resolve()))
    return env


def run_pandoc(combined_md: Path, pdf_out: Path, title: str, author: str | None,
               engine: str, root: Path | None = None, edition: str | None = None) -> None:
    root = root or Path.cwd()
    theme = theme_files(root)
    build_dir = combined_md.parent
    themed = theme is not None and engine == "xelatex"
    cmd = [
        "pandoc", str(combined_md), "-o", str(pdf_out),
        f"--pdf-engine={engine}",
        "--from", "markdown+task_lists+emoji+autolink_bare_uris-raw_tex",
        "--top-level-division=part",
        "--toc", "--toc-depth=2",
        "-V", "documentclass=report",
        "--metadata", f"title={title}",
    ]
    if author:
        cmd += ["--metadata", f"author={author}"]
    if themed:
        # The theme sets the page, fonts, colours and every element's style.
        flag = highlight_flag().split("=")[0]
        cmd += [f"{flag}={(theme / 'highlight.theme').resolve()}"]
        cmd += theme_args(root, theme, build_dir, guide_version(root, edition))
    else:
        cmd += [highlight_flag(), "-V", "geometry:margin=1in", "-V", "colorlinks=true",
                "-V", "linkcolor=blue", "-V", "urlcolor=blue", "-V", "toccolor=blue"]
        if engine in UNICODE_ENGINES:
            # DejaVu has wide glyph coverage (but no color emoji; see the
            # skill's caveats).
            cmd += ["-V", "mainfont=DejaVu Sans", "-V", "monofont=DejaVu Sans Mono"]
    # DejaVu has no CJK glyphs, so text such as "Hello, 世界" would print blank.
    # With xelatex, pandoc's template loads xeCJK when CJKmainfont is set.
    # A language-learning book loads its script's own fonts in the theme.
    language_fonts = themed and bool(LANGUAGE_FONTS.get(guide_language(root) or ""))
    cjk_font = find_cjk_font() if engine == "xelatex" and not language_fonts else None
    if cjk_font:
        cmd += ["-V", f"CJKmainfont={cjk_font}", "-V", f"CJKmonofont={cjk_font}"]
        # xeCJK treats curly quotes, dashes and ellipses as full-width CJK
        # punctuation ("Let’ s"); keep them with the surrounding Western text.
        cmd += ["-V", "header-includes=\\xeCJKDeclareCharClass{Default}"
                      '{"00B7, "2013, "2014, "2018, "2019, "201C, "201D, "2026}']
        print(f"CJK font found: {cjk_font}")
    # Render ```mermaid blocks to images if mermaid-filter is installed
    # (npm install -g mermaid-filter); otherwise they render as code listings.
    # Filters run in order: mermaid-filter first (diagrams become images), then
    # the theme's Lua filter.
    filters = []
    use_mermaid = bool(shutil.which("mermaid-filter"))
    if use_mermaid:
        filters += ["--filter", "mermaid-filter"]
        print("mermaid-filter found: diagrams will be rendered")
    if themed and (theme / "guide.lua").is_file():
        filters += ["--lua-filter", str((theme / "guide.lua").resolve())]
    cmd[1:1] = filters
    env = mermaid_env(root, theme if themed else None, build_dir)
    # The Lua filter needs the book's language to recognize example sentences.
    env = {**(env or os.environ), "GUIDE_LANGUAGE": guide_language(root) or ""}
    if themed:
        # Render LaTeX with pandoc, then compile it ourselves in build/. pandoc's
        # own PDF step compiles with -output-directory, where makeindex can't
        # find the index file; compiling in place keeps the index, and three
        # passes settle the contents, the index and the cover overlays.
        tex = build_dir / (pdf_out.stem + ".tex")
        cmd[cmd.index("-o") + 1] = str(tex)
        cmd.insert(cmd.index("-o"), "--standalone")
    print("running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError:
        # mermaid-filter drives a headless browser that intermittently fails on
        # its first launch; one retry clears it. Anything else fails for real.
        if not use_mermaid:
            raise
        print("pandoc failed with mermaid-filter; retrying once", file=sys.stderr)
        subprocess.run(cmd, check=True, env=env)
    finally:
        err = Path("mermaid-filter.err")
        if err.is_file() and err.stat().st_size == 0:
            err.unlink()
    if themed:
        compile_latex(tex, pdf_out, engine)


def compile_latex(tex: Path, pdf_out: Path, engine: str, passes: int = 3) -> None:
    """Compile a standalone .tex file in its own directory, then copy the PDF out."""
    log = tex.with_suffix(".log")
    for n in range(1, passes + 2):
        result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                                 "-shell-restricted", tex.name],
                                cwd=tex.parent, capture_output=True, text=True)
        if result.returncode != 0:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []
            first = next((i for i, l in enumerate(lines) if l.startswith("!")), None)
            detail = "\n".join(lines[first:first + 12]) if first is not None else result.stdout[-2000:]
            sys.exit(f"LaTeX failed on pass {n} (full log: {log}):\n{detail}")
        needs_rerun = "Rerun" in log.read_text(encoding="utf-8", errors="replace")
        if n >= passes and not needs_rerun:
            break
    shutil.copyfile(tex.with_suffix(".pdf"), pdf_out)


CJK_FONTS = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Hiragino Sans GB", "PingFang SC")


def find_cjk_font() -> str | None:
    """Return an installed CJK font, if both xeCJK and fontconfig can find one."""
    if not (shutil.which("kpsewhich") and shutil.which("fc-list")):
        return None
    has_xecjk = subprocess.run(["kpsewhich", "xeCJK.sty"], capture_output=True,
                               text=True).stdout.strip()
    if not has_xecjk:
        return None
    families = subprocess.run(["fc-list", ":lang=zh", "family"], capture_output=True,
                              text=True).stdout
    installed = {name.strip() for line in families.splitlines() for name in line.split(",")}
    return next((f for f in CJK_FONTS if f in installed), None)


def highlight_flag() -> str:
    """pandoc 3.8+ renamed --highlight-style to --syntax-highlighting and warns
    on the old name. Pick whichever this pandoc understands."""
    try:
        help_text = subprocess.run(["pandoc", "--help"], capture_output=True,
                                   text=True, check=False).stdout
    except OSError:
        help_text = ""
    if "--syntax-highlighting" in help_text:
        return "--syntax-highlighting=tango"
    return "--highlight-style=tango"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a single PDF from a Markdown guide.")
    ap.add_argument("--root", default=".", help="guide repo root (default: current dir)")
    ap.add_argument("--title", help="PDF title (default: root README's H1, else dir name)")
    ap.add_argument("--author", help="PDF author (default: none — guides are anonymous)")
    ap.add_argument("--output", help="output PDF path (default: <root-name>.pdf in root)")
    ap.add_argument("--edition", help="edition shown on the cover, e.g. v1.0.0 "
                                      "(default: the release tag, else the latest git tag)")
    ap.add_argument("--check", action="store_true",
                    help="only check the guide against the conventions; don't build")
    ap.add_argument("--strict", action="store_true",
                    help="refuse to build if the guide breaks any convention")
    ap.add_argument("--sync", action="store_true",
                    help="install or update the guide's copy of the house standard and "
                         "theme (tools/pdf/) from the skill, then check the guide")
    ap.add_argument("--nav", action="store_true",
                    help="regenerate every page's Previous | Next navigation from the "
                         "reading order, then check the guide; don't build")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"error: --root {root} is not a directory")

    if args.sync:
        changed = sync_theme(root)
        print(f"Sync: {len(changed)} file(s) updated from {SKILL_THEME}")
        for c in changed:
            print(f"  - {c}")
        if not (root / "guide.toml").is_file():
            print("note: add a guide.toml (see the skill's SKILL.md) to adopt the standard",
                  file=sys.stderr)

    if args.nav:
        files = collect_files(root)
        changed, skipped = write_nav(root, files)
        print(f"Navigation: {len(changed)} page(s) updated, {len(files)} pages in reading order")
        if skipped:
            print("Skipped (hand-written footer, no <!--nav--> markers). Delete the old "
                  "footer or wrap it in <!--nav--> ... <!--/nav-->, then re-run --nav:",
                  file=sys.stderr)
            for f in skipped:
                print(f"  - {f.relative_to(root)}", file=sys.stderr)

    problems = check_conventions(root, collect_files(root))
    problems += book_leaks(root, collect_files(root))
    problems += editorial_problems(root, collect_files(root))
    if problems:
        print(f"Convention check: {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
    else:
        print("Convention check: OK")
    drift = theme_drift(root)
    if drift:
        print(f"note: {len(drift)} file(s) of the house standard differ from the skill's copy; "
              "run the skill's build_guide_pdf.py --sync to update:", file=sys.stderr)
        for d in drift[:10]:
            print(f"  - {d}", file=sys.stderr)
    if args.check or args.nav or args.sync:
        sys.exit(1 if problems else 0)
    if problems and args.strict:
        sys.exit("refusing to build with --strict; fix the problems above")

    engine = check_prereqs()

    build_dir = root / "build"
    combined_md, n = build_combined(root, build_dir)
    print(f"combined {n} files -> {combined_md}")

    files = collect_files(root)
    title = args.title or derive_title(root, files[0] if files else None)
    author = args.author  # anonymous unless explicitly given
    pdf_out = Path(args.output).resolve() if args.output else root / f"{root.name}.pdf"

    run_pandoc(combined_md, pdf_out, title, author, engine, root=root, edition=args.edition)
    print(f"wrote {pdf_out}")


if __name__ == "__main__":
    main()
