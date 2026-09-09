"""Resolve a list of anchors against this package. Reads JSON on stdin.

WHY THIS IS FOUR LINES OF LOGIC AND NOT A RESOLVER.

``anchor-integrity.js`` needs to know whether ``api:GET /api/v1/auth/me``
names an operation this client declares, and whether ``sdk:aegis_sdk.User``
names a symbol it exports. Both answers already exist, derived by AST walk and
by real import, in ``aegis_sdk.handbook.check``.

A second derivation of one fact drifts, and the drift is silent — this package's
own gates say so in three separate headers. So this file DERIVES NOTHING. It
imports the checker's functions and applies them. If the checker's derivation
changes, this changes with it, because there is nothing here to keep in
agreement.

Input   {"anchors": [{"kind": "api"|"sdk", "body": "..."}, ...]}
Output  {"ok": true, "declared_ops": N, "results": [{"resolved": bool, ...}]}
        {"ok": false, "reason": "..."}   — the caller treats this as SKIPPED,
                                           never as clean.

Exit 0 either way: "I could not resolve these" is an answer, and the caller
must be able to distinguish it from "these do not resolve". A non-zero exit
would be read as a crash and would collapse the two.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        anchors = payload["anchors"]
    except Exception as exc:  # noqa: BLE001 - any malformed input is "cannot tell"
        print(json.dumps({"ok": False, "reason": f"bad input: {exc}"}))
        return 0

    try:
        from aegis_sdk.handbook.check import (
            _HTTP_METHODS,
            _resolves_as_symbol,
            declared_operations,
            normalise_path,
        )
    except Exception as exc:  # noqa: BLE001 - not installed, not importable, etc.
        print(json.dumps({"ok": False, "reason": f"aegis_sdk not importable: {exc}"}))
        return 0

    try:
        ops = declared_operations()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "reason": f"derivation failed: {exc}"}))
        return 0

    results = []
    for a in anchors:
        kind, body = a.get("kind"), str(a.get("body", ""))
        if kind == "api":
            bits = body.split(None, 1)
            if len(bits) != 2 or bits[0] not in _HTTP_METHODS:
                results.append({"body": body, "resolved": False, "why": "malformed api anchor"})
                continue
            hit = (bits[0], normalise_path(bits[1])) in ops
            results.append(
                {
                    "body": body,
                    "resolved": hit,
                    "why": "" if hit else "this client declares no such operation",
                }
            )
        elif kind == "sdk":
            hit = bool(_resolves_as_symbol(body.strip()))
            results.append(
                {
                    "body": body,
                    "resolved": hit,
                    "why": "" if hit else "not a symbol this package exports",
                }
            )
        else:
            results.append({"body": body, "resolved": False, "why": f"unknown anchor kind {kind!r}"})

    print(json.dumps({"ok": True, "declared_ops": len(ops), "results": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
