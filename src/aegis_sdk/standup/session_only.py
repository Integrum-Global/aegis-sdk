"""Which standup calls need a user session — the SINGLE declaration.

Read this ONE list rather than re-deriving the platform's router graph. The
example, the package docstring and the security gate that pins the behaviour all
resolve here, so a declaration and its consumers cannot drift apart.

WHY A CALL CAN BE UNREACHABLE BY *ANY* API KEY
----------------------------------------------
An API-key principal carries ``personas: []`` by construction (``get_current_user``'s
API-key branch mints it as its fail-closed default). A route whose only gate is a
plain ``require_persona`` therefore admits no key **at any scope**: there is no
scope to grant, no rotation that helps, and no role change that applies. That is a
different fact from "your key is missing a scope", and it is the difference this
module exists to state — a partner who reads it as the second spends an hour
looking for a grant that does not exist.

THE TWO SURFACES, AND WHY EACH IS DELIBERATE
--------------------------------------------
``approvals`` — the human-on-the-loop decision surface. An approval IS the
in-the-loop half of Human-on-the-Loop; a machine credential performing one is not
a scope shortfall, it is the WRONG PRINCIPAL ENTIRELY. Every route on that router
is session-only for the same reason, reads included.

``ontology`` — the per-organization governance vocabulary. Applying a preset
SHAPES THE GOVERNANCE MODEL, so admitting a key to it would collapse "manage the
thing" into "govern the thing": the credential that operates under a model would
also be the one that rewrites it. The config reads sit behind the same gate
because the router gates as a unit; ``/ontology/resolved/{organization_id}`` is
served by a separate ungated router for callers that only need the rendered terms.

WHAT THIS DECLARATION DOES NOT COVER — the surface is wider than these two
routers, and those calls are NOT declared session-only because they are not.
``organizations``, ``units``, ``roles``, ``knowledge`` and ``envelopes`` are
reachable by a key holding the right scopes (``envelopes`` additionally carries a
per-route ``require_scope``, so the area is necessary and not sufficient).
"""

from typing import Final

#: Every standup-surface call that NO API key can reach, at any scope, spelled
#: ``"<client attribute>.<method>"`` — the same vocabulary a caller writes.
#:
#: The list is complete over ``aegis_sdk.standup``'s own modules. It is not a
#: subset chosen by an example: a call omitted here would tell a partner their
#: key can make it.
SESSION_ONLY_CALLS: Final[tuple[str, ...]] = (
    "ontology.apply_preset",
    "ontology.get_config",
    "ontology.list_presets",
    "ontology.update_config",
    "approvals.approve",
    "approvals.get",
    "approvals.list_pending",
    "approvals.modify",
    "approvals.reject",
)

#: Why each surface refuses a key, keyed by the client attribute the calls hang
#: off. The reason is a property of the SURFACE, not of each call: the router
#: gates as a unit, so splitting it per call would invent a distinction the
#: platform does not make.
SESSION_ONLY_REASON: Final[dict[str, str]] = {
    "approvals": (
        "An approval is the in-the-loop half of Human-on-the-Loop. A machine "
        "credential performing one is not a scope shortfall — it is the wrong "
        "principal entirely."
    ),
    "ontology": (
        "A preset shapes the governance model. Admitting a key would collapse "
        "'manage the thing' into 'govern the thing'."
    ),
}


def is_session_only(call_id: str) -> bool:
    """Whether ``call_id`` (``"<attr>.<method>"``) requires a user session."""
    return call_id in SESSION_ONLY_CALLS
