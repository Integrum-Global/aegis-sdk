"""
Agentic OS SDK Trust Module.

Provides modules for trust chains, delegations, postures, audit logging,
organizational authorities, per-agent trust reads, the trust registry,
pipeline validation, revocation recovery, aggregate observability, and
Enterprise Security Authority configuration, following the Enterprise Agent
Trust Protocol (EATP).

AUTHENTICATION: unlike several other areas of this SDK, the trust routes ARE
reachable with an API key -- their router is wired with the key-aware persona
gate and admits a key carrying the ``trust`` scope. Two routes ask for more
than a read scope and say so in their own docstrings: registering an agent and
recording a heartbeat both WRITE, and both require a trust write scope.

The health snapshot is the one route here that needs no credential at all.
"""

from .agent_trust import AgentTrustModule
from .audit import AuditModule
from .authorities import AuthoritiesModule
from .chains import ChainsModule
from .delegations import DelegationsModule
from .esa import ESAModule
from .observability import TrustObservabilityModule
from .pipeline import PipelineTrustModule
from .postures import PosturesModule
from .registry import TrustRegistryModule
from .revocation import RevocationModule

__all__ = [
    "AgentTrustModule",
    "AuditModule",
    "AuthoritiesModule",
    "ChainsModule",
    "DelegationsModule",
    "ESAModule",
    "PipelineTrustModule",
    "PosturesModule",
    "RevocationModule",
    "TrustObservabilityModule",
    "TrustRegistryModule",
]
