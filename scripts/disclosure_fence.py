#!/usr/bin/env python3
"""Partner-name disclosure fence — nothing distributed from here names a client.

WHY THIS EXISTS
---------------
This repository is handed to architects at partner organisations, some of whom
work for firms that compete with each other. A client's identity rendered into
a handbook screenshot, a persona, a fixture or a comment therefore discloses a
commercial relationship to a third party. That is a confidentiality defect, not
an aesthetic one, and it has happened: a seeded demo persona carried a real
client's name in a greeting, a sidebar identity, and the alt text beside them.

NO CLIENT IS NAMED IN THIS FILE, DELIBERATELY
---------------------------------------------
A denylist of confidential tokens, committed to a repository built for external
distribution, IS the disclosure it exists to prevent. Writing the names here
would leak them to every reader of the fence — including the fence's own
findings output. So every token is supplied from OUTSIDE the tree at run time,
and every finding is printed with the token REDACTED, which makes this script's
output safe to paste into a ticket, a PR, or a chat window.

That constraint is the whole design problem. This repository has no
``.gitmodules`` and no client mount, so unlike the platform's own fence it has
no token source of its own to derive from. It must be given one.

THE TOKEN SOURCES, AND WHY MORE THAN ONE
----------------------------------------
Resolved in order; the first that yields tokens wins::

    1. AEGIS_PARTNER_TOKENS   comma/whitespace-separated, straight from the env
    2. .partner-tokens.local  a gitignored file at the repository root
    3. AEGIS_PLATFORM_REPO    a checkout of the platform repository, from which
                              tokens are DERIVED the way the platform's own
                              fence derives them: the ``.gitmodules`` mount
                              paths, the ``.gitmodules`` URLs (and the owner/repo
                              and bare repository name inside them), and the
                              directory entries under the client mount — three
                              independent derivations, so losing one does not
                              silently empty the set.

FAIL CLOSED, AND THE DISTINCTION THAT MATTERS MOST
--------------------------------------------------
A fence whose token list silently empties prints exactly what a clean tree
prints. That single property is what makes a disclosure fence trustworthy or
useless, so the two are never collapsed here:

    exit 0  CLEAN            tokens were loaded AND nothing matched
    exit 2  FINDINGS         at least one file names a client
    exit 3  NO-TOKEN-SOURCE  no source was configured — NOT a pass
    exit 4  EMPTY-TOKEN-SET  a source resolved but produced no tokens — NOT a pass

Exit 1 is deliberately unused: an uncaught exception exits 1, and if that shared
a code with a verdict, a crash would masquerade as an answer.

WHAT THIS CANNOT CATCH — stated plainly, because a gate that oversells its reach
is worse than no gate
-------------------------------------------------------------------------------
  * **IT CANNOT READ PIXELS, AND THAT IS THE ORIGINATING DEFECT'S OWN HIDING
    PLACE.** The incident that motivated this fence put a client's name in the
    rendered text of two PNGs. ``grep`` cannot see that, and neither can this.
    A GREEN RUN SAYS NOTHING ABOUT WHAT IS RENDERED INSIDE AN IMAGE. Every run
    therefore reports how many binary files it skipped, so the size of that
    blind spot is visible at the bottom of every clean result instead of being
    something a reader has to already know. Screenshots must be reviewed by
    LOOKING at them.
  * **IT GUARDS THIS BOUNDARY ONLY, AND THE UPSTREAM ONE IS OPEN.** This
    material originates in the platform repository and is copied here. The
    platform's capture-time de-sensitisation gate checks the rendered DOM for a
    loopback URL, a production hostname, a non-reserved email domain and a
    JWT-shaped token — it has **no name predicate at all**, which is why it
    passed the images that caused this. So a fresh capture run re-emits the
    same disclosure, and this fence is the LAST checkpoint rather than the
    first. It catches a re-introduced name on the way out; it cannot stop one
    being produced. The durable fix is a name predicate at the capture step,
    and it does not live in this repository.
  * **IT ONLY KNOWS THE TOKENS IT IS GIVEN.** A client absent from the
    configured source is invisible. The platform derivation (source 3) is the
    only one that stays current on its own.
  * **IT MATCHES IDENTIFIER SEGMENTS, NOT MEANING.** A client described but not
    named — "the big four firm we onboarded in March" — passes cleanly.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXIT_CLEAN = 0
EXIT_FINDINGS = 2
EXIT_NO_SOURCE = 3
EXIT_EMPTY_SET = 4

LOCAL_TOKEN_FILE = ".partner-tokens.local"

# The mount under which the platform keeps its client directories. A PATH, not a
# client name, so naming it here discloses nothing.
PLATFORM_CLIENT_MOUNT = "deploy/clients"

# Scaffolding under that mount that names no client and must not be read as one.
PLATFORM_TEMPLATE_DIR = "_template"

# A token is a disclosure when it is a whole SEGMENT of the identifier it sits
# in. These end a segment. `_` is included even though it is a `\w` character,
# which is exactly why the boundary cannot be spelled `\b`.
SEGMENT_DELIMITERS = "-_./"

# There is deliberately NO minimum token length, and the omission is the design.
# A length floor would silently drop the SHORT client slugs — and dropping a
# client to quieten the fence is the exact inversion of what it is for. The
# delimiter-anchored form below is what makes a short slug safe: it matches a
# whole segment, never a substring, so a 3-letter slug cannot match inside an
# ordinary word. A short slug that still collides is a weakness in the TOKEN,
# not in the fence, and the honest fix is a better token upstream.


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


# --------------------------------------------------------------------------
# Token sources
# --------------------------------------------------------------------------


def _split_tokens(raw: str) -> set[str]:
    return {t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()}


def _from_platform_checkout(root: Path) -> set[str]:
    """Derive from a platform checkout, three independent ways."""
    tokens: set[str] = set()

    gitmodules = ""
    try:
        gitmodules = _git("show", "HEAD:.gitmodules", cwd=root)
    except RuntimeError:
        pass  # a platform checkout with no clients yet is a legitimate state

    for raw in re.findall(r"^\s*path\s*=\s*(\S+)", gitmodules, re.M):
        slug = raw.rstrip("/").rsplit("/", 1)[-1]
        if slug and slug != PLATFORM_TEMPLATE_DIR:
            tokens.add(slug)

    for url in re.findall(r"^\s*url\s*=\s*(\S+)", gitmodules, re.M):
        tokens.add(url)
        repo = url.rstrip("/").rsplit("/", 1)[-1]
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        if repo:
            tokens.add(repo)
        m = re.search(r"[:/]([^/:]+/[^/:]+?)(?:\.git)?$", url)
        if m:
            tokens.add(m.group(1))

    try:
        listing = _git("ls-tree", f"HEAD:{PLATFORM_CLIENT_MOUNT}", cwd=root)
    except RuntimeError:
        listing = ""
    for line in listing.splitlines():
        name = line.split("\t", 1)[-1].strip()
        if name and name != PLATFORM_TEMPLATE_DIR:
            tokens.add(name)

    return tokens


def load_tokens() -> tuple[set[str], str]:
    """Return (tokens, source-description). Empty set means the source failed."""
    raw = os.environ.get("AEGIS_PARTNER_TOKENS", "")
    if raw.strip():
        return _split_tokens(raw), "AEGIS_PARTNER_TOKENS"

    local = REPO / LOCAL_TOKEN_FILE
    if local.is_file():
        lines = [
            ln.split("#", 1)[0]
            for ln in local.read_text(encoding="utf-8", errors="replace").splitlines()
        ]
        return _split_tokens(" ".join(lines)), LOCAL_TOKEN_FILE

    platform = os.environ.get("AEGIS_PLATFORM_REPO", "")
    if platform.strip():
        root = Path(platform).expanduser().resolve()
        if not (root / ".git").exists():
            raise RuntimeError(f"AEGIS_PLATFORM_REPO is not a git checkout: {root}")
        return _from_platform_checkout(root), f"AEGIS_PLATFORM_REPO={root}"

    return set(), ""


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def token_regex(token: str) -> re.Pattern[str]:
    """Match the token as a whole segment of the identifier it sits in."""
    # Anchored on alphanumerics, NOT on `\b`: every character in
    # SEGMENT_DELIMITERS must be allowed to sit beside the token, and `_` is a
    # word character, so `\b` would refuse `foo_<token>` — a real disclosure
    # shape. Anchoring on [A-Za-z0-9] admits every delimiter at once.
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", re.IGNORECASE
    )


def redact(line: str, matches: list[re.Match[str]]) -> str:
    """Rebuild the line with every matched token replaced by a placeholder.

    This is what makes the fence's own output safe to paste anywhere.
    """
    out, last = [], 0
    for m in matches:
        out.append(line[last : m.start()])
        out.append("<client-token>")
        last = m.end()
    out.append(line[last:])
    return "".join(out).strip()[:200]


def main() -> int:
    try:
        tokens, source = load_tokens()
    except RuntimeError as exc:
        print(f"NO-TOKEN-SOURCE: {exc}", file=sys.stderr)
        return EXIT_NO_SOURCE

    if not source:
        print(
            "NO-TOKEN-SOURCE: no client-token source is configured.\n"
            "  This is NOT a clean result — the fence did not run.\n"
            f"  Set AEGIS_PARTNER_TOKENS, or write {LOCAL_TOKEN_FILE} (gitignored),\n"
            "  or set AEGIS_PLATFORM_REPO to a platform checkout to derive them.",
            file=sys.stderr,
        )
        return EXIT_NO_SOURCE

    if not tokens:
        print(
            f"EMPTY-TOKEN-SET: source '{source}' resolved but yielded no tokens.\n"
            "  This is NOT a clean result — a silently-emptied list would print\n"
            "  exactly what a clean tree prints, which is the one failure this\n"
            "  fence exists to make impossible.",
            file=sys.stderr,
        )
        return EXIT_EMPTY_SET

    patterns = [(t, token_regex(t)) for t in sorted(tokens)]

    files = [f for f in _git("ls-files", "-z", cwd=REPO).split("\0") if f]
    findings: list[str] = []
    skipped_binary = 0
    scanned = 0

    for rel in files:
        path = REPO / rel
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            skipped_binary += 1
            continue
        scanned += 1
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            hits = [m for _, rx in patterns for m in rx.finditer(line)]
            if hits:
                hits.sort(key=lambda m: m.start())
                findings.append(f"  {rel}:{lineno}: {redact(line, hits)}")

    print(f"token source : {source}")
    print(f"tokens loaded: {len(tokens)} (values withheld by design)")
    print(f"files scanned: {scanned} text, {skipped_binary} binary SKIPPED")

    if findings:
        print(f"\nFINDINGS: {len(findings)} line(s) name a client\n", file=sys.stderr)
        for f in findings:
            print(f, file=sys.stderr)
        print(
            "\n  Tokens above are redacted so this output is safe to share.",
            file=sys.stderr,
        )
        return EXIT_FINDINGS

    print(
        f"\nCLEAN — no tracked TEXT file names a client.\n"
        f"  ⚠ This says NOTHING about the {skipped_binary} binary files skipped.\n"
        f"    Text rendered inside a screenshot is invisible here and must be\n"
        f"    checked by looking at the image."
    )
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
