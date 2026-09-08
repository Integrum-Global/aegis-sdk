"""The SDK-shipped prose gate runs HERE too, not only on the reader's machine.

WHY THIS EXISTS
---------------
``aegis_sdk.handbook.check`` re-resolves every anchor in the shipped prose — the
handbook and the architect working material under ``coc/`` — against the build it
is packaged with. Its whole design property is that it ships with the thing it
checks, so the reader can run it.

That property is real and it was doing only half a job: measured before this file
existed, **no test and no workflow step in this repository executed it**. The
grep is one line and returns nothing:

    grep -rn "handbook.check" tests/ scripts/ .github/     ->  0 matches

So a claim could lose its grounding here, land, ship, and the FIRST party to
discover it would be the customer running the command we told them to run. That
inverts the point of shipping a checkable artifact: we would be handing the
reader an instrument whose job is to catch our own regressions, and finding out
from them.

This is the gate-liveness shape this repo has recorded more than once — a check
that exists, decides nothing, and is indistinguishable from a check that does not
exist. It costs ~1s to close.

WHAT THIS TEST DOES NOT ESTABLISH
---------------------------------
Everything ``check`` itself cannot see, which its module docstring enumerates at
length and which is not re-litigated here: existence is not behaviour, it cannot
see fail-open, and the route table it resolves against is this client's BELIEF
about the API rather than the API. A green here means every named surface still
exists in this build. It means nothing about whether the server honours it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"


@pytest.fixture(scope="module")
def check_module():
    """Import the shipped checker from THIS tree, not from an installed copy.

    The distinction is load-bearing and this repo carries the scar: a bare
    ``import aegis_sdk`` in a worktree can resolve to the primary checkout
    through a shared editable install, so the gate would measure a different
    tree than the one under test and report a clean result about source nobody
    changed.
    """
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from aegis_sdk.handbook import check as mod

    resolved = Path(mod.__file__).resolve()
    assert resolved.is_relative_to(SRC), (
        f"the checker resolved to {resolved}, which is outside {SRC} — this test "
        "would be measuring another tree"
    )
    return mod


def test_every_anchor_in_shipped_prose_resolves(check_module) -> None:
    counts, problems = check_module.scan()
    assert not problems, (
        "shipped prose names surfaces this build does not have:\n  "
        + "\n  ".join(problems)
    )
    assert counts, "the scan found no chapters at all — it is measuring nothing"


def test_no_chapter_fell_below_its_anchor_floor(check_module) -> None:
    """The floor only rises. Falling below it is a claim that lost its grounding.

    The polarity is deliberate and opposite to a disclosure baseline: the failure
    being fenced is DELETING a claim to make a gate pass, so removal is what has
    to be expensive.
    """
    import json

    counts, _ = check_module.scan()
    floors = json.loads(check_module.FLOOR_PATH.read_text(encoding="utf-8"))["floors"]

    below = {
        rel: (counts[rel], floor)
        for rel, floor in floors.items()
        if rel in counts and counts[rel] < floor
    }
    assert not below, (
        "a chapter lost anchors — re-anchor the claim, do not lower the floor: "
        f"{below}"
    )

    pinned_but_gone = sorted(rel for rel in floors if rel not in counts)
    assert not pinned_but_gone, (
        f"floors pinned for chapters that no longer exist: {pinned_but_gone}"
    )


def test_the_architect_material_is_actually_covered(check_module) -> None:
    """A control on the gate's own reach, not on the prose.

    ``scan()`` covering both roots is the property this asserts. Without it the
    architect material would sit beside a green gate that never opened it — and
    a chapter absent from the denominator is indistinguishable, in the output,
    from a chapter with nothing wrong.
    """
    counts, _ = check_module.scan()
    coc_keys = [k for k in counts if k.startswith("coc/")]
    assert coc_keys, (
        "scan() returned no coc/ chapters; the architect material is outside the "
        "gate's reach and its anchors are ungoverned"
    )
    assert sum(counts[k] for k in coc_keys) > 0, (
        "the coc/ chapters are scanned but carry zero anchors between them — the "
        "gate is reaching them and finding nothing to check"
    )
