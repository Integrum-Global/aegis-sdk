"""Render the shipped handbook as one self-contained HTML file and one PDF.

WHY THIS EXISTS
---------------
The handbook ships as Markdown because Markdown is what the reader can diff,
grep and amend. That is the right source form and the wrong reading form for
two audiences this SDK actually has: someone reviewing the governance model end
to end, and someone who has to hand a bound document to a person who will never
open a terminal.

So this module produces the reading forms — and it **ships with the book**, for
the same reason :mod:`aegis_sdk.handbook.check` does. A PDF built somewhere else
and mailed over is a claim about a tree the reader cannot see; a PDF the reader
regenerates from the handbook in their own clone is the handbook. Both commands
are on the same footing::

    python -m aegis_sdk.handbook.check            # are the claims still anchored?
    python -m aegis_sdk.handbook.render --all -o build/   # give me the book

TWO DOCUMENTS, ONE RENDERER
---------------------------
The whole handbook is the default. ``--parts 08,09,10`` renders an EXTRACT of
the named parts instead — the same pipeline, a narrower running order, and a
cover that says so rather than claiming to be the book. It exists because a
reader is often asking a narrower question than "give me everything", and the
honest answer to that is a shorter document rather than a longer index.

Under ``--all`` an extract is named for its selection —
``handbook-parts-08-09-10.pdf`` — and never ``handbook.pdf``. Sharing the
complete book's filename would let one ``--all --parts`` run replace the whole
book in a build directory with three parts of it, silently: the file is newer,
it is not empty, and it opens. ``--html``/``--pdf`` take the path you give them
and are left alone.

An unknown part number FAILS, listing the parts that do exist. A filter that
silently matched nothing would emit a title page and a contents with no
chapters beneath them, and exit 0 — a document that looks finished and is empty.

THE CHAPTER ORDER IS DERIVED, NEVER LISTED
------------------------------------------
:func:`chapters` walks the tree: parts in sorted order, each part's ``README.md``
first, then that part's chapters in sorted order. A hand-maintained running
order is the defect this avoids — it is correct on the day it is written and
silently wrong on the day a chapter lands, and the failure is invisible because
a book missing one chapter looks exactly like a book.

RENDERING IS DELEGATED, AND THE DELEGATION IS HONEST ABOUT ITSELF
-----------------------------------------------------------------
Markdown becomes HTML through ``pandoc``; HTML becomes PDF through
``weasyprint`` (or headless Chrome, if WeasyPrint is not installed). This
package declares neither as a dependency, so both are resolved at run time and
a missing one is reported **by name, with how to install it, at a non-zero
exit**. There is deliberately no degraded path: a renderer that quietly drops
the chapters it could not convert and exits 0 hands you a document whose gaps
are indistinguishable from the book not having those chapters.

Everything between those two boundaries — the derivation, the title page, the
contents, the anchors, the cross-reference rewriting, the asset inlining — is
this module's own, which is why it is also what the tests drive.

WHAT SELF-CONTAINED MEANS HERE
------------------------------
One file, no network. The stylesheet is inlined, and every image is inlined as a
``data:`` URI read off disk. An asset the tree does not have, or one that would
resolve over the network, **fails the render** rather than becoming a broken
image in a document somebody prints.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

HANDBOOK = Path(__file__).resolve().parent
ASSETS = HANDBOOK / "assets"
STYLESHEET = ASSETS / "book.css"

#: Directories under the handbook root that are never parts.
_NOT_A_PART = frozenset({"assets", "__pycache__"})

#: A setext- or atx-style level-1 heading. Only atx is used in this book, but
#: the leading-hash form is the one worth matching precisely: a ``#`` inside a
#: fenced block is not a heading, which is why :func:`_first_heading` tracks
#: fences rather than scanning with this alone.
_ATX_H1 = re.compile(r"^#\s+(.*\S)\s*$")

_FENCE = re.compile(r"^\s*(```|~~~)")

#: The ``NN`` of an ``NN-slug`` part directory. ``--parts`` matches on this, not
#: on the slug, so retitling a part cannot break a selection.
_PART_PREFIX = re.compile(r"^(\d+)(?:[-_]|$)")

#: ``<h2 id="x">text</h2>`` in pandoc's output. Used to build the navigation the
#: filter box searches; the printed contents are built from the derivation, not
#: from this.
_HEADING = re.compile(r"<h([1-6])\s+id=\"([^\"]+)\"[^>]*>(.*?)</h\1>", re.DOTALL)

_TAG = re.compile(r"<[^>]+>")

#: ``src="..."`` / ``src='...'`` on any element pandoc emits.
_SRC = re.compile(r"""(\ssrc=)(["'])([^"']+)\2""")

#: A markdown cross-reference that pandoc left alone because its target is not
#: an in-document anchor: ``href="../part/chapter.md"``, optionally ``#frag``.
_MD_HREF = re.compile(r"""(\shref=)(["'])([^"'#]+\.md)(#[^"']*)?\2""")

#: Anything that would make the document reach the network. The check is on
#: attributes, never on prose: a URL a chapter *talks about* is content, a URL
#: the document *loads from* is a self-containment failure.
_EXTERNAL_REF = re.compile(
    r"""(?:\ssrc=|\sdata-src=|\ssrcset=|<link[^>]*\shref=|@import\s+|url\()\s*"""
    r"""["']?\s*(https?://[^"')\s>]+)""",
    re.IGNORECASE,
)


class RenderError(RuntimeError):
    """The book could not be rendered. Raised instead of emitting a partial one."""


class MissingToolError(RenderError):
    """A required external program is not installed. Names it, and how to get it."""


# ───────────────────────────────── the derivation ────────────────────────────


@dataclass(frozen=True)
class Part:
    """One numbered part of the book, with its chapters in reading order."""

    directory: Path
    title: str
    readme: Path | None
    chapter_files: tuple[Path, ...]

    @property
    def files(self) -> tuple[Path, ...]:
        """Every markdown file in this part, README first."""
        return ((self.readme,) if self.readme is not None else ()) + self.chapter_files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _first_heading(text: str) -> str | None:
    """The first level-1 heading outside a fenced block, or None."""
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _ATX_H1.match(line)
        if match:
            return match.group(1)
    return None


#: Inline Markdown that survives a raw paragraph lift: emphasis, code spans and
#: link syntax. The title page takes its text straight out of the README rather
#: than through pandoc, so it has to undo these itself.
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_EMPHASIS = re.compile(r"(\*{1,3}|_{1,3}|`+)(.+?)\1", re.DOTALL)

#: An HTML comment, possibly spanning lines. Markdown carries build directives
#: this way (``<!-- anchor-floor: exempt -->``), and :func:`_front_matter` lifts
#: a paragraph VERBATIM rather than rendering it — so a comment reaches the
#: cover as text unless it is removed first. ``DOTALL`` because these wrap.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _plain(text: str) -> str:
    """Strip inline Markdown from a paragraph lifted verbatim out of a file.

    Without this the title page prints the asterisks — the attribution reads
    ``**CARE**, **PACT**`` on the cover of a document going to a client.
    """
    text = _MD_LINK.sub(r"\1", text)
    for _ in range(3):  # nested emphasis: ``**bold *and italic* **``
        text, count = _MD_EMPHASIS.subn(r"\2", text)
        if not count:
            break
    return " ".join(text.split())


def _humanise(stem: str) -> str:
    """A readable title for a file that carries no heading of its own."""
    return (
        re.sub(r"^\d+[-.]?\s*", "", stem).replace("-", " ").replace("_", " ").strip().capitalize()
    )


def title_of(path: Path) -> str:
    """The chapter's own title — its first heading, or its filename humanised."""
    return _first_heading(_read(path)) or _humanise(path.stem)


def slug_for(path: Path, root: Path = HANDBOOK) -> str:
    """A stable, document-unique anchor for a chapter file.

    Derived from the path relative to the handbook root, so it changes only when
    the file moves — which is the one time a stale bookmark *should* break.
    """
    rel = path.resolve().relative_to(root.resolve()).with_suffix("")
    return "-".join(rel.parts)


def part_number(directory_name: str) -> str | None:
    """The ``NN`` of an ``NN-slug`` part directory, or None if it carries none."""
    match = _PART_PREFIX.match(directory_name)
    return match.group(1) if match else None


def _normalise_number(value: str) -> str:
    """``08`` and ``8`` name the same part; anything non-numeric matches literally."""
    text = value.strip()
    return str(int(text)) if text.isdigit() else text.casefold()


def parts(root: Path = HANDBOOK, select: Sequence[str] | None = None) -> list[Part]:
    """Every part of the book, in reading order, derived from the tree.

    A part is a direct subdirectory holding at least one ``.md`` file. Ordering
    is the sorted directory name, which is what the ``NN-`` prefixes are for;
    within a part the ``README.md`` leads and the remaining chapters follow in
    sorted order.

    ``select`` narrows the result to the named part NUMBERS (``["08", "09"]``),
    matched against the directory's own ``NN-`` prefix rather than against any
    name written down here — a hardcoded name would break the moment a part is
    retitled, which is the same defect the running order avoids.

    An unknown number RAISES, listing what does exist. It is never silently
    dropped: a filter that matches nothing would otherwise render a title page
    and a contents with no chapters under them, and exit 0 — a document that
    looks finished and is empty.
    """
    found: list[Part] = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if directory.name in _NOT_A_PART or directory.name.startswith("."):
            continue
        markdown = sorted(p for p in directory.glob("*.md"))
        if not markdown:
            continue
        readme = next((p for p in markdown if p.name == "README.md"), None)
        rest = tuple(p for p in markdown if p is not readme)
        anchor = readme if readme is not None else rest[0]
        found.append(
            Part(
                directory=directory,
                title=title_of(anchor),
                readme=readme,
                chapter_files=rest,
            )
        )
    if select is None:
        return found

    wanted = [v for v in (s.strip() for s in select) if v]
    if not wanted:
        raise RenderError("--parts was given no part numbers")

    available = {_normalise_number(p.directory.name.split("-", 1)[0]): p for p in found}
    by_name = {_normalise_number(p.directory.name): p for p in found}
    chosen: list[Part] = []
    unknown: list[str] = []
    for value in wanted:
        key = _normalise_number(value)
        part = available.get(key) or by_name.get(key)
        if part is None:
            unknown.append(value)
        elif part not in chosen:
            chosen.append(part)
    if unknown:
        listing = ", ".join(
            f"{part_number(p.directory.name) or p.directory.name} ({p.title})" for p in found
        )
        raise RenderError(
            f"unknown part number(s): {', '.join(unknown)}\n"
            f"  this handbook has: {listing or '(no parts)'}"
        )
    # Reading order is the book's, never the order they were typed on the CLI.
    return [p for p in found if p in chosen]


def chapters(root: Path = HANDBOOK, select: Sequence[str] | None = None) -> list[Path]:
    """Every chapter file, in reading order — the book's running order.

    DERIVED FROM THE TREE, never a list in this file. A chapter that lands is in
    the book on the next render with no edit here; a hand-written order would
    have to be remembered, and the render that forgets it produces a book that
    looks complete.

    The handbook's own top-level ``README.md`` is deliberately NOT here: it is
    the book's front matter, not a chapter, and :func:`build_html` places it
    before the first part.

    This is the FLATTENING of :func:`parts`, never a second walk of the tree.
    The renderer assembles the book from :func:`parts`, so a ``chapters`` that
    derived its own order could disagree with the document it is supposed to
    describe — and the contents page would then be a confident list of the
    wrong book.
    """
    return [f for part in parts(root, select) for f in part.files]


def book_readme(root: Path = HANDBOOK) -> Path | None:
    """The book's front matter, if the tree has one."""
    candidate = root / "README.md"
    return candidate if candidate.is_file() else None


def output_stem(root: Path = HANDBOOK, select: Sequence[str] | None = None) -> str:
    """The base filename for a render: ``handbook``, or a named extract.

    An extract MUST NOT be written as ``handbook.pdf``. That is the complete
    book's name, so rendering one into an existing build directory REPLACES
    the whole book with three parts of it, and nothing reports the
    substitution: the file is newer, it is not empty, and it opens. The next
    person to send "the handbook" to a client sends the extract.

    Derived from the parts actually selected — never from the string typed on
    the CLI — so the name cannot describe a different selection from the one
    bound into the document.
    """
    if select is None:
        return "handbook"
    numbers = [part_number(p.directory.name) or p.directory.name for p in parts(root, select)]
    return "handbook-parts-" + "-".join(numbers)


def _front_matter(root: Path) -> tuple[str, str, str]:
    """``(title, subtitle, attribution)`` read off the book's own README.

    Every one of the three is DERIVED. The attribution in particular is a
    compliance obligation (Aegis implements the Foundation's standards; it does
    not own them), so it is lifted from the README rather than retyped here —
    two copies of an attribution is one copy that can go wrong silently.

    HTML COMMENTS ARE STRIPPED BEFORE A BLOCK IS CONSIDERED PROSE. A comment is
    a note to the BUILD, never to the reader, and this function lifts a
    paragraph verbatim rather than rendering it — so without the strip a
    directive addressed to a checker becomes the subtitle of a document going to
    a partner. Measured on the shipped tree 2026-09-20: the README's first
    non-heading block is
    ``<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->``
    and the cover printed exactly that, HTML-escaped, where the subtitle
    belongs. Same class as the raw ``**CARE**`` emphasis :func:`_plain` exists
    to undo, and invisible for the same reason: every heading-ish prefix was
    filtered and ``<!--`` was not one of them.

    Stripping at the TEXT, before the split into blocks, rather than filtering
    the block list: it handles a comment that merely PREFIXES a real paragraph
    as well as one that is a block of its own, and it keeps a comment that
    happens to contain ``CC BY`` from being lifted as the attribution.
    """
    readme = book_readme(root)
    if readme is None:
        return ("Handbook", "", "")
    text = _HTML_COMMENT.sub("", _read(readme))
    title = _first_heading(text) or "Handbook"

    body = text.split("\n", 1)[1] if "\n" in text else ""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    prose = [b for b in blocks if not b.startswith(("#", "|", "```", ">", "-", "*"))]
    subtitle = _plain(prose[0]) if prose else ""
    attribution = next(
        (_plain(b) for b in prose if "CC BY" in b or "Terrene Foundation" in b),
        "",
    )
    return (_plain(title), subtitle, attribution)


# ───────────────────────────── the external boundary ─────────────────────────

#: ``(program, environment override, how to install it)``.
_TOOLS: dict[str, tuple[str, str]] = {
    "pandoc": (
        "AEGIS_HANDBOOK_PANDOC",
        "brew install pandoc | apt-get install pandoc | https://pandoc.org/installing.html",
    ),
    "weasyprint": (
        "AEGIS_HANDBOOK_WEASYPRINT",
        "pipx install weasyprint | pip install weasyprint | "
        "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html",
    ),
}

#: Where headless Chrome lives, per platform. Only consulted when WeasyPrint is
#: absent — see :func:`write_pdf`.
_CHROME_CANDIDATES: tuple[str, ...] = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def find_tool(name: str) -> str | None:
    """Resolve an external program, honouring its environment override.

    Returns None rather than raising: a caller that has a fallback needs to ask
    without being interrupted, and a caller that does not calls
    :func:`require_tool`.
    """
    env_var, _hint = _TOOLS.get(name, ("", ""))
    override = os.environ.get(env_var) if env_var else None
    if override:
        return override if Path(override).is_file() else shutil.which(override)
    return shutil.which(name)


def require_tool(name: str) -> str:
    """Resolve an external program, or fail naming it and how to install it."""
    resolved = find_tool(name)
    if resolved:
        return resolved
    _env, hint = _TOOLS.get(name, ("", ""))
    raise MissingToolError(
        f"required program not found: {name}\n"
        f"  install it with: {hint}\n"
        f"  or point at an existing copy: {_TOOLS.get(name, ('<none>',))[0]}=/path/to/{name}"
    )


def _run(command: Sequence[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 - argv list, never a shell string
            list(command),
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RenderError(f"could not run {command[0]}: {exc}") from exc


def markdown_to_html(text: str, id_prefix: str) -> str:
    """One chapter's Markdown, converted by pandoc, with anchors namespaced.

    ``--id-prefix`` is what lets 48 chapters share one document without their
    headings colliding: it prefixes every generated identifier AND every
    in-document link, so a chapter's own internal cross-references keep working
    after the merge.
    """
    pandoc = require_tool("pandoc")
    result = _run(
        [pandoc, "--from=gfm", "--to=html5", "--wrap=none", f"--id-prefix={id_prefix}"],
        stdin=text,
    )
    if result.returncode != 0:
        raise RenderError(f"pandoc failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


Converter = Callable[[str, str], str]


# ───────────────────────────────── assembly ──────────────────────────────────


def _strip_leading_h1(fragment: str) -> str:
    """Drop a chapter's own title heading; the section header already carries it."""
    return re.sub(r"\A\s*<h1[^>]*>.*?</h1>\s*", "", fragment, count=1, flags=re.DOTALL)


def _inline_assets(fragment: str, base_dir: Path) -> str:
    """Replace every ``src`` with a ``data:`` URI read off disk.

    A missing file or a network-resolved source raises. That is the point: a
    renderer that skipped them would produce a document whose broken images are
    only discoverable by someone looking at the page.
    """

    def replace(match: re.Match[str]) -> str:
        attr, quote, source = match.group(1), match.group(2), match.group(3)
        if source.startswith("data:"):
            return match.group(0)
        if source.startswith(("http://", "https://", "//")):
            raise RenderError(
                f"asset resolves over the network and cannot be inlined: {source}\n"
                "  the handbook must render to a single offline file"
            )
        path = (base_dir / source).resolve()
        if not path.is_file():
            raise RenderError(f"asset not found: {source} (looked in {base_dir})")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"{attr}{quote}data:{mime};base64,{encoded}{quote}"

    return _SRC.sub(replace, fragment)


def _rewrite_cross_references(
    fragment: str,
    *,
    chapter: Path,
    root: Path,
    known: dict[Path, str],
) -> str:
    """Turn ``../part/chapter.md`` links into in-document anchors.

    The book is one file, so a link to another chapter's *file* goes nowhere. A
    link whose target is not a chapter of this book is left alone rather than
    guessed at — a wrong anchor is worse than a link that visibly does nothing,
    because it lands the reader somewhere plausible.
    """

    def replace(match: re.Match[str]) -> str:
        attr, quote, target, fragment_id = (
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(4) or "",
        )
        resolved = (chapter.parent / target).resolve()
        slug = known.get(resolved)
        if slug is None:
            return match.group(0)
        anchor = f"#{slug}{fragment_id.replace('#', '-', 1)}" if fragment_id else f"#{slug}"
        return f"{attr}{quote}{anchor}{quote}"

    return _MD_HREF.sub(replace, fragment)


def _headings(fragment: str, *, levels: Iterable[int] = (2, 3)) -> list[tuple[int, str, str]]:
    """``(level, anchor, text)`` for the headings the navigation filter searches."""
    wanted = set(levels)
    out: list[tuple[int, str, str]] = []
    for match in _HEADING.finditer(fragment):
        level = int(match.group(1))
        if level not in wanted:
            continue
        text = " ".join(_TAG.sub("", match.group(3)).split())
        out.append((level, match.group(2), html.unescape(text)))
    return out


@dataclass
class _Section:
    """One rendered unit of the book: a part opener, or a chapter."""

    kind: str  # "part" | "chapter"
    slug: str
    title: str
    body: str
    headings: list[tuple[int, str, str]]


def external_asset_references(document: str) -> list[str]:
    """Every URL the document would LOAD over the network. Empty means offline.

    Deliberately keyed on the loading attributes (``src``, ``<link href>``,
    ``srcset``, ``@import``, ``url()``) rather than on the text: a chapter that
    *mentions* a URL is prose, and flagging it would make the check fire on
    correct documents until someone turned it off.
    """
    return [m.group(1) for m in _EXTERNAL_REF.finditer(document)]


def _stylesheet(path: Path | None = None) -> str:
    sheet = path or STYLESHEET
    if not sheet.is_file():
        raise RenderError(f"stylesheet not found: {sheet}")
    return _read(sheet)


def _today() -> str:
    """Today, or the pinned date — so a build can be made reproducible."""
    override = os.environ.get("AEGIS_HANDBOOK_DATE")
    if override:
        return override
    return datetime.date.today().isoformat()


def _render_sections(
    root: Path, convert: Converter, select: Sequence[str] | None = None
) -> list[_Section]:
    # Keyed on the SELECTED chapters: under `--parts` a link to a chapter this
    # document does not carry is left as its `.md` target rather than pointed at
    # an anchor that is not here. A dead-looking link is honest; one that lands
    # the reader on the wrong section is not.
    known = {p.resolve(): slug_for(p, root) for p in chapters(root, select)}
    sections: list[_Section] = []

    readme = book_readme(root)
    if readme is not None:
        slug = "front-matter"
        body = convert(_read(readme), f"{slug}-")
        body = _strip_leading_h1(body)
        body = _rewrite_cross_references(body, chapter=readme, root=root, known=known)
        body = _inline_assets(body, readme.parent)
        sections.append(
            _Section("front", slug, _first_heading(_read(readme)) or "About this book", body, [])
        )

    for part in parts(root, select):
        for index, source in enumerate(part.files):
            slug = slug_for(source, root)
            body = convert(_read(source), f"{slug}-")
            headings = _headings(body)
            body = _strip_leading_h1(body)
            body = _rewrite_cross_references(body, chapter=source, root=root, known=known)
            body = _inline_assets(body, source.parent)
            sections.append(
                _Section(
                    kind="part" if (index == 0 and source is part.readme) else "chapter",
                    slug=slug,
                    title=title_of(source),
                    body=body,
                    headings=headings,
                )
            )
    return sections


def _nav_html(sections: Sequence[_Section]) -> str:
    rows: list[str] = []
    for section in sections:
        css = {"front": "nav-front", "part": "nav-part"}.get(section.kind, "nav-chapter")
        rows.append(
            f'<li class="{css}" data-text="{html.escape(section.title.lower())}">'
            f'<a href="#{section.slug}">{html.escape(section.title)}</a></li>'
        )
        for level, anchor, text in section.headings:
            rows.append(
                f'<li class="nav-h{level}" data-text="{html.escape(text.lower())}">'
                f'<a href="#{anchor}">{html.escape(text)}</a></li>'
            )
    return "\n".join(rows)


def _toc_html(sections: Sequence[_Section]) -> str:
    """The printed contents: part, then its chapters. Page numbers come from CSS."""
    rows: list[str] = []
    open_list = False
    for section in sections:
        if section.kind in {"front", "part"}:
            if open_list:
                rows.append("</ol></li>")
                open_list = False
            rows.append(
                f'<li class="toc-part"><a href="#{section.slug}">'
                f"{html.escape(section.title)}</a>"
            )
            if section.kind == "part":
                rows.append('<ol class="toc-chapters">')
                open_list = True
            else:
                rows.append("</li>")
        else:
            rows.append(
                f'<li class="toc-chapter"><a href="#{section.slug}">'
                f"{html.escape(section.title)}</a></li>"
            )
    if open_list:
        rows.append("</ol></li>")
    return "\n".join(rows)


_SCRIPT = """
(function () {
  var toggle = document.getElementById('nav-toggle');
  var filter = document.getElementById('nav-filter');
  var items = Array.prototype.slice.call(
    document.querySelectorAll('#nav-list > li')
  );
  if (toggle) {
    toggle.addEventListener('click', function () {
      document.body.classList.toggle('nav-open');
    });
  }
  if (filter) {
    filter.addEventListener('input', function () {
      var needle = filter.value.trim().toLowerCase();
      var empty = needle === '';
      var hits = 0;
      items.forEach(function (li) {
        var match = empty || (li.getAttribute('data-text') || '').indexOf(needle) !== -1;
        li.hidden = !match;
        if (match) { hits += 1; }
      });
      document.getElementById('nav-empty').hidden = empty || hits > 0;
    });
  }
})();
"""


def build_html(
    root: Path = HANDBOOK,
    *,
    convert: Converter | None = None,
    stylesheet: Path | None = None,
    today: str | None = None,
    select: Sequence[str] | None = None,
) -> str:
    """The whole book as one self-contained HTML document.

    ``convert`` is the Markdown→HTML boundary, injected so it can be exercised
    without pandoc; the production default IS pandoc and is unchanged by the
    seam existing. Everything else here — derivation, contents, anchors,
    cross-references, asset inlining — is this module's own work and is what a
    test of this function actually measures.
    """
    converter = convert or markdown_to_html
    selected = parts(root, select)  # validates `select` BEFORE any conversion work
    sections = _render_sections(root, converter, select)
    if not sections or not selected:
        raise RenderError(f"no chapters found under {root} — nothing to render")

    title, subtitle, attribution = _front_matter(root)
    document_title = title
    if select is not None:
        # The cover must not claim to be the whole handbook when it is an
        # extract. Derived from the parts actually included, so it cannot
        # describe a selection other than the one bound into the document.
        numbers = [part_number(p.directory.name) or p.directory.name for p in selected]
        plural = "s" if len(selected) > 1 else ""
        subtitle = f"An extract: part{plural} " f"{', '.join(numbers)} of {title} — " + "; ".join(
            p.title for p in selected
        )
        # `<title>` is what a PDF reader shows as the DOCUMENT TITLE, in the
        # window chrome and in file properties. Left at the book's own title
        # an extract is indistinguishable from the complete handbook in every
        # surface that reads metadata rather than the cover — including the
        # one a recipient checks when asking "is this the whole thing?".
        document_title = f"{title} — extract: part{plural} {', '.join(numbers)}"
    stamp = today or _today()

    body_parts: list[str] = []
    for section in sections:
        if section.kind == "part":
            body_parts.append(
                f'<section class="part-opener" id="{section.slug}">\n'
                f'<h1 class="part-title">{html.escape(section.title)}</h1>\n'
                f"{section.body}\n</section>"
            )
        else:
            css = "front-matter" if section.kind == "front" else "chapter"
            body_parts.append(
                f'<section class="{css}" id="{section.slug}">\n'
                f"<h1>{html.escape(section.title)}</h1>\n"
                f"{section.body}\n</section>"
            )

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(document_title)}</title>
<meta name="generator" content="aegis_sdk.handbook.render">
<style>
{_stylesheet(stylesheet)}
</style>
</head>
<body>
<button id="nav-toggle" type="button" aria-label="Show contents">Contents</button>
<nav id="nav" aria-label="Contents">
  <label class="nav-filter-label" for="nav-filter">Filter</label>
  <input id="nav-filter" type="search" placeholder="Filter headings&hellip;"
         autocomplete="off" spellcheck="false">
  <ol id="nav-list">
{_nav_html(sections)}
  </ol>
  <p id="nav-empty" hidden>No heading matches that.</p>
</nav>
<main>
<section class="title-page">
  <p class="title-eyebrow">Aegis</p>
  <h1 class="book-title">{html.escape(title)}</h1>
  <p class="book-subtitle">{html.escape(subtitle)}</p>
  <p class="book-attribution">{html.escape(attribution)}</p>
  <p class="book-date">Generated {html.escape(stamp)}</p>
</section>
<section class="toc-page" id="contents">
  <h1>Contents</h1>
  <ol class="toc">
{_toc_html(sections)}
  </ol>
</section>
{chr(10).join(body_parts)}
</main>
<script>
{_SCRIPT}
</script>
</body>
</html>
"""
    leaks = external_asset_references(document)
    if leaks:
        raise RenderError(
            "document is not self-contained; these references load over the network:\n  "
            + "\n  ".join(sorted(set(leaks)))
        )
    return document


# ─────────────────────────────────── outputs ─────────────────────────────────


def write_html(out: Path, root: Path = HANDBOOK, **kwargs: object) -> Path:
    """Build the book and write it. Built fully in memory first, so a failed
    render leaves no half-written file behind for someone to read as the book."""
    document = build_html(root, **kwargs)  # type: ignore[arg-type]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    return out


def _pdf_via_weasyprint(program: str, source: Path, out: Path) -> None:
    result = _run([program, "--encoding", "utf-8", str(source), str(out)])
    if result.returncode != 0:
        raise RenderError(f"weasyprint failed (exit {result.returncode}): {result.stderr.strip()}")


def _find_chrome() -> str | None:
    for candidate in _CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _pdf_via_chrome(program: str, source: Path, out: Path) -> None:
    result = _run(
        [
            program,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-pdf-header-footer",
            "--virtual-time-budget=20000",
            f"--print-to-pdf={out}",
            source.as_uri(),
        ]
    )
    if result.returncode != 0:
        raise RenderError(f"chrome failed (exit {result.returncode}): {result.stderr.strip()}")


def write_pdf(out: Path, root: Path = HANDBOOK, **kwargs: object) -> Path:
    """Build the book and print it to PDF.

    WeasyPrint is preferred because it implements CSS Paged Media, which is what
    the running heads, the part openers and the page-numbered contents are built
    on. Headless Chrome is a fallback for a machine that has no WeasyPrint, and
    it is genuinely a fallback: it honours the page box and loses the paged
    generated content. It is used only when WeasyPrint is ABSENT — a WeasyPrint
    that runs and fails is a real failure and is reported as one.
    """
    document = build_html(root, **kwargs)  # type: ignore[arg-type]
    out.parent.mkdir(parents=True, exist_ok=True)

    weasyprint = find_tool("weasyprint")
    chrome = None if weasyprint else _find_chrome()
    if not weasyprint and not chrome:
        _env, hint = _TOOLS["weasyprint"]
        raise MissingToolError(
            "required program not found: weasyprint (no headless Chrome either)\n"
            f"  install it with: {hint}\n"
            "  or point at an existing copy: AEGIS_HANDBOOK_WEASYPRINT=/path/to/weasyprint"
        )

    with tempfile.TemporaryDirectory(prefix="aegis-handbook-") as tmp:
        source = Path(tmp) / "handbook.html"
        source.write_text(document, encoding="utf-8")
        if weasyprint:
            _pdf_via_weasyprint(weasyprint, source, out)
        else:
            assert chrome is not None
            _pdf_via_chrome(chrome, source, out)

    if not out.is_file() or out.stat().st_size == 0:
        raise RenderError(f"the renderer reported success but produced no PDF at {out}")
    return out


# ───────────────────────────────────── cli ───────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m aegis_sdk.handbook.render",
        description="Render the handbook as one self-contained HTML file and/or a PDF.",
    )
    ap.add_argument("--html", metavar="PATH", help="write the self-contained HTML here")
    ap.add_argument("--pdf", metavar="PATH", help="write the PDF here")
    ap.add_argument("--all", action="store_true", help="write both, into --out-dir")
    ap.add_argument(
        "--out-dir",
        "-o",
        metavar="DIR",
        default="build",
        help="directory for --all (default: build)",
    )
    ap.add_argument(
        "--parts",
        metavar="NN,NN",
        help="render only these part numbers (e.g. 08,09,10); default is the whole book",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="print the derived chapter order and exit, rendering nothing",
    )
    args = ap.parse_args(argv)
    select = args.parts.split(",") if args.parts else None

    # Read through the module global at CALL time rather than relying on the
    # default argument, which binds at definition time and so cannot be
    # redirected at a different tree.
    root = HANDBOOK

    if args.list:
        try:
            listed = parts(root, select)
        except RenderError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        for part in listed:
            print(part.title)
            for source in part.files:
                print(f"  {title_of(source):<52} {source.relative_to(root)}")
        return 0

    if not (args.html or args.pdf or args.all):
        ap.error("nothing to do: pass --html, --pdf, or --all")

    targets: list[tuple[str, Path]] = []
    if args.all:
        out_dir = Path(args.out_dir)
        try:
            # Named from the SELECTION, so an extract never lands on the
            # complete book's filename. An explicit --html/--pdf path is the
            # caller's own choice and is left exactly as given.
            stem = output_stem(root, select)
        except RenderError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        targets += [("html", out_dir / f"{stem}.html"), ("pdf", out_dir / f"{stem}.pdf")]
    if args.html:
        targets.append(("html", Path(args.html)))
    if args.pdf:
        targets.append(("pdf", Path(args.pdf)))

    try:
        for kind, path in targets:
            writer = write_html if kind == "html" else write_pdf
            written = writer(path, root, select=select)
            print(f"{kind:<4} {written} ({written.stat().st_size:,} bytes)")
    except RenderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
