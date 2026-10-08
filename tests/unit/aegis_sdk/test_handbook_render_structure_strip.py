"""The committed handbook PDF must resolve every reference it makes.

WHY THIS FILE EXISTS, and it is a measured failure rather than a hypothetical.

Headless Chrome emits a TAGGED PDF: this book's 513 pages produce 56,067
``StructElem`` objects, roughly 9 MB of a 16.1 MB file. :func:`render.strip_tagged_structure`
removes them, because the repository has a no-file-over-10-MB rule and the
operators of this document are people reading it.

The first cut of that strip dropped every object containing ``/Type /StructElem``.
That misses the tree's CONTAINER objects -- the ``/ParentTree`` ``/Nums``
sub-arrays and the ``/IDTree`` name-tree nodes hold no such string -- so they
survived, orphaned, still pointing at elements that had been deleted. It
produced a file of 9,408,862 bytes that:

* opened,
* reported 513 pages,
* reported 38 embedded fonts,
* extracted 170,166 words with ``pdftotext``,
* and carried **37,681 dangling references**.

Every cheap signal said "fine". Reference resolution is the only check that told
it apart from a good file, so it is pinned here rather than measured once, and
:func:`test_the_reference_check_detects_a_dangling_reference` is its bipolar
control: the check must be able to return the OTHER answer, or it is not
evidence (``instrument-discipline.md`` MUST-1).

The two ``test_the_committed_handbook_pdf_*`` cases are the ones that would have
caught the malformed build at the point it mattered. They run over the SHIPPED
artifact, not a synthetic one, so they cannot drift away from what ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_sdk.handbook import render

#: The reference walk must survive a payload that LOOKS like a reference. If the
#: strip rewrote inside stream payloads it would corrupt image samples and
#: compressed operators, so this object carries a reference-shaped byte run and
#: ``test_the_strip_does_not_edit_stream_payloads`` asserts it comes through
#: byte for byte.
_TRAP_PAYLOAD = b"\nstream\nBT 99 0 R /StructParent 3 (hello) Tj ET\nendstream"


def _build_pdf(objects: dict[int, bytes]) -> bytes:
    """A minimal but well-formed PDF: classic xref, objects at line starts."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj" % number + objects[number] + b"\nendobj\n"

    size = max(objects) + 1
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for number in range(1, size):
        if number in offsets:
            out += b"%010d 00000 n \n" % offsets[number]
        else:
            out += b"0000000000 65535 f \n"
    out += (
        b"trailer\n<</Size "
        + str(size).encode()
        + b" /Root 1 0 R>>\nstartxref\n"
        + str(xref_at).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)


def _plain_pdf() -> bytes:
    """A PDF with no structure tree at all — what an untagged renderer emits."""
    return _build_pdf(
        {
            1: b"\n<</Type /Catalog /Pages 2 0 R>>",
            2: b"\n<</Type /Pages /Kids [3 0 R] /Count 1>>",
            3: b"\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R>>",
            4: b"\n<</Length 12>>" + _TRAP_PAYLOAD,
        }
    )


def _tagged_pdf(*, page_contents: int = 4) -> bytes:
    """A tagged PDF shaped like Chrome's: a tree, its element, and a container.

    Object 7 is the container that the first cut of the strip left behind: it
    holds no ``/Type /StructElem``, so a string-keyed rule misses it, and it
    points at the element being deleted. It is the whole reason the rule is a
    transitive closure.

    ``page_contents`` points the KEPT page at a different object. Aiming it at
    the element (6) builds the shape the postcondition must refuse: a retained
    object referencing a removed one.
    """
    return _build_pdf(
        {
            1: b"\n<</Type /Catalog /Pages 2 0 R /StructTreeRoot 5 0 R"
            b" /MarkInfo <</Type /MarkInfo /Marked true>>>>",
            2: b"\n<</Type /Pages /Kids [3 0 R] /Count 1>>",
            3: b"\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Contents " + b"%d 0 R" % page_contents + b" /StructParents 0 /Tabs /S>>",
            4: b"\n<</Length 43>>" + _TRAP_PAYLOAD,
            5: b"\n<</Type /StructTreeRoot /K 6 0 R /ParentTree 7 0 R>>",
            6: b"\n<</Type /StructElem /S /P /P 5 0 R /Pg 3 0 R /K 0>>",
            7: b"\n<</Nums [0 [6 0 R]]>>",
        }
    )


def _shipped_pdf() -> Path:
    pdf = render.HANDBOOK / "handbook.pdf"
    assert pdf.is_file(), (
        f"{pdf} is missing. It is committed deliberately (the operator's "
        f"2026-10-08 decision), and this file pins it. Regenerate with: "
        f"python -m aegis_sdk.handbook.render --pdf {pdf}"
    )
    return pdf


# ─────────────────────── the shipped artifact, pinned ────────────────────────


def test_the_committed_handbook_pdf_has_no_dangling_references() -> None:
    """THE CHECK THAT MATTERS, run over what actually ships.

    This is the case that would have failed the malformed 9.4 MB build. Nothing
    else here would have: it opened, paginated, counted fonts and extracted text
    exactly like a good one.
    """
    dangling = render.dangling_references(_shipped_pdf().read_bytes())
    assert dangling == [], (
        f"the committed handbook.pdf references {len(dangling)} object(s) that do "
        f"not exist in it, first {dangling[:5]}. It will open and paginate "
        f"anyway — that is what makes this class of defect dangerous. Re-render "
        f"with `python -m aegis_sdk.handbook.render --pdf "
        f"{render.HANDBOOK / 'handbook.pdf'}` and re-run this test."
    )


def test_the_committed_handbook_pdf_carries_no_structure_tree() -> None:
    """Pins the operator's 2026-10-08 decision, and what it cost.

    Tagging is what a screen reader consumes. Dropping it was a decision taken
    WITH the accessibility loss named and accepted, against the alternative of a
    16.1 MB file that breaches the repository's 10 MB binary rule. Asserting it
    here means a future session re-enabling tagging has to find and change this
    test, rather than silently shipping a file twice the size.
    """
    data = _shipped_pdf().read_bytes()
    assert b"/StructTreeRoot" not in data, (
        "handbook.pdf carries a structure tree again. Chrome emits one by "
        "default and it is roughly half the file; render.strip_tagged_structure "
        "removes it. If tagging is being restored on purpose, that reverses the "
        "operator's 2026-10-08 decision and needs them, not this test edited."
    )
    assert b"/StructElem" not in data, "structure elements survive in handbook.pdf"


# ─────────────────── the strip, and the defect it had ────────────────────────


def test_the_strip_drops_the_trees_containers_not_only_its_elements() -> None:
    """THE REGRESSION. A string-keyed rule leaves the container orphaned.

    Object 7 holds no ``/Type /StructElem`` and references only the element, so
    dropping by type leaves it behind pointing at a deleted object. That is the
    exact shape of the 37,681-reference failure, at the scale where it is
    reviewable.
    """
    stripped = render.strip_tagged_structure(_tagged_pdf())

    assert b"/StructTreeRoot" not in stripped
    assert b"/StructElem" not in stripped
    assert b"/Nums" not in stripped, (
        "the /ParentTree container survived the strip. It holds no "
        "/Type /StructElem, so it is only removed by walking out from "
        "StructTreeRoot — and orphaned it still references the deleted element."
    )
    assert render.dangling_references(stripped) == []


def test_the_strip_keeps_the_page_the_link_and_the_payload() -> None:
    """What the strip must NOT touch, asserted rather than assumed."""
    tagged = _tagged_pdf()
    stripped = render.strip_tagged_structure(tagged)

    assert b"/Type /Page" in stripped, "the page was dropped"
    assert render._pdf_page_count(stripped) == render._pdf_page_count(tagged)
    assert _TRAP_PAYLOAD in stripped, (
        "the stream payload was edited. Payloads are arbitrary bytes — image "
        "samples and compressed operators — and a reference-shaped run inside "
        "one is a coincidence, not a reference."
    )
    assert b"/StructParents" not in stripped, (
        "a key that only indexes the removed tree survived; without the "
        "/ParentTree it points at nothing"
    )


def test_the_strip_does_not_edit_stream_payloads() -> None:
    """The trap payload carries `99 0 R` and `/StructParent 3` INSIDE a stream.

    Both must come through untouched. If the key-removal or the renumbering ran
    over the payload, the first would be rewritten to a different object number
    and the second deleted — either one silently corrupting the file.
    """
    stripped = render.strip_tagged_structure(_tagged_pdf())
    start = stripped.index(b"stream\n") + len(b"stream\n")
    end = stripped.index(b"\nendstream", start)
    assert stripped[start:end] == _TRAP_PAYLOAD[len(b"\nstream\n") : -len(b"\nendstream")]


def test_the_strip_leaves_an_untagged_pdf_completely_alone() -> None:
    """Identity, not equality — an untagged file must not be repacked at all."""
    plain = _plain_pdf()
    assert render.strip_tagged_structure(plain) is plain


def test_the_strip_refuses_a_pdf_it_cannot_parse() -> None:
    """A strip that cannot verify its output must not produce one."""
    with pytest.raises(render.RenderError, match="object streams"):
        render.strip_tagged_structure(_tagged_pdf().replace(b"/Nums", b"/ObjStm"))


# ────────────────── the check itself, and its bipolar control ────────────────


def test_the_reference_check_detects_a_dangling_reference() -> None:
    """BIPOLAR CONTROL — the check must be able to return the OTHER answer.

    Without this, ``dangling_references`` returning ``[]`` proves nothing: an
    implementation that returned ``[]`` unconditionally would satisfy every
    other case in this file. A check that cannot discriminate is not evidence
    (``instrument-discipline.md`` MUST-1), and this one is the only instrument
    that caught the malformed build.
    """
    broken = _build_pdf(
        {
            1: b"\n<</Type /Catalog /Pages 2 0 R>>",
            2: b"\n<</Type /Pages /Kids [3 0 R] /Count 1>>",
            3: b"\n<</Type /Page /Parent 2 0 R /Annots [999 0 R]>>",
        }
    )
    assert render.dangling_references(broken) == [999]
    assert render.dangling_references(_plain_pdf()) == []
    assert render.dangling_references(_tagged_pdf()) == []


def test_the_strip_refuses_when_it_would_leave_a_dangling_reference() -> None:
    """The postcondition is a REFUSAL, not a warning.

    The closure decides what to REMOVE; it does not re-point what STAYS, and a
    kept object can reference a removed one. Here the page's ``/Contents`` aims
    at the element the strip drops, so emitting the result would leave a
    reference resolving to nothing — or, once the kept objects are renumbered,
    to a DIFFERENT object, which is worse because no check would see it. The
    strip must raise rather than write that file.
    """
    with pytest.raises(render.RenderError, match="dangling reference"):
        render.strip_tagged_structure(_tagged_pdf(page_contents=6))
