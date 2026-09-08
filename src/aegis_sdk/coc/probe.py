"""Credential-reachability and transport-honesty probe for a deployed platform.

WHY THIS EXISTS
---------------
The handbook records that an API key cannot reach a persona-gated route, that no
scope configuration changes that, and then marks the *size* of that surface
**UNVERIFIED** — three different counting units give three different numbers and
the route-level enumeration had not been done.

It could not be done there, and that is worth saying plainly rather than
treating as an omission. A route-level enumeration derived from the platform's
own source would be a list you cannot open, checked by a gate you cannot run,
about a build that is not necessarily the one you were given. It would be an
assertion with a decoration on it.

So this probe answers the same question from the other side: it asks **your**
deployment, with **your** credentials, and reports the routes where the two
disagree. That answer is narrower than the source-derived one — it covers only
what this client declares and only what is safe to call — and it is an answer
you obtained yourself, about the system you actually have.

WHAT IT DOES
------------
1. Derives the operation set from this package's own call sites, reusing the
   handbook checker's derivation. Never a hand-written list: a hand-written list
   drifts the moment a module adds a call and then reports a clean sweep the
   client would not agree with.
2. Keeps only ``GET`` operations with **no path parameters** — the subset that is
   safe to call blind and deterministic to interpret. A probe that mutates the
   deployment it is measuring is not a probe.
3. Calls each one with each credential you supplied, and classifies the pair.

THE POSITIVE CONTROL, WHICH IS THE PART THAT MAKES THE ZERO MEAN ANYTHING
-------------------------------------------------------------------------
An expired token and a perfectly reachable API produce the same output from a
naive version of this: everything refused, nothing to report, exit clean. So
before any count is printed, each credential must authenticate. If either does
not, the run reports **UNDETERMINED** and exits ``3`` — never ``0``.

Name the falsifying result before you cite a run of this as evidence. For "this
route family is reachable by my key" the falsifying result is a ``KEY-DENIED``
row for that family. If no result this probe could have produced would have
falsified what you are about to claim, it is not evidence for that claim.

WHAT THIS CANNOT CATCH — stated plainly, because a probe that oversells its
reach is worse than no probe
-------------------------------------------------------------------------
  * **IT ONLY SEES WHAT THIS CLIENT DECLARES.** The denominator is this
    package's belief about the API, not the API. A route no module here calls is
    invisible, and if the client is wrong about a path the probe is wrong in
    exactly the same direction.
  * **IT ONLY PROBES PARAMETER-FREE GETs.** Every mutating route and every
    ``/{id}`` route is out of scope by construction. The reachability posture of
    a write is frequently different from the read beside it, and this cannot see
    that difference.
  * **A 404 IS AMBIGUOUS.** Route absent, resource absent, and route present but
    tenant-scoped to nothing look identical from here. Those rows are reported
    separately and are not counted as reachable or as denied.
  * **IT CANNOT SEE FAIL-OPEN.** A route that admits you when it should not
    returns ``200`` and this records ``200``. The whole class where a control
    stopped enforcing is invisible to a reachability probe, in both directions.
  * **REACHABLE IS NOT CORRECT.** A ``200`` proves you were admitted. It proves
    nothing about whether the body is right, whether tenancy was applied, or
    whether anything was recorded.
  * **THE TRANSPORT SCAN IS A SOURCE SCAN, NOT A RUNTIME ONE.** It reads the
    installed package. A module that reaches the network by a shape it does not
    recognise is missed, and it says nothing about whether the server is real.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

#: The one operation both credentials must satisfy before any zero is printed.
CONTROL_PATH = "/api/v1/auth/me"

#: Exit codes. ``3`` exists so that "could not tell" is never spelled ``0``.
EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE, EXIT_UNDETERMINED = 0, 1, 2, 3


# ─────────────────────────────── the denominator ──────────────────────────────


def probeable_operations() -> list[str]:
    """Parameter-free ``GET`` paths this client declares, sorted.

    Reuses the handbook checker's AST derivation rather than re-deriving it. Two
    derivations of one fact drift, and the drift is silent — this repo's own
    gates record that shape more than once.
    """
    from aegis_sdk.handbook.check import declared_operations

    return sorted(
        path
        for method, path in declared_operations()
        if method == "GET" and "{}" not in path
    )


# ───────────────────────────── the transport scan ─────────────────────────────


#: Libraries through which this package could actually reach a network. A module
#: importing none of them cannot be performing HTTP, whatever its methods claim.
_HTTP_LIBRARIES = frozenset(
    {"httpx", "aiohttp", "requests", "urllib3", "urllib", "http", "websockets"}
)


def _imports_http(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] in _HTTP_LIBRARIES for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _HTTP_LIBRARIES:
                return True
    return False


def _is_transport_name(name: str) -> bool:
    """A method that carries a request to a server, not a hook that observes one.

    ``on_request`` is the case this excludes and the reason the test is not a
    substring match: a plugin hook named for the request it is *told about* was
    the first thing an earlier version of this flagged, while missing the real
    stub entirely. Both errors came from the same loose matcher.
    """
    if name.startswith("on_"):
        return False
    return name.lstrip("_") in {"request", "send"} or name.endswith(
        ("_request", "_transport", "_send")
    )


def simulated_transports(package_root: Path = PACKAGE_ROOT) -> tuple[int, int, list[str]]:
    """``(files parsed, files eligible, findings)`` — the denominator is returned.

    **The counts are not decoration and they are not merely printed.** ``no
    findings`` reads identically whether this walked 144 files or zero, so a
    wrong root, a failed glob or a package that would not parse all report the
    same clean result as a healthy scan. Returning the denominator is what lets
    a caller — including :func:`main` below — tell "nothing is wrong" from
    "nothing was examined", which are the two branches of the question this
    scan exists to answer.

    ``eligible`` is reported separately from ``parsed`` because the HTTP-import
    filter is the third way this goes quiet: if it excluded every file, the scan
    ran, examined nothing, and would still print zero.

    Transport methods that fabricate a response instead of performing one.

    Flagged on the CONJUNCTION of three conditions, each of which is wrong alone:

      1. the method is named like a transport (not like a hook);
      2. its **module imports no HTTP library at all** — the discriminating one,
         because a module that cannot reach a network is not reaching one
         whatever its method names promise;
      3. it returns a non-``None`` literal — i.e. it hands back a fabricated
         body, as opposed to an abstract method that returns nothing.

    Why this matters more than it looks: a fabricated response is indistinguish-
    able from a real one at the call site. The caller gets a populated object and
    a success status, having touched no network, and nothing in the type, the
    docstring or the ``__all__`` says so.

    Known limit, stated because the first version of this was wrong in both
    directions at once: a module that imports an HTTP library and *still* stubs
    one method is missed. Condition 2 buys precision and costs exactly that.
    """
    findings: list[str] = []
    parsed = 0
    eligible = 0
    for py in sorted(package_root.rglob("*.py")):
        if py.name == "probe.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        parsed += 1
        if _imports_http(tree):
            continue
        eligible += 1
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_transport_name(node.name):
                continue
            fabricates = any(
                isinstance(r, ast.Return)
                and (
                    isinstance(r.value, (ast.Dict, ast.List))
                    or (isinstance(r.value, ast.Constant) and r.value.value is not None)
                )
                for r in ast.walk(node)
            )
            if fabricates:
                rel = py.relative_to(package_root.parent).as_posix()
                findings.append(f"{rel}::{node.name} (line {node.lineno})")
    return parsed, eligible, findings


# ─────────────────────────────── the live probe ───────────────────────────────


async def _status(client: object, base_url: str, path: str, header: dict) -> int:
    import httpx

    assert isinstance(client, httpx.AsyncClient)
    try:
        r = await client.get(base_url.rstrip("/") + path, headers=header, timeout=20.0)
        return r.status_code
    except Exception:
        return -1


async def run_probe(base_url: str, api_key: str | None, token: str | None) -> int:
    import httpx

    creds: dict[str, dict] = {}
    if api_key:
        creds["key"] = {"X-API-Key": api_key}
    if token:
        creds["session"] = {"Authorization": f"Bearer {token}"}
    if not creds:
        print("UNDETERMINED: supply --api-key, --token, or both.", file=sys.stderr)
        return EXIT_USAGE

    paths = probeable_operations()
    print(f"base url          : {base_url}")
    print(f"credentials       : {', '.join(sorted(creds))}")
    print(f"probeable GETs    : {len(paths)}")

    async with httpx.AsyncClient(follow_redirects=False) as http:
        # ── positive control, before anything is counted ──────────────────────
        control: dict[str, int] = {}
        for name, header in creds.items():
            control[name] = await _status(http, base_url, CONTROL_PATH, header)
        bad = {n: s for n, s in control.items() if s != 200}
        if bad:
            print(f"\nUNDETERMINED: control {CONTROL_PATH} did not return 200 for: {bad}")
            print("A credential that cannot authenticate refuses everything, which is")
            print("byte-identical to a deployment that denies everything. No count is")
            print("printed, because none would mean anything.")
            return EXIT_UNDETERMINED
        print(f"control           : {CONTROL_PATH} -> 200 for every credential")

        results: dict[str, dict[str, int]] = {}
        for path in paths:
            results[path] = {
                name: await _status(http, base_url, path, header)
                for name, header in creds.items()
            }

    if len(creds) < 2:
        only = next(iter(creds))
        denied = sorted(p for p, r in results.items() if r[only] == 403)
        print("\nONE CREDENTIAL ONLY — this answers a weaker question than the trap.")
        print(f"403 for the {only} credential: {len(denied)} of {len(paths)}")
        for p in denied:
            print(f"  403  {p}")
        print("\nWith one credential a 403 cannot be attributed. Supply both to")
        print("separate 'this credential type cannot reach it' from 'you lack a")
        print("permission', which is the distinction that decides what to do next.")
        return EXIT_FINDINGS if denied else EXIT_CLEAN

    trapped = sorted(
        p
        for p, r in results.items()
        if r.get("key") == 403 and r.get("session") in (200, 204)
    )
    both_ok = sum(1 for r in results.values() if r.get("key") in (200, 204))
    ambiguous = sorted(p for p, r in results.items() if 404 in r.values() or -1 in r.values())

    print(f"reachable by key  : {both_ok}")
    print(f"ambiguous (404/err): {len(ambiguous)}  — not counted either way")
    print(f"\nKEY-DENIED, SESSION-OK: {len(trapped)}")
    for p in trapped:
        print(f"  {p}")
    if trapped:
        print("\nEach row above is refused for your API key and served to your session.")
        print("Widening the key's scopes does not move any of them — scopes are not")
        print("consulted on that path — and it leaves you holding a more powerful")
        print("credential than the job needs. Use a session for these calls.")
    return EXIT_FINDINGS if trapped else EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", help="your deployment, e.g. https://aegis.example.com")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--token", default=None, help="a session bearer token")
    ap.add_argument(
        "--transports-only",
        action="store_true",
        help="run only the offline transport-honesty scan; no network, no credentials",
    )
    args = ap.parse_args(argv)

    parsed, eligible, stubs = simulated_transports()
    print(f"files parsed         : {parsed}")
    print(f"eligible (no HTTP lib): {eligible}")
    print(f"SIMULATED TRANSPORTS : {len(stubs)}")
    for s in stubs:
        print(f"  {s}")
    if stubs:
        print(
            "\nThese fabricate a response without performing a request. A call into\n"
            "one returns a populated object and a success status having touched no\n"
            "network. Treat any result obtained through them as unmeasured.\n"
        )

    # TWO ZEROS, TWO DIAGNOSES. Both refuse a clean exit, and collapsing them
    # into one message was a real defect: the remedy for an unresolved root is
    # not the remedy for a filter that ate everything, and printing the first
    # against the second sends the reader to check something that is fine.
    if parsed == 0:
        print(
            "\nUNDETERMINED: the scan parsed no files at all (parsed=0).\n"
            "The instrument was PREVENTED from measuring — a root that does not\n"
            "resolve, a glob that matched nothing, or a tree that would not parse.\n"
            "Check that the package root resolves.",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED
    if eligible == 0:
        print(
            f"\nUNDETERMINED: {parsed} file(s) parsed, none eligible (eligible=0).\n"
            "The walk RAN and the HTTP-import filter excluded every file, so the\n"
            "finding count says nothing about simulated transports — there were no\n"
            "candidates to examine.\n"
            "Non-zero deliberately: for a package whose purpose is an HTTP client,\n"
            "'every module can reach a network' is far more likely a broken filter\n"
            "than a true property. Check _HTTP_LIBRARIES before reading this as\n"
            "'no stubs'.",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED
    print()

    if args.transports_only:
        return EXIT_FINDINGS if stubs else EXIT_CLEAN
    if not args.base_url:
        print("UNDETERMINED: --base-url is required unless --transports-only.", file=sys.stderr)
        return EXIT_USAGE

    live = asyncio.run(run_probe(args.base_url, args.api_key, args.token))

    # UNDETERMINED OUTRANKS FINDINGS, and the order is the whole point.
    #
    # The previous roll-up was `EXIT_FINDINGS if (stubs or live == EXIT_FINDINGS)
    # else live`, which returns 1 whenever a stub was found — and this build
    # ALWAYS has one, so the live probe's UNDETERMINED could never reach the
    # caller. Four shipped documents tell an operator to key on 3, so an expired
    # token plus the known stub exited 1: byte-identical to a completed
    # measurement that found a trapped route.
    #
    # "I could not tell" and "I found something" answer different questions, and
    # collapsing the first into the second is the failure this probe exists to
    # warn about. So it is reported first, even though it means a real finding
    # can be reported in the same run as an unanswered question — the operator
    # needs to re-run either way, and the stub list is printed regardless.
    if live in (EXIT_UNDETERMINED, EXIT_USAGE):
        return live
    return EXIT_FINDINGS if (stubs or live == EXIT_FINDINGS) else live


if __name__ == "__main__":
    sys.exit(main())
