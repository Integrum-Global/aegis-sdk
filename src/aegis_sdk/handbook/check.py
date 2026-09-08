"""Anchor gate for the SDK-shipped handbook — the replacement for citation drift.

WHY THIS EXISTS
---------------
The handbook was kept honest by ``path:line`` citations into the private core
package, adjudicated by a drift gate that re-read the cited lines. That
mechanism cannot travel. The parts shipped here are written for architects,
operators, developers and users, and the whole reason they ship with the SDK is
that **those readers are not given the core codebase**. A citation into a tree
the reader cannot open is simultaneously useless to them and a disclosure.

So the anchoring moves from *source coordinates* to *observable surface*: every
load-bearing claim names something the reader can resolve from what they were
actually given. Two anchor kinds, both checkable **from inside this package**:

    `api:POST /api/v1/trust/establish`   an HTTP operation this client performs
    `sdk:aegis_sdk.TrustChain`           a public symbol this package exports

TWO ROOTS, ONE GATE
-------------------
The architect working material under ``aegis_sdk/coc/`` ships to the same reader
and makes the same kind of claim, so it is gated here rather than trusted
because it is shorter. Its floor keys are prefixed ``coc/``. Both roots are
excluded from the operation DERIVATION for the same reason: prose about the
client is not a call site of it, and counting its literals would let a file
satisfy its own anchors.

THE PROPERTY THAT MATTERS MOST, AND IT IS NOT DRIFT DETECTION
-------------------------------------------------------------
The old gate ran in core. Its audience could never run it, so from their side
the handbook's honesty was an assertion. This gate **ships with the thing it
checks**::

    python -m aegis_sdk.handbook.check

A reader handed the SDK can verify, on their own machine, that every claim in
their handbook still names a surface this build actually has. That is a
capability the citation gate never had, and it is the one real gain in the
trade.

WHAT THIS CANNOT CATCH — stated plainly, because a gate that oversells its
reach is a worse defect than no gate
--------------------------------------------------------------------------
  * **EXISTENCE IS NOT BEHAVIOUR, AND THIS IS THE BIG ONE.** A resolving
    ``api:`` anchor proves this client declares that operation. It does NOT
    prove the server enforces anything on it, returns the status the prose
    claims, or checks a permission. The citation it replaced could point at the
    ``raise``; an anchor structurally cannot. **A control that silently stopped
    enforcing looks identical to one that never stopped.**
  * **IT CANNOT SEE FAIL-OPEN.** Precisely the class the handbook's Enforcement
    Ledger exists to record. That is why the ledger's verdicts are NOT anchored
    this way — they stay bound to the citation-backed core copy by a separate
    verdict-parity test, and this module is deliberately not that test.
  * **THE ROUTE TABLE IS THIS CLIENT'S BELIEF ABOUT THE API, NOT THE API.** It
    is extracted from this package's own call sites. If the client is wrong
    about a path, the anchor is wrong in exactly the same direction and nothing
    here notices. An OpenAPI document emitted by the server would be a stronger
    anchor; it is not available offline to this package's audience, which is
    the whole constraint.
  * **NO LINE-LEVEL RESOLUTION.** There are no line coordinates to drift, which
    removes the false-positive class the old gate spent most of its docstring
    on — and removes the true positives with it.
  * **IT SAYS NOTHING ABOUT DISCLOSURE.** Core-path leakage on this surface is
    covered by the core-side pre-export gate. Reimplementing it here would be a
    second mechanism for one property, which this repo has already retired once.
  * **THE FLOOR COUNTS ANCHORS, NOT CLAIMS.** A chapter can satisfy its floor
    and still contain an unanchored assertion. The floor stops wholesale
    un-grounding; it does not prove any particular sentence is grounded.

THE FLOOR ONLY RISES
--------------------
``anchors.json`` pins a per-chapter minimum. Falling below it fails. This is the
opposite polarity from a disclosure baseline and deliberately so: the failure
mode being fenced is **deleting a claim to make a gate pass**, so the ratchet
has to make removal expensive rather than addition expensive. Raising a floor
is free (``--sync``); lowering one is a diff a reviewer has to justify.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

HANDBOOK = Path(__file__).resolve().parent
PACKAGE_ROOT = HANDBOOK.parent
FLOOR_PATH = HANDBOOK / "anchors.json"

#: The architect working material ships beside the handbook and makes the same
#: kind of claim, so it is gated the same way rather than being trusted because
#: it is shorter.
COC = PACKAGE_ROOT / "coc"
COC_FLOOR_PATH = COC / "anchors.json"

#: Roots whose ``.md`` files are anchor-checked: ``(root, floor-key base, floor
#: file)``.
#:
#: EACH ROOT OWNS ITS OWN FLOOR FILE, and that is not tidiness — it is the fix
#: for a measured collision. Both roots are authored by different people at the
#: same time; when they shared one file, a wholesale key rename on one side and
#: an addition on the other produced a textual conflict AND, if resolved
#: carelessly, a set of stale keys each reporting "floor pinned but the chapter
#: is gone". Separate files make the two edits disjoint by construction.
#:
#: Keys keep their base-relative prefix (``coc/…``) even though the file is no
#: longer shared, so a key still says which root it belongs to if the files are
#: ever read together or merged back.
_PROSE_ROOTS: tuple[tuple[Path, Path, Path], ...] = (
    (HANDBOOK, HANDBOOK, FLOOR_PATH),
    (COC, PACKAGE_ROOT, COC_FLOOR_PATH),
)

#: ``api:METHOD /path`` or ``sdk:dotted.name``, inside backticks.
ANCHOR = re.compile(r"`(api|sdk):([^`]+)`")

#: A markdown link to another chapter: ``[text](../part/chapter.md)``. Only
#: ``.md`` targets are checked — an ``http(s)`` link cannot be resolved offline,
#: and an asset link is the screenshot-binding gate's question, not this one.
MD_LINK = re.compile(r"\]\(([^)\s]+\.md)(?:#[^)]*)?\)")

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

#: Path parameters differ in spelling between a call site and a chapter
#: (``{chain_id}`` vs ``{id}``); the *shape* is what is being anchored.
_PARAM = re.compile(r"\{[^}]*\}")


def normalise_path(path: str) -> str:
    return _PARAM.sub("{}", path.strip().rstrip("/")) or "/"


# ───────────────────────────── the resolvable surfaces ───────────────────────


def _string_of(node: ast.AST) -> str | None:
    """A literal string, or an f-string reduced to its ``{}`` shape.

    Returns None for anything whose text is not knowable statically — a bare
    name, a call, a concatenation with a variable. Those are skipped rather than
    guessed: a guessed route would make the anchor set LARGER than the truth,
    which is the direction that turns a gate into a rubber stamp.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            elif isinstance(part, ast.FormattedValue):
                out.append("{}")
            else:
                return None
        return "".join(out)
    return None


def declared_operations(package_root: Path = PACKAGE_ROOT) -> set[tuple[str, str]]:
    """``(METHOD, normalised path)`` for every HTTP call this package makes.

    Derived by parsing the package, never hand-listed — a hand-written route
    list is the defect, because it drifts the moment a module adds a call and
    then reports a clean sweep the client would not agree with.
    """
    found: set[tuple[str, str]] = set()
    for py in sorted(package_root.rglob("*.py")):
        # The handbook and the architect material are ABOUT the client; they are
        # not call sites of it. Counting their literals would let a file satisfy
        # its own anchors, which is the direction that turns a gate into a
        # rubber stamp — the same reason a route whose text is not statically
        # knowable is skipped rather than guessed.
        if py.is_relative_to(HANDBOOK) or py.is_relative_to(COC):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            args = [a for a in node.args if not isinstance(a, ast.Starred)]
            texts = [_string_of(a) for a in args]
            for i in range(len(texts) - 1):
                method, path = texts[i], texts[i + 1]
                if method in _HTTP_METHODS and path and path.startswith("/"):
                    found.add((method, normalise_path(path)))
    return found


def _resolves_as_symbol(dotted: str) -> bool:
    """Walk ``aegis_sdk.a.b.C.method`` by import then getattr.

    An import failure is a FAILURE to resolve, never a pass. A gate that treats
    an unimportable module as "probably fine" reports silence it did not earn.
    """
    if dotted != "aegis_sdk" and not dotted.startswith("aegis_sdk."):
        return False
    parts = dotted.split(".")
    module = None
    rest: list[str] = []
    for i in range(len(parts), 0, -1):
        try:
            module = __import__(".".join(parts[:i]), fromlist=["_"])
        except Exception:
            continue
        rest = parts[i:]
        break
    if module is None:
        return False
    obj: object = module
    for attr in rest:
        try:
            obj = getattr(obj, attr)
        except AttributeError:
            return False
    return True


# ───────────────────────────────── the checks ────────────────────────────────


def chapters(root: Path = HANDBOOK) -> list[Path]:
    return sorted(root.rglob("*.md"))


def broken_links(
    roots: tuple[tuple[Path, Path, Path], ...] | None = None,
) -> tuple[int, int, list[str]]:
    """``(files walked, links checked, findings)`` across every prose root.

    TWO DENOMINATORS ARE RETURNED, NOT ONE, AND THE SECOND IS NOT ENOUGH ON ITS
    OWN. A link checker reporting "0 broken" is indistinguishable from one that
    found no links to check — and there are THREE ways to reach that, which one
    number cannot separate:

      * the walk found no files at all — a root that does not resolve, or a
        glob that matches nothing. The wiring is broken.
      * files were walked and contain no markdown links — a tree that
        cross-references by backticked path instead. Legitimate, and vacuous.
      * links were found and every one was filtered out before comparison.

    ``files`` separates the first from the other two; ``checked`` separates the
    rest. This function filters twice between walking and comparing — ``MD_LINK``
    matches only ``.md`` targets, and external schemes are skipped — so
    ``checked`` is an ELIGIBLE count, never a found count, and reporting it alone
    would have hidden the first case entirely.

    None of this is hypothetical. The companion prose tree had exactly zero
    markdown links when it was first offered as a second root; wiring it in then
    would have installed a permanently-vacuous check inside the gate built to
    stop unresolvable references.

    POLARITY, stated because it differs from the companion probe deliberately: a
    root that walks ZERO FILES is a finding, because a declared root resolving to
    nothing is a wiring error. A root with files but zero links is NOT a finding
    — a prose tree with no cross-references is unhelpful, not broken — so it is
    made visible in the counts and left to the reader's judgement.

    WHY THIS IS HERE and not left to a reader noticing a 404: this handbook was
    renumbered as a standalone book, and a renumbering breaks links silently —
    every one of them still *looks* right. The anchor checks above cannot see a
    link at all, so without this a chapter could point at a part that does not
    ship and nothing would say so. Measured at the time this was added: one such
    link was already live, into a part that had never crossed into this tree.

    It reads ``_PROSE_ROOTS`` — the SAME registry the anchor floors derive from —
    rather than keeping a second list of its own. Two registries for one property
    is how a root gets link-checked and not floor-checked, or the reverse, with
    nothing to say which is the mistake.

    It resolves ONLY relative ``.md`` targets, and that boundary is deliberate.
    An ``http`` link cannot be resolved offline, which is the constraint this
    whole module lives under; an image or asset link is the screenshot-binding
    gate's question and re-answering it here would be a second mechanism for one
    property.

    A target is resolved against the FILESYSTEM, not against the set of chapters
    this gate knows about — so a link that leaves its own root and lands on a
    real file in another one resolves, which is correct: the reader can follow
    it. Only a link to nothing is a finding.
    """
    files = 0
    checked = 0
    problems: list[str] = []
    for root, base, _floor in roots if roots is not None else _PROSE_ROOTS:
        in_root = 0
        for md in chapters(root):
            in_root += 1
            rel = md.relative_to(base).as_posix()
            text = md.read_text(encoding="utf-8", errors="replace")
            for target in MD_LINK.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                checked += 1
                if not (md.parent / target).resolve().is_file():
                    problems.append(f"{rel}: broken link -> {target}")
        if in_root == 0:
            problems.append(
                f"{root.name}: prose root walked ZERO files — it does not "
                "resolve, or holds no .md. Nothing here is being checked."
            )
        files += in_root
    return files, checked, problems


def _gated_prose() -> list[tuple[str, Path]]:
    """``(floor key, file)`` for every gated markdown file across both roots."""
    out: list[tuple[str, Path]] = []
    for root, base, _floor in _PROSE_ROOTS:
        if not root.exists():
            continue
        for md in chapters(root):
            out.append((md.relative_to(base).as_posix(), md))
    return sorted(out)


def _load_floors(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("floors", {})


def _keys_for(root: Path, base: Path) -> set[str]:
    """The floor keys a given root owns, derived from the tree.

    Derived rather than inferred from a prefix: a prefix test would silently
    mis-file a key if a root ever moved, and the point of splitting the files is
    that each one contains exactly its own root's keys.
    """
    if not root.exists():
        return set()
    return {md.relative_to(base).as_posix() for md in chapters(root)}


def scan(root: Path | None = None) -> tuple[dict[str, int], list[str]]:
    """``(per-chapter anchor counts, unresolved-anchor findings)``.

    ``root`` narrows the scan to one tree, for a caller that wants only the
    handbook. The default covers every gated root — a default that covered only
    one would silently exempt the other the moment it was added.
    """
    ops = declared_operations()
    counts: dict[str, int] = {}
    problems: list[str] = []
    files = (
        [(md.relative_to(root).as_posix(), md) for md in chapters(root)]
        if root is not None
        else _gated_prose()
    )
    for rel, md in files:
        text = md.read_text(encoding="utf-8", errors="replace")
        # Whitespace-normalised: prose here wraps at ~80 columns, and an anchor
        # split across a newline is invisible to a line-oriented match. This
        # repo already carries that scar in its liability-framing scan.
        norm = re.sub(r"\s+", " ", text)
        n = 0
        for kind, body in ANCHOR.findall(norm):
            n += 1
            if kind == "api":
                bits = body.split(None, 1)
                if len(bits) != 2 or bits[0] not in _HTTP_METHODS:
                    problems.append(f"{rel}: malformed api anchor `api:{body}`")
                    continue
                if (bits[0], normalise_path(bits[1])) not in ops:
                    problems.append(f"{rel}: `api:{body}` — this client declares no such operation")
            elif not _resolves_as_symbol(body.strip()):
                problems.append(f"{rel}: `sdk:{body}` — not a symbol this package exports")
        counts[rel] = n
    return counts, problems


_RATCHET_DOC = [
    "It only RISES. Falling below a floor fails the gate: the failure mode being",
    "fenced is deleting a claim to make a gate pass, so removal is what has to be",
    "expensive. See check.py for what this gate structurally cannot catch.",
]

#: Per-root header, so a `--sync` of one root does not rewrite the other's file.
#: The handbook's line is preserved VERBATIM from before the roots were split —
#: rewriting it would have made every sync a diff against a file another author
#: is renaming wholesale, which is the collision this split exists to end.
_FLOOR_DOC_BY_ROOT: dict[str, list[str]] = {
    "handbook": ["Per-chapter MINIMUM anchor count for the SDK-shipped handbook.", *_RATCHET_DOC],
    "coc": [
        "Per-chapter MINIMUM anchor count for the architect working material.",
        "Keys keep their `coc/` prefix so a key still names its root if these",
        "files are ever read together.",
        *_RATCHET_DOC,
    ],
}


def check(sync: bool = False) -> int:
    counts, problems = scan()
    link_files, links_checked, links = broken_links()
    floors: dict[str, int] = {}
    for _root, _base, floor_path in _PROSE_ROOTS:
        floors.update(_load_floors(floor_path))

    if sync:
        total = 0
        for root, base, floor_path in _PROSE_ROOTS:
            owned = _keys_for(root, base)
            if not owned:
                continue
            existing = _load_floors(floor_path)
            merged = {k: max(counts.get(k, 0), existing.get(k, 0)) for k in owned}
            doc = _FLOOR_DOC_BY_ROOT[root.name]
            payload = {"_doc": doc, "floors": dict(sorted(merged.items()))}
            floor_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"synced {len(merged)} floor(s) -> {floor_path.relative_to(PACKAGE_ROOT)}")
            total += len(merged)
        if not total:
            print("nothing to sync — no gated prose found")
        return 0

    for rel, floor in sorted(floors.items()):
        if rel not in counts:
            problems.append(f"{rel}: floor pinned but the chapter is gone — prune it (--sync)")
        elif counts[rel] < floor:
            problems.append(
                f"{rel}: {counts[rel]} anchor(s), floor is {floor} — a claim lost its"
                " grounding. Re-anchor it; do not lower the floor."
            )

    problems.extend(links)

    print(f"chapters          : {len(counts)}")
    print(f"anchors           : {sum(counts.values())}")
    print(f"declared ops      : {len(declared_operations())}")
    print(f"links checked     : {links_checked} (across {link_files} file(s))")
    print(f"broken links      : {len(links)}")
    if problems:
        print(f"\nFAIL: {len(problems)} finding(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    print("\nOK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Anchor gate for the shipped handbook.")
    ap.add_argument("--sync", action="store_true", help="raise floors to the current counts")
    return check(sync=ap.parse_args(argv).sync)


if __name__ == "__main__":
    sys.exit(main())
