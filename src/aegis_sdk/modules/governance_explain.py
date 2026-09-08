"""
Governance Diagnostics SDK Module (``/api/v1/governance``).

Operator diagnostics for the governance layer: why a particular access
decision came out the way it did, what a role's effective envelope is, what a
D/T/R address means, and three readiness readouts over the org's envelopes and
role grammar.

These are **read and explain** tools. Nothing here changes a decision, a role,
or an envelope; every method is either a pure explanation of a hypothetical or
a report over current state.

Relationship to ``client.governance``:
    Different surface. ``client.governance`` covers the data-governance and
    RBAC APIs (classifications, consents, lineage, policies, roles). This module
    covers the ``/api/v1/governance`` diagnostics mount only.

Credential:
    Unlike most of the governance write surfaces, these routes **do** accept an
    API key. Five require ``organizations:read``;
    :meth:`GovernanceExplainModule.envelope_coverage` requires ``audit:read``
    instead, which is deliberately narrower — see its docstring. There is no
    persona gate and no edition gate: these stay reachable on every tier so a
    support incident does not become unrecoverable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccessExplanation(BaseModel):
    """Step-by-step trace of one access decision.

    Note:
        This explains a **hypothetical** you describe in the request. It does
        not read a real knowledge item, and it does not record an access — so
        the answer is only as accurate as the ``knowledge_item`` you supplied.
    """

    model_config = ConfigDict(populate_by_name=True)

    allowed: bool
    reason: str = ""
    step_reached: str = ""
    access_path: str = ""


class EnvelopeExplanation(BaseModel):
    """A role's effective envelope, explained through its ancestor chain."""

    model_config = ConfigDict(populate_by_name=True)

    address: str = ""
    explanation: str = ""


class AddressDescription(BaseModel):
    """Human-readable reading of a D/T/R address."""

    model_config = ConfigDict(populate_by_name=True)

    address: str = ""
    description: str = ""


class SkippedRoleEnvelope(BaseModel):
    """One role envelope that the last hydration pass skipped.

    A skipped envelope means its role currently operates with **no** hydrated
    standing envelope. The engine falls back to a restrictive bootstrap default
    — deny, never unlimited — so a skip is fail-closed, not a hole. It is
    silent everywhere else, which is why it is surfaced here.
    """

    model_config = ConfigDict(populate_by_name=True)

    envelope_id: str
    target_role_id: str | None = None
    target_role_title: str | None = None
    defining_role_id: str | None = None
    reason: str = ""
    detected_at: str = ""


class EnvelopeHydrationStatus(BaseModel):
    """Summary of the organization's last envelope hydration pass."""

    model_config = ConfigDict(populate_by_name=True)

    hydrated: int = 0
    skipped: int = 0
    skipped_roles: list[SkippedRoleEnvelope] = Field(default_factory=list)
    computed_at: str | None = None


class RoleEnvelopeCoverage(BaseModel):
    """Coverage verdict for one agent-reachable role.

    Three fields carry a three-valued meaning that collapses badly if you
    coerce them, and the distinctions are the point of the report:

    * ``bucket`` — ``resolved_constrained``, ``resolved_allow_all``,
      ``not_resolved``, or ``unclassified``. ``unclassified`` is **neither**
      covered nor uncovered; it is the tool declining to guess, and any
      non-zero count of it means the coverage question is not fully answered.
    * ``has_active_envelope_row`` — ``True``/``False`` when the envelope table
      was read, ``None`` when it was **not** read. "No row" and "could not
      look" are opposite findings; do not treat ``None`` as ``False``.
    * ``allowed_actions`` — ``None`` when no envelope resolved. Never ``0``
      for that case, because ``0`` **is** the allow-all answer. Do not
      default it to zero.
    """

    model_config = ConfigDict(populate_by_name=True)

    role_id: str
    role_title: str | None = None
    role_address: str | None = None
    bucket: str = ""
    detail: str | None = None
    has_active_envelope_row: bool | None = None
    allowed_actions: int | None = None
    blocked_actions: int | None = None
    agent_ids: list[str] = Field(default_factory=list)


class EnvelopeCoverageReport(BaseModel):
    """Envelope-coverage report for the caller's organization.

    Of the roles an agent can actually execute as, how many resolve an
    envelope that would genuinely constrain anything.

    Note:
        ``complete`` is ``False`` when **any** part of the measurement did not
        happen, and ``unmeasured`` names what was missed. A partial report is
        never presented as a whole one — check ``complete`` before quoting any
        number from this object.

    Note:
        ``enforcement_ready`` is conjunctive: it is ``True`` only when the
        measurement was complete **and** every reachable role resolves a
        constraining envelope. A ``False`` therefore does not tell you which of
        the two failed; read ``complete`` and ``counts``.

    Note:
        ``agents_without_role_linkage`` is reported separately rather than
        folded into the denominator. Those agents resolve no address at all and
        would be denied before an envelope is consulted, so counting them as
        covered would overstate readiness.
    """

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = ""
    measured_at: str = ""
    complete: bool = False
    unmeasured: list[str] = Field(default_factory=list)
    agents_total: int = 0
    agents_without_role_linkage: int = 0
    agents_with_unresolvable_role: int = 0
    agent_reachable_roles: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    enforcement_ready: bool = False
    hydration: dict[str, Any] | None = None
    roles: list[RoleEnvelopeCoverage] = Field(default_factory=list)


class CorruptedRoleEntry(BaseModel):
    """A role observed to violate one or more D/T/R grammar invariants.

    Note:
        ``violations`` carries named strings such as ``address_null``,
        ``is_primary_for_unit_false_on_head`` and
        ``shadow_agent_id_null_despite_auto_generate``.
    """

    model_config = ConfigDict(populate_by_name=True)

    role_id: str
    organization_unit_id: str | None = None
    title: str | None = None
    violations: list[str] = Field(default_factory=list)


class CorruptedRolesReport(BaseModel):
    """Inventory of role-grammar violations in the caller's organization.

    Note:
        ``total_corrupted`` and ``counts_by_violation`` are computed over every
        role examined, but ``corrupted_roles`` is **truncated at 500 entries**.
        ``len(corrupted_roles) < total_corrupted`` is expected on a large org
        and is not a discrepancy.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_corrupted: int = 0
    counts_by_violation: dict[str, int] = Field(default_factory=dict)
    corrupted_roles: list[CorruptedRoleEntry] = Field(default_factory=list)


class GovernanceExplainModule:
    """
    Governance-diagnostics SDK module (``/api/v1/governance``).

    Methods:
        - explain_access(): Why one hypothetical access decision resolves as
          it does
        - explain_envelope(): A role's effective envelope and ancestor chain
        - describe_address(): Read a D/T/R address in plain language
        - envelope_hydration_status(): The last hydration pass, and what it
          skipped
        - envelope_coverage(): Whether envelopes would actually constrain
          anything
        - probe_corrupted_roles(): Role-grammar invariant violations

    Everything here is read-only. None of it changes a decision or a record.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key="your-api-key")
        >>>
        >>> why = await client.governance_explain.explain_access(
        ...     role_id="role-1",
        ...     knowledge_item={
        ...         "id": "doc-9",
        ...         "classification": "confidential",
        ...         "unit_address": "D1-R1",
        ...     },
        ...     posture="supervised",
        ... )
        >>> print(why.allowed, why.step_reached, why.reason)
    """

    def __init__(self, http_client):
        """Initialize the governance-diagnostics module with an HTTP client."""
        self._http = http_client

    async def explain_access(
        self, role_id: str, knowledge_item: dict[str, Any], posture: str
    ) -> AccessExplanation:
        """
        Explain how one access decision resolves, step by step.

        This evaluates the item **you describe**, not a stored one. It is a
        dry run: nothing is accessed, nothing is recorded as an access, and the
        verdict is only as good as the ``knowledge_item`` you pass. Do not use
        it as evidence that a real access was permitted.

        Args:
            role_id: The role requesting access
            knowledge_item: The item to evaluate. Requires ``id``,
                ``classification`` and ``unit_address``; ``compartment`` is
                optional. A wrong or missing value changes the verdict.
            posture: The agent's trust posture — one of ``pseudo``,
                ``supervised``, ``shared_planning``, ``continuous_insight`` or
                ``delegated``. Anything else is rejected.

        Returns:
            The decision, the reason, the step the evaluation reached, and the
            access path taken. ``step_reached`` is the useful field when
            ``allowed`` is ``False``: it names where the chain stopped.

        Raises:
            ValidationError: ``400``/``422`` — an unrecognized posture or a
                malformed knowledge item.
            AuthorizationError: ``403`` — missing ``organizations:read``.

        Example:
            >>> why = await client.governance_explain.explain_access(
            ...     role_id="role-1",
            ...     knowledge_item={
            ...         "id": "doc-9",
            ...         "classification": "confidential",
            ...         "unit_address": "D1-R1",
            ...         "compartment": "legal",
            ...     },
            ...     posture="delegated",
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/governance/explain-access",
            json_data={
                "role_id": role_id,
                "knowledge_item": knowledge_item,
                "posture": posture,
            },
        )
        return AccessExplanation(**response)

    async def explain_envelope(self, role_address: str) -> EnvelopeExplanation:
        """
        Explain a role's effective operating envelope through its ancestors.

        Args:
            role_address: The role's D/T/R address, e.g. ``"D1-R1-T1-R2"``

        Returns:
            The address and a prose explanation of how the effective envelope
            was composed down the chain.

        Raises:
            ValidationError: ``400``/``422`` — the address is not a valid
                D/T/R address.
            AuthorizationError: ``403`` — missing ``organizations:read``.

        Example:
            >>> exp = await client.governance_explain.explain_envelope("D1-R1-T1-R2")
            >>> print(exp.explanation)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/governance/explain-envelope",
            json_data={"role_address": role_address},
        )
        return EnvelopeExplanation(**response)

    async def describe_address(self, address: str) -> AddressDescription:
        """
        Read a D/T/R address in plain language.

        Args:
            address: The address string to describe

        Returns:
            The address and its description.

        Raises:
            ValidationError: ``400``/``422`` — the address is malformed.
            AuthorizationError: ``403`` — missing ``organizations:read``.

        Example:
            >>> desc = await client.governance_explain.describe_address("D1-R1-T1-R2")
            >>> print(desc.description)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/governance/describe-address",
            json_data={"address": address},
        )
        return AddressDescription(**response)

    async def envelope_hydration_status(self) -> EnvelopeHydrationStatus:
        """
        Report the organization's last envelope-hydration pass.

        A non-zero ``skipped`` is not an outage: a skipped envelope leaves its
        role on a restrictive bootstrap default, so the effect is a role that
        is more constrained than intended, never less. It is worth fixing
        because it is otherwise invisible, not because it is permissive.

        Returns:
            Counts, the skipped envelopes with a reason each, and the timestamp
            of the underlying pass. ``computed_at`` is ``None`` when no pass has
            been recorded — that is "not measured", not "clean".

        Raises:
            AuthorizationError: ``403`` — missing ``organizations:read``.

        Example:
            >>> status = await client.governance_explain.envelope_hydration_status()
            >>> for s in status.skipped_roles:
            ...     print(s.target_role_title, s.reason)
        """
        response = await self._http.request(
            "GET", "/api/v1/governance/envelope-hydration-status"
        )
        return EnvelopeHydrationStatus(**response)

    async def envelope_coverage(self) -> EnvelopeCoverageReport:
        """
        Report whether envelopes would actually constrain the roles agents run as.

        The question this answers is not "do envelopes exist" but "would they
        stop anything" — an envelope that resolves to allow-all provides false
        assurance, and it is counted separately from one that constrains.

        **Check ``complete`` first.** When it is ``False``, part of the
        measurement did not happen and ``unmeasured`` names which part; the
        counts are then a floor, not a total.

        Args:
            None.

        Returns:
            The coverage report. Read the three-valued fields on each role
            carefully — see :class:`RoleEnvelopeCoverage`.

        Raises:
            AuthorizationError: ``403`` — this route needs ``audit:read``,
                **not** the ``organizations:read`` the rest of this module uses.
                The narrower gate is deliberate: the report enumerates every
                agent-reachable role with its address and the agents that reach
                it, which is a wider disclosure than the other diagnostics. An
                API key must be scoped to ``audit`` explicitly; no
                ``organizations``-family scope reaches it.

        Example:
            >>> report = await client.governance_explain.envelope_coverage()
            >>> if not report.complete:
            ...     print("partial:", report.unmeasured)
            >>> print(report.counts, report.enforcement_ready)
        """
        response = await self._http.request(
            "GET", "/api/v1/governance/envelope-coverage"
        )
        return EnvelopeCoverageReport(**response)

    async def probe_corrupted_roles(self) -> CorruptedRolesReport:
        """
        Inventory roles that violate the D/T/R grammar invariants.

        Read-only triage. It reports; it repairs nothing.

        Two limits to read the result against:
            * ``corrupted_roles`` is truncated at 500 entries while
              ``total_corrupted`` and ``counts_by_violation`` cover every role
              examined. A shorter list than the total is expected, not a bug.
            * The scan itself reads up to 10,000 active roles. An organization
              larger than that is under-reported, and nothing in the response
              says so.

        One violation is a candidate, not a finding:
            ``is_primary_for_unit_false_on_head`` flags roles that *look* like
            they should be a unit's head (authority level 1, with a unit). The
            probe cannot distinguish a head role from a supplementary one, so
            treat this violation as a list to review rather than a list to fix.

        Returns:
            The corrupted-role inventory.

        Raises:
            AuthorizationError: ``403`` — missing ``organizations:read``.

        Example:
            >>> report = await client.governance_explain.probe_corrupted_roles()
            >>> print(report.total_corrupted, report.counts_by_violation)
        """
        response = await self._http.request(
            "GET", "/api/v1/governance/probe-corrupted-roles"
        )
        return CorruptedRolesReport(**response)
