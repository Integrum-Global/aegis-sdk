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
]
