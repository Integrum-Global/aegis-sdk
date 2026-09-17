"""
Credentials SDK Module (``/api/v1/credentials``).

Encrypted credential storage: store, list and inspect metadata, retrieve the
decrypted value, rotate, revoke, delete.

Values are never returned by any read. The single method that returns a
plaintext secret is :meth:`CredentialsModule.retrieve`, which is a ``POST`` for
that reason — keeping the identifier out of web-server access logs and forcing
the access onto the audit trail.

.. important::
    **Every route on this surface rejects API-key credentials — reads
    included.** The router admits only callers holding the ``admin`` or
    ``architect`` persona, and an API-key principal carries no persona at all,
    so the refusal is a flat ``403`` regardless of the key's scopes. There is
    no scope that grants it. Use a user-session token.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class CredentialMetadata(TolerantModel):
    """A stored credential, without its value.

    Note:
        ``metadata`` is populated on the single-credential reads (:meth:`get`,
        :meth:`rotate`, :meth:`revoke`) and is **always ``None`` on
        :meth:`list` rows** — the list projection does not include it. A
        ``None`` here therefore does not mean the credential has no metadata.

    Note:
        ``status`` is one of ``active``, ``rotated`` or ``revoked``. Two things
        it does **not** tell you:

        * It never becomes ``expired``. A credential past its ``expires_at``
          keeps reporting ``active`` — expiry is checked when the value is
          retrieved, not by a background sweep. Compare ``expires_at`` against
          the clock yourself; do not read ``status`` as usability.
        * Nothing in the platform writes ``rotated``. It is an advertised
          filter value that matches no record, so a "recently rotated" view
          built on it will always be empty. Use ``last_rotated_at``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    name: str
    credential_type: str
    status: str
    last_accessed_at: str | None = None
    last_rotated_at: str | None = None
    expires_at: str | None = None
    created_by: str
    created_at: str
    updated_at: str | None = None
    metadata: dict[str, Any] | None = None


class CredentialValue(TolerantModel):
    """A decrypted credential value.

    Handle as a secret: it is the plaintext, and the platform recorded an audit
    entry for the access that produced it.
    """

    model_config = ConfigDict(populate_by_name=True)

    value: str


class CredentialTypes(TolerantModel):
    """The credential types the platform accepts."""

    model_config = ConfigDict(populate_by_name=True)

    types: list[str] = Field(default_factory=list)


class CredentialStatuses(TolerantModel):
    """The credential status values the platform declares.

    Note:
        This is the declared vocabulary, not the set of statuses in use — see
        the note on :class:`CredentialMetadata` about ``rotated``.
    """

    model_config = ConfigDict(populate_by_name=True)

    statuses: list[str] = Field(default_factory=list)


class CredentialsModule:
    """
    Encrypted-credential SDK module (``/api/v1/credentials``).

    Methods:
        - list_types() / list_statuses(): The declared vocabularies
        - store(): Store a new credential
        - list(): Credential metadata, never values
        - get(): One credential's metadata
        - retrieve(): The decrypted value (audited)
        - rotate(): Replace the value
        - revoke(): Mark revoked without deleting
        - delete(): Permanently delete

    Credential requirement:
        This whole surface — reads included — is unreachable with an API key.
        See the module docstring.

    Tenant scope:
        A credential belonging to another organization is reported as
        **absent** (``404``), never as forbidden, and the platform deliberately
        emits the same message for both so the response cannot be used to
        probe for existence elsewhere.

    Revocation is reversible, and that is not obvious:
        :meth:`rotate` sets the credential back to ``active`` and does **not**
        check the current status first. Rotating a revoked credential therefore
        un-revokes it. If you need revocation to be terminal, use
        :meth:`delete`.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key=user_session_token)
        >>>
        >>> cred = await client.credentials.store(
        ...     name="alerts-webhook",
        ...     credential_type="webhook_secret",
        ...     value=secret,
        ... )
        >>> value = await client.credentials.retrieve(cred.id)
    """

    def __init__(self, http_client):
        """Initialize the credentials module with an HTTP client."""
        self._http = http_client

    async def list_types(self) -> CredentialTypes:
        """
        List the credential types the platform accepts.

        Returns:
            The accepted ``credential_type`` values. :meth:`store` rejects
            anything outside this set with ``400``.

        Example:
            >>> types = await client.credentials.list_types()
            >>> print(types.types)
        """
        response = await self._http.request("GET", "/api/v1/credentials/types")
        return CredentialTypes(**response)

    async def list_statuses(self) -> CredentialStatuses:
        """
        List the credential status values the platform declares.

        Returns:
            The declared vocabulary. This is what the platform *names*, not
            what it *uses* — see :class:`CredentialMetadata`.

        Example:
            >>> statuses = await client.credentials.list_statuses()
        """
        response = await self._http.request("GET", "/api/v1/credentials/statuses")
        return CredentialStatuses(**response)

    async def store(
        self,
        name: str,
        credential_type: str,
        value: str,
        metadata: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> CredentialMetadata:
        """
        Store a new encrypted credential. Responds ``201``.

        Args:
            name: Credential name (1-100 characters)
            credential_type: One of :meth:`list_types`
            value: The plaintext secret. Encrypted at rest by the platform;
                never returned by any read except :meth:`retrieve`.
            metadata: Free-form metadata stored alongside the credential. Do
                not put secrets here — it is returned in plaintext by
                :meth:`get`.
            expires_at: ISO-8601 expiry. What this does: :meth:`retrieve`
                refuses the credential once the timestamp has passed. What it
                does **not** do: change ``status``, notify anyone, or stop the
                credential appearing as ``active`` in :meth:`list`.

        Returns:
            The stored credential's metadata, without the value.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, or a session
                without the ``admin``/``architect`` persona.
            ValidationError: ``400``/``422`` — unknown ``credential_type``, or
                a field-length constraint.

        Example:
            >>> cred = await client.credentials.store(
            ...     name="alerts-webhook",
            ...     credential_type="webhook_secret",
            ...     value=secret,
            ...     expires_at="2027-01-01T00:00:00Z",
            ... )
        """
        body: dict[str, Any] = {
            "name": name,
            "credential_type": credential_type,
            "value": value,
        }
        if metadata is not None:
            body["metadata"] = metadata
        if expires_at is not None:
            body["expires_at"] = expires_at

        response = await self._http.request("POST", "/api/v1/credentials/", json_data=body)
        return CredentialMetadata(**response)

    async def list(
        self,
        credential_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CredentialMetadata]:
        """
        List credential metadata. Never returns values.

        Args:
            credential_type: Filter by type
            status: Filter by status. Filtering on ``"rotated"`` matches
                nothing — see :class:`CredentialMetadata`.
            limit: Page size (default 100)
            offset: Page offset

        Returns:
            Credential metadata rows. ``metadata`` is ``None`` on every row
            regardless of what the credential carries; use :meth:`get` for it.

        Example:
            >>> creds = await client.credentials.list(credential_type="api_key")
            >>> for c in creds:
            ...     print(c.name, c.status, c.expires_at)
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if credential_type is not None:
            params["credential_type"] = credential_type
        if status is not None:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/credentials/", params=params)
        return [CredentialMetadata(**row) for row in response or []]

    async def get(self, credential_id: str) -> CredentialMetadata:
        """
        Get one credential's metadata. Does not return the value.

        Args:
            credential_id: Credential ID

        Returns:
            The credential's metadata, including ``metadata``.

        Raises:
            NotFoundError: ``404`` — no such credential in this organization.

        Example:
            >>> cred = await client.credentials.get("cred-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/credentials/{encode_path_param(credential_id)}"
        )
        return CredentialMetadata(**response)

    async def retrieve(self, credential_id: str) -> CredentialValue:
        """
        Retrieve the decrypted credential value.

        This is the only method that returns a plaintext secret. The platform
        records an audit entry and updates ``last_accessed_at`` on every call,
        so this is a tracked access rather than a read — do not call it in a
        loop to populate a display.

        It is a ``POST`` deliberately: the identifier stays out of URLs, and
        therefore out of web-server access logs and browser history.

        Args:
            credential_id: Credential ID

        Returns:
            The decrypted value. Treat the returned object as a secret.

        Raises:
            NotFoundError: ``404`` — no such credential in this organization.
            ValidationError: ``400`` — the credential is not ``active``, or its
                ``expires_at`` has passed. **This is the only place expiry is
                enforced**, so a credential that lists as ``active`` can still
                fail here.
            AuthorizationError: ``403`` — an API-key credential, or a session
                without the required persona.

        Example:
            >>> secret = (await client.credentials.retrieve("cred-1")).value
        """
        response = await self._http.request(
            "POST", f"/api/v1/credentials/{encode_path_param(credential_id)}/retrieve"
        )
        return CredentialValue(**response)

    async def rotate(self, credential_id: str, new_value: str) -> CredentialMetadata:
        """
        Replace a credential's value.

        Two behaviours worth knowing before you call this:
            * It sets ``status`` back to ``active`` **without checking the
              current status**, so rotating a revoked credential re-activates
              it. Revocation is not terminal against this method.
            * It does **not** touch ``expires_at``. Rotating an expired
              credential leaves it expired, so :meth:`retrieve` will still
              refuse it. Store a new credential to reset the expiry.

        Args:
            credential_id: Credential ID
            new_value: The new plaintext secret

        Returns:
            The credential's updated metadata, re-read after the write.

        Raises:
            NotFoundError: ``404`` — no such credential in this organization.
            AuthorizationError: ``403`` — an API-key credential, or a session
                without the required persona.

        Example:
            >>> await client.credentials.rotate("cred-1", new_value=new_secret)
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/credentials/{encode_path_param(credential_id)}/rotate",
            json_data={"new_value": new_value},
        )
        return CredentialMetadata(**response)

    async def revoke(self, credential_id: str) -> CredentialMetadata:
        """
        Mark a credential revoked without deleting it.

        A revoked credential fails :meth:`retrieve` with ``400`` and keeps its
        metadata and audit history. It can be brought back — see
        :meth:`rotate`. Use :meth:`delete` when the credential must not be
        recoverable.

        Args:
            credential_id: Credential ID

        Returns:
            The credential's updated metadata, re-read after the write.

        Raises:
            NotFoundError: ``404`` — no such credential in this organization.
            AuthorizationError: ``403`` — an API-key credential, or a session
                without the required persona.

        Example:
            >>> await client.credentials.revoke("cred-1")
        """
        response = await self._http.request(
            "POST", f"/api/v1/credentials/{encode_path_param(credential_id)}/revoke"
        )
        return CredentialMetadata(**response)

    async def delete(self, credential_id: str) -> None:
        """
        Permanently delete a credential. Responds ``204`` with no body.

        This is irreversible and removes the stored value. Prefer
        :meth:`revoke` when the record should survive for audit.

        Args:
            credential_id: Credential ID

        Returns:
            ``None``. The platform returns no representation of the deleted
            credential.

        Raises:
            NotFoundError: ``404`` — no such credential in this organization.
            AuthorizationError: ``403`` — an API-key credential, or a session
                without the required persona.

        Example:
            >>> await client.credentials.delete("cred-1")
        """
        await self._http.request(
            "DELETE", f"/api/v1/credentials/{encode_path_param(credential_id)}"
        )
        return None
