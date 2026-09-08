"""
Unit tests for SDK invoices module.

Tests InvoicesModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.invoices import InvoicesModule
from aegis_sdk.types import (
    Invoice,
    InvoicesResponse,
    InvoiceStatus,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def invoices_module(mock_http):
    """Create InvoicesModule with mock HTTP client."""
    return InvoicesModule(mock_http)


def make_invoice_response(invoice_id="inv_123", status="paid"):
    """Create an invoice response dict."""
    return {
        "id": invoice_id,
        "number": "INV-2024-001",
        "status": status,
        "amount_due": 59900,
        "amount_paid": 59900 if status == "paid" else 0,
        "currency": "usd",
        "created": 1704067200,
        "due_date": 1706745600,
        "invoice_pdf": f"https://stripe.com/invoice/{invoice_id}.pdf",
        "hosted_invoice_url": f"https://invoice.stripe.com/{invoice_id}",
        "lines": [
            {
                "description": "Professional plan - Monthly",
                "amount": 59900,
                "quantity": 1,
                "currency": "usd",
            }
        ],
    }


MOCK_INVOICES_RESPONSE = {
    "invoices": [
        make_invoice_response("inv_001", "paid"),
        make_invoice_response("inv_002", "paid"),
        make_invoice_response("inv_003", "open"),
    ],
    "has_more": True,
}


@pytest.mark.unit
@pytest.mark.asyncio
class TestInvoicesModule:
    """Test InvoicesModule methods."""

    async def test_list_invoices(self, mock_http, invoices_module):
        """list() should return paginated invoices."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        result = await invoices_module.list(limit=10)

        assert isinstance(result, InvoicesResponse)
        assert len(result.invoices) == 3
        assert all(isinstance(inv, Invoice) for inv in result.invoices)
        assert result.has_more is True
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/subscriptions/invoices",
            params={"limit": 10},
        )

    async def test_list_invoices_default_limit(self, mock_http, invoices_module):
        """list() should use default limit of 10."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        await invoices_module.list()

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["limit"] == 10

    async def test_list_invoices_caches_result(self, mock_http, invoices_module):
        """list() should cache invoices for get_details."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        await invoices_module.list()

        assert invoices_module._invoices_cache is not None
        assert len(invoices_module._invoices_cache) == 3

    async def test_list_invoices_parses_line_items(self, mock_http, invoices_module):
        """list() should parse invoice line items correctly."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        result = await invoices_module.list()

        invoice = result.invoices[0]
        assert len(invoice.lines) == 1
        assert invoice.lines[0].description == "Professional plan - Monthly"
        assert invoice.lines[0].amount == 59900

    async def test_download_returns_pdf_url(self, mock_http, invoices_module):
        """download() should return PDF URL."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        url = await invoices_module.download("inv_001")

        assert url is not None
        assert "inv_001" in url
        assert ".pdf" in url

    async def test_download_fallback_to_hosted_url(self, mock_http, invoices_module):
        """download() should fall back to hosted invoice URL."""
        # Create response without PDF URL
        no_pdf_response = {
            "invoices": [
                {
                    "id": "inv_001",
                    "status": "draft",
                    "amount_due": 100,
                    "amount_paid": 0,
                    "currency": "usd",
                    "created": 1704067200,
                    "invoice_pdf": None,
                    "hosted_invoice_url": "https://invoice.stripe.com/inv_001",
                    "lines": [],
                }
            ],
            "has_more": False,
        }
        mock_http.request = AsyncMock(return_value=no_pdf_response)

        url = await invoices_module.download("inv_001")

        assert url is not None
        assert "stripe.com" in url

    async def test_download_returns_none_if_not_found(self, mock_http, invoices_module):
        """download() should return None if invoice not found."""
        mock_http.request = AsyncMock(return_value={"invoices": [], "has_more": False})

        url = await invoices_module.download("inv_nonexistent")

        assert url is None

    async def test_get_details_from_cache(self, mock_http, invoices_module):
        """get_details() should return from cache if available."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        # First call loads cache
        await invoices_module.list()

        # Second call should use cache
        invoice = await invoices_module.get_details("inv_001")

        assert isinstance(invoice, Invoice)
        assert invoice.id == "inv_001"
        # Should only have called request once (for list)
        assert mock_http.request.call_count == 1

    async def test_get_details_reloads_if_not_cached(self, mock_http, invoices_module):
        """get_details() should reload if not in cache."""
        mock_http.request = AsyncMock(return_value=MOCK_INVOICES_RESPONSE)

        invoice = await invoices_module.get_details("inv_002")

        assert isinstance(invoice, Invoice)
        assert invoice.id == "inv_002"

    async def test_get_details_returns_none_if_not_found(self, mock_http, invoices_module):
        """get_details() should return None if invoice not found."""
        mock_http.request = AsyncMock(return_value={"invoices": [], "has_more": False})

        invoice = await invoices_module.get_details("inv_nonexistent")

        assert invoice is None

    async def test_invoice_status_values(self, mock_http, invoices_module):
        """list() should parse different invoice statuses."""
        response = {
            "invoices": [
                make_invoice_response("inv_paid", "paid"),
                make_invoice_response("inv_open", "open"),
                make_invoice_response("inv_draft", "draft"),
            ],
            "has_more": False,
        }
        mock_http.request = AsyncMock(return_value=response)

        result = await invoices_module.list()

        statuses = [inv.status for inv in result.invoices]
        assert InvoiceStatus.PAID in statuses
        assert InvoiceStatus.OPEN in statuses
        assert InvoiceStatus.DRAFT in statuses
