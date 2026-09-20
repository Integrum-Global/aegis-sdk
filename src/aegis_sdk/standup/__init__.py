"""Vertical-standup modules for the Aegis SDK.

Client modules for the families needed to stand up a vertical end-to-end:
organizations, organization units, organization roles, teams, role envelopes,
knowledge, ontology, and the human-on-the-loop approvals queue.

VERBS PER MODULE -- stated explicitly, because a docstring that promises a verb
the module does not have costs a partner a failed run. The caller writes
``client.roles.list(...)``, gets ``AttributeError``, and an idempotent
provisioning script reads that as "cannot reconcile" and refuses to create:

    organizations   create · get · list
    units           create · get · list
    roles           create · get · list
    teams           create · get · list
    envelopes       create · get · list      (list is per-supervisor, see below)
    knowledge       create · get · list · publish
    ontology        apply_preset · update_config · get_config · list_presets
    approvals       list_pending · get · approve · reject · modify

SCOPES PER MODULE -- stated for the same reason, and it costs a partner more
than a missing verb does. A verb that does not exist raises ``AttributeError``
on the call you are looking at. A scope you did not mint raises 403 on a LATER
call, after the earlier ones have already created organization, unit and role
rows -- leaving a half-provisioned tenant, which is the state an idempotent
provisioning script is least able to reconcile.

``agents:read``/``agents:write`` -- the pair the SDK's agent-workflow docs show
-- is NOT sufficient for this package. The resources here are gated in two
different ways, and the difference matters:

    organizations   some ``organizations:*``         (router scope_resources)
    units           some ``organizations:*`` AND ``units:*``
    roles           some ``organizations:*`` AND ``roles:*``
    and the WRITE routes name the scope exactly: the role-envelope create
    carries ``require_scope("roles:write")``, which ``roles:read`` does not
    satisfy. Area coverage is necessary and not sufficient.

NINE calls in this package are reachable by NO API key at ANY scope, because
their routers gate on ``require_persona`` alone and an API-key principal
resolves to ``personas: []`` by construction: every route on the ontology router
and every route on the approvals router. Those need a JWT/bearer session.

That list -- and the reason for each surface -- is declared ONCE, in
``aegis_sdk.standup.session_only``, and re-exported here as
``SESSION_ONLY_CALLS`` / ``SESSION_ONLY_REASON``. Read it there rather than
inferring which calls are safe from a router name: the ontology router serves
``apply_preset``, both config methods AND ``list_presets``, so "it is only the
write that needs a session" is false. The working set of scopes for the rest is
carried verbatim in
``examples/stand_up_a_vertical.py::REQUIRED_SCOPES`` -- use it rather than
assembling one by hand.

⚠ THESE MODULES ARE NOT THE WHOLE SURFACE, and the obvious name is the smaller
one. Update and delete live elsewhere, on modules that are NOT cross-linked
from the client attribute a standup caller reaches first:

    roles      -> ``client.role_admin`` (``/api/v1/roles``, an ALIAS for
                  ``/api/v1/organization-roles``; same
                  ``OrganizationRoleService.list``, typed responses) and
                  ``client.org_standup`` (update/delete).
    envelopes  -> ``client.trust_posture`` (update · delete · ACTIVATE ·
                  suspend). ``create`` exists ONLY here and ``activate``
                  exists ONLY there, so an envelope created through this
                  module stays ``draft`` until a different module is used.

Each route/verb/body is verified against the corresponding server router
(cited per-method).
"""

from .approvals import ApprovalsModule
from .envelopes import RoleEnvelopesModule
from .knowledge import KnowledgeModule
from .ontology import OntologyModule
from .organizations import OrganizationsModule
from .roles import OrganizationRolesModule
from .session_only import SESSION_ONLY_CALLS, SESSION_ONLY_REASON, is_session_only
from .teams import TeamsModule
from .units import OrganizationUnitsModule

__all__ = [
    "OrganizationsModule",
    "OrganizationUnitsModule",
    "OrganizationRolesModule",
    "TeamsModule",
    "RoleEnvelopesModule",
    "KnowledgeModule",
    "OntologyModule",
    "ApprovalsModule",
    "SESSION_ONLY_CALLS",
    "SESSION_ONLY_REASON",
    "is_session_only",
]
