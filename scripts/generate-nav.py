#!/usr/bin/env python3
"""
generate-nav.py — Add uniform "Previous | Home | Next" navigation to every page
of The Japanese Guide.

The reading order is taken from the README (Foundations -> Politeness -> Culture
-> Practical -> History -> Music -> Tracks -> JLPT). The order lives in ORDER
below and is the single source of truth; it is also written out to
scripts/pages.txt so build-pdf.sh assembles the PDF in the exact same sequence.

The script is idempotent: each nav block is wrapped in
<!-- nav-footer:start --> / <!-- nav-footer:end --> markers, so re-running
replaces the existing block instead of stacking duplicates.

Usage:
    python3 scripts/generate-nav.py
"""

import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (path relative to repo root, short nav label) in canonical reading order.
ORDER = [
    ("README.md", "Home"),
    ("foundations/01-hiragana.md", "Hiragana"),
    ("foundations/02-katakana.md", "Katakana"),
    ("foundations/03-kanji.md", "Kanji"),
    ("foundations/04-grammar-basics.md", "Grammar Basics"),
    ("foundations/05-vocabulary-core.md", "Core Vocabulary"),
    ("foundations/06-phrases-and-idioms.md", "Phrases & Idioms"),
    ("foundations/07-spoken-vs-written.md", "Spoken vs. Written"),
    ("foundations/08-internet-and-slang.md", "Internet & Slang"),
    ("politeness/01-levels-overview.md", "Politeness Levels"),
    ("politeness/02-casual-japanese.md", "Casual Japanese"),
    ("politeness/03-polite-japanese.md", "Polite Japanese"),
    ("politeness/04-honorific-japanese.md", "Honorific Japanese"),
    ("culture/01-culture-and-norms.md", "Culture & Norms"),
    ("culture/02-food.md", "Food"),
    ("culture/03-matsuri.md", "Matsuri"),
    ("culture/04-pop-culture.md", "Pop Culture"),
    ("culture/05-dialects.md", "Dialects"),
    ("culture/06-seasons-and-nature.md", "Seasons & Nature"),
    ("culture/07-traditional-arts.md", "Traditional Arts"),
    ("culture/08-baseball-and-sumo.md", "Baseball & Sumo"),
    ("practical/trains-and-transit.md", "Trains & Transit"),
    ("practical/cities-and-regions.md", "Cities & Regions"),
    ("practical/shopping-and-money.md", "Shopping & Money"),
    ("practical/emergencies.md", "Emergencies"),
    ("history/overview.md", "Historical Overview"),
    ("history/samurai-and-bushido.md", "Samurai & Bushido"),
    ("history/postwar-japan.md", "Postwar Japan"),
    ("history/language-evolution.md", "Language Evolution"),
    ("music/j-pop.md", "J-Pop"),
    ("music/traditional-music.md", "Traditional Music"),
    ("tracks/anime-lover.md", "Anime Lover"),
    ("tracks/manga-reader.md", "Manga Reader"),
    ("tracks/business-japanese.md", "Business Japanese"),
    ("tracks/news-japanese.md", "News Japanese"),
    ("tracks/jlpt/overview.md", "JLPT Overview"),
    ("tracks/jlpt/n5.md", "JLPT N5"),
    ("tracks/jlpt/n4.md", "JLPT N4"),
    ("tracks/jlpt/n3.md", "JLPT N3"),
    ("tracks/jlpt/n2.md", "JLPT N2"),
    ("tracks/jlpt/n1.md", "JLPT N1"),
]

START = "<!-- nav-footer:start -->"
END = "<!-- nav-footer:end -->"


def rel_link(from_path, to_path):
    """Relative markdown link target from one page's directory to another page."""
    from_dir = os.path.dirname(os.path.join(REPO_ROOT, from_path))
    target = os.path.join(REPO_ROOT, to_path)
    return os.path.relpath(target, from_dir)


def strip_existing_nav(text):
    """Remove a previously generated nav block (and trailing whitespace) if present."""
    idx = text.find(START)
    if idx == -1:
        return text.rstrip() + "\n"
    return text[:idx].rstrip() + "\n"


def build_nav(index):
    path, _ = ORDER[index]
    parts = []

    if index > 0:
        prev_path, prev_label = ORDER[index - 1]
        parts.append(f"[← {prev_label}]({rel_link(path, prev_path)})")

    # Home link on every page except the README itself, and except the first
    # content page whose "Previous" link already points at the README.
    prev_is_home = index > 0 and ORDER[index - 1][0] == "README.md"
    if path != "README.md" and not prev_is_home:
        parts.append(f"[🏠 Home]({rel_link(path, 'README.md')})")

    if index < len(ORDER) - 1:
        next_path, next_label = ORDER[index + 1]
        label = "Begin" if path == "README.md" else next_label
        parts.append(f"[{label} →]({rel_link(path, next_path)})")

    nav_line = " · ".join(parts)
    return f"{START}\n\n---\n\n{nav_line}\n\n{END}\n"


def main():
    for i, (path, _) in enumerate(ORDER):
        full = os.path.join(REPO_ROOT, path)
        with open(full, "r", encoding="utf-8") as fh:
            original = fh.read()

        body = strip_existing_nav(original)
        new = body + "\n" + build_nav(i)

        if new != original:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(new)
            print(f"nav updated: {path}")
        else:
            print(f"nav unchanged: {path}")

    manifest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages.txt")
    with open(manifest, "w", encoding="utf-8") as fh:
        for path, _ in ORDER:
            fh.write(path + "\n")
    print(f"\nwrote manifest: {os.path.relpath(manifest, REPO_ROOT)} ({len(ORDER)} pages)")


if __name__ == "__main__":
    main()
