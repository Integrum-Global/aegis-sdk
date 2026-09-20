"""An HTML comment in the book README must never reach the cover.

A MEASURED defect, not a hypothetical one. The shipped README's first
non-heading block is an HTML comment — ``<!-- anchor-floor: exempt (part
navigation; chapters carry the anchors) -->`` — and on 2026-09-20 the rendered
cover printed exactly that, HTML-escaped, in the subtitle slot. A note
addressed to a checker appeared on the front page of a document that goes to a
partner.

It was invisible because every prefix :func:`render._front_matter`'s prose
filter knew about (``#``, ``|``, ```````, ``>``, ``-``, ``*``) is a MARKDOWN
one, and ``<!--`` is not. Same class as the raw ``**CARE**`` emphasis
:func:`render._plain` already exists to undo.

These pin :func:`render._front_matter` DIRECTLY rather than through a rendered
document: the defect is in what that function lifts, and the smaller instrument
is the one whose red names the cause. Each case asserts BOTH directions — the
comment's absence alone would pass if the subtitle were empty, which is exactly
what stripping the comment too late would produce: no leak, and no subtitle
either.

All three were verified RED against the pre-fix ``render.py`` and GREEN after
it, on 2026-09-20.
"""

from __future__ import annotations

from pathlib import Path

from aegis_sdk.handbook import render

_ATTRIBUTION = "Published by the **Terrene Foundation** under CC BY 4.0"


def _book(tmp_path: Path, readme: str) -> Path:
    """A book root carrying nothing but the README the case is about."""
    root = tmp_path / "handbook"
    root.mkdir()
    (root / "README.md").write_text(readme, encoding="utf-8")
    return root


def test_a_build_directive_comment_never_reaches_the_cover(tmp_path: Path) -> None:
    """The real shape: comment FIRST as its own block, real subtitle SECOND."""
    root = _book(
        tmp_path,
        "# The Test Handbook\n\n"
        "<!-- anchor-floor: exempt (part navigation) -->\n\n"
        "The real subtitle paragraph.\n\n"
        f"{_ATTRIBUTION}.\n",
    )

    title, subtitle, attribution = render._front_matter(root)

    assert title == "The Test Handbook"
    assert "anchor-floor" not in subtitle, f"a build directive reached the cover: {subtitle!r}"
    assert "<!--" not in subtitle and "-->" not in subtitle, "comment syntax on the cover"
    assert subtitle == "The real subtitle paragraph.", "the comment displaced the real subtitle"
    # The attribution is still derived, and from the paragraph rather than the comment.
    assert "Terrene Foundation" in attribution and "CC BY 4.0" in attribution


def test_a_comment_prefixing_a_paragraph_does_not_truncate_it(tmp_path: Path) -> None:
    """Stripping must not merely DROP an offending block.

    A comment on the line above a paragraph is ONE block, not two, so a filter
    that skipped comment-leading blocks would discard the subtitle with it.
    Stripping at the text is what keeps the paragraph.
    """
    root = _book(
        tmp_path,
        "# The Test Handbook\n\n"
        "<!-- a directive -->\nThe subtitle that follows it.\n\n"
        f"{_ATTRIBUTION}.\n",
    )

    _title, subtitle, _attribution = render._front_matter(root)

    assert "a directive" not in subtitle
    assert subtitle == "The subtitle that follows it."


def test_a_comment_containing_the_attribution_tokens_is_not_lifted(tmp_path: Path) -> None:
    """The attribution is a COMPLIANCE line, so a commented-out one must not
    satisfy it — the cover would otherwise carry a licence claim nobody
    published."""
    root = _book(
        tmp_path,
        "# The Test Handbook\n\n"
        "The real subtitle.\n\n"
        "<!-- old: Terrene Foundation, CC BY 4.0, superseded -->\n\n"
        f"{_ATTRIBUTION}, current.\n",
    )

    _title, subtitle, attribution = render._front_matter(root)

    assert subtitle == "The real subtitle."
    assert "superseded" not in attribution, "a commented-out attribution was lifted onto the cover"
    assert "current" in attribution, "the live attribution is the one that must appear"


def test_a_readme_with_no_comments_is_unaffected(tmp_path: Path) -> None:
    """The control: the strip must not be what produces the subtitle.

    Without this, a bug that emptied every subtitle would pass all three cases
    above — they each assert an absence as well as a presence, but a reader
    cannot tell from them that the ordinary path still works.
    """
    root = _book(
        tmp_path,
        "# The Test Handbook\n\nA subtitle with **emphasis** in it.\n\n" f"{_ATTRIBUTION}.\n",
    )

    title, subtitle, attribution = render._front_matter(root)

    assert title == "The Test Handbook"
    assert subtitle == "A subtitle with emphasis in it."
    assert "Terrene Foundation" in attribution
