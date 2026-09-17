"""Tier 1: contract tests for the shared response-envelope helper.

The Aegis API wraps every successful body as ``{"data": ...}``; list routes add
``{"data": [...], "total": N}``. Clients that read the envelope as if it were
the payload do not error — they return a plausible, EMPTY, WRONG answer. That
is the most expensive failure shape a client can have, so the unwrap helper is
pinned here in BOTH polarities: it must unwrap a real envelope, and it must
leave alone every shape that only LOOKS like one.

The negative polarity is the load-bearing half. A payload that legitimately
owns a top-level ``data`` field (a record whose own schema has a ``data``
column, for example) must survive untouched; a helper that unwraps it would
silently discard the record's siblings.
"""

import pytest

from aegis_sdk._http import unwrap_envelope

# Keys the server is known to emit ALONGSIDE ``data`` as envelope metadata.
# A sibling key outside this set means the dict is a payload, not an envelope.
PAGINATION_SIBLINGS = [
    "total",
    "message",
    "meta",
    "page",
    "page_size",
    "has_next",
    "limit",
    "offset",
    "count",
]


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestUnwrapEnvelopePositive:
    """Shapes the helper MUST unwrap."""

    def test_unwraps_dict_payload(self):
        assert unwrap_envelope({"data": {"id": "p_1", "name": "Research"}}) == {
            "id": "p_1",
            "name": "Research",
        }

    def test_unwraps_list_payload(self):
        assert unwrap_envelope({"data": [{"id": "p_1"}, {"id": "p_2"}]}) == [
            {"id": "p_1"},
            {"id": "p_2"},
        ]

    def test_unwraps_list_envelope_with_total(self):
        """The list-route shape: ``data`` plus the ``total`` metadata sibling."""
        assert unwrap_envelope({"data": [{"id": "p_1"}], "total": 1}) == [{"id": "p_1"}]

    @pytest.mark.parametrize("sibling", PAGINATION_SIBLINGS)
    def test_unwraps_despite_each_known_metadata_sibling(self, sibling):
        """Each allow-listed sibling alone must not block the unwrap."""
        assert unwrap_envelope({"data": [{"id": "p_1"}], sibling: 1}) == [{"id": "p_1"}]

    def test_unwraps_falsy_payloads(self):
        """An empty payload is still a payload — ``data`` present is the signal,
        not ``data`` being truthy. A truthiness test here would return the whole
        envelope for every legitimately-empty list route."""
        assert unwrap_envelope({"data": []}) == []
        assert unwrap_envelope({"data": None}) is None
        assert unwrap_envelope({"data": [], "total": 0}) == []


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestUnwrapEnvelopeNegative:
    """Shapes the helper MUST NOT touch. This is the over-application guard."""

    def test_does_not_unwrap_when_an_unexpected_sibling_is_present(self):
        """A payload legitimately owning a top-level ``data`` field keeps ALL of
        its fields. Unwrapping here would discard ``unexpected_key`` silently."""
        payload = {"data": {"blob": 1}, "unexpected_key": "mine"}
        assert unwrap_envelope(payload) == payload

    def test_does_not_unwrap_record_owning_a_data_column(self):
        payload = {"id": "rec_1", "data": {"k": "v"}, "created_at": "2026-01-01T00:00:00Z"}
        assert unwrap_envelope(payload) == payload

    def test_returns_unchanged_when_no_data_key(self):
        payload = {"items": [{"id": "p_1"}], "total": 1}
        assert unwrap_envelope(payload) == payload

    def test_returns_unchanged_on_empty_dict(self):
        assert unwrap_envelope({}) == {}

    @pytest.mark.parametrize(
        "value",
        [
            [{"id": "p_1"}],
            "a string",
            42,
            None,
            True,
        ],
    )
    def test_returns_non_dict_unchanged(self, value):
        """A bare array is the legacy list shape; it is already the payload."""
        assert unwrap_envelope(value) == value

    def test_does_not_double_unwrap(self):
        """One level only. A payload that is itself ``{"data": X}`` must come
        back as ``{"data": X}``, not as ``X`` — otherwise a record whose own
        ``data`` column holds a dict loses a level of nesting."""
        assert unwrap_envelope({"data": {"data": {"inner": 1}}}) == {"data": {"inner": 1}}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestUnwrapEnvelopeDoesNotMutate:
    """The helper reads; it must not edit the caller's dict in place."""

    def test_input_dict_is_not_mutated(self):
        envelope = {"data": [{"id": "p_1"}], "total": 1}
        snapshot = {"data": [{"id": "p_1"}], "total": 1}
        unwrap_envelope(envelope)
        assert envelope == snapshot
