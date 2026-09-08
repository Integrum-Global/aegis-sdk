"""Vertical-standup modules for the Aegis SDK ( P0).

Typed create/get (+ trivial list/publish/approve) client modules for the
families needed to stand up a vertical end-to-end: organizations, organization
units, organization roles, teams, role envelopes, knowledge, ontology, and the
human-on-the-loop approvals queue.

Each route/verb/body is verified against the corresponding server router under (cited per-method).
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
