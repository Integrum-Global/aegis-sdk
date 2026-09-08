"""
Invoices Module for Agentic OS SDK.

Provides invoice management operations including listing, downloading,
and viewing invoice details.

3 methods:
- list() - List organization's invoices
- download() - Get invoice download URL
- get_details() - Get detailed invoice information
"""

from ..types import (
    Invoice,
    InvoicesResponse,
)


class InvoicesModule:
    """
    Invoice management module.

    Provides methods for listing and accessing invoice information.

    Examples:
        # List recent invoices
        >>> response = await client.revenue.invoices.list(limit=10)
        >>> for invoice in response.invoices:
        ...     print(f"{invoice.number}: ${invoice.amount_paid / 100} ({invoice.status})")

        # Download invoice PDF
        >>> url = await client.revenue.invoices.download("inv_123")
        >>> print(f"Download from: {url}")

        # Get invoice details
        >>> invoice = await client.revenue.invoices.get_details("inv_123")
        >>> for line in invoice.lines:
        ...     print(f"  {line.description}: ${line.amount / 100}")
    """

    def __init__(self, http_client):
        """
        Initialize invoices module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client
        # Cache for invoices to support get_details
        self._invoices_cache: list[Invoice] | None = None

    async def list(self, limit: int = 10) -> InvoicesResponse:
        """
        List organization's invoices.

        Returns invoice history from Stripe.

        Args:
            limit: Maximum number of invoices to return (default 10)

        Returns:
            InvoicesResponse: Invoices with pagination info

        Raises:
            AuthenticationError: If not authenticated

        Example:
            >>> response = await client.revenue.invoices.list(limit=5)
            >>> print(f"Found {len(response.invoices)} invoices")
            >>> for inv in response.invoices:
            ...     status_emoji = "✓" if inv.status == "paid" else "○"
            ...     print(f"{status_emoji} {inv.number}: ${inv.amount_paid / 100}")
            >>> if response.has_more:
            ...     print("More invoices available...")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/subscriptions/invoices",
            params={"limit": limit},
        )

        invoices = [Invoice(**inv) for inv in response.get("invoices", [])]
        # Cache for get_details
        self._invoices_cache = invoices

        return InvoicesResponse(
            invoices=invoices,
            has_more=response.get("has_more", False),
        )

    async def download(self, invoice_id: str) -> str | None:
        """
        Get invoice PDF download URL.

        Returns the Stripe-hosted PDF URL for the invoice.

        Args:
            invoice_id: Invoice identifier

        Returns:
            Optional[str]: PDF download URL, or None if not available

        Example:
            >>> url = await client.revenue.invoices.download("inv_123")
            >>> if url:
            ...     print(f"Download PDF: {url}")
            ...     # Can redirect user or download programmatically
            ... else:
            ...     print("No PDF available for this invoice")
        """
        # First check cache
        invoice = await self.get_details(invoice_id)
        if invoice and invoice.invoice_pdf:
            return invoice.invoice_pdf
        elif invoice and invoice.hosted_invoice_url:
            return invoice.hosted_invoice_url
        return None

    async def get_details(self, invoice_id: str) -> Invoice | None:
        """
        Get detailed invoice information.

        Returns full invoice details including line items.

        Args:
            invoice_id: Invoice identifier

        Returns:
            Optional[Invoice]: Invoice details, or None if not found

        Example:
            >>> invoice = await client.revenue.invoices.get_details("inv_123")
            >>> if invoice:
            ...     print(f"Invoice #{invoice.number}")
            ...     print(f"Status: {invoice.status}")
            ...     print(f"Total: ${invoice.amount_due / 100}")
            ...     print("Line items:")
            ...     for line in invoice.lines:
            ...         print(f"  - {line.description}: ${line.amount / 100}")
        """
        # Check cache first
        if self._invoices_cache:
            for inv in self._invoices_cache:
                if inv.id == invoice_id:
                    return inv

        # Reload invoices to find the one we want
        # Note: Stripe API doesn't have single invoice endpoint by default
        # We fetch the list and search for the specific invoice
        response = await self.list(limit=100)

        for inv in response.invoices:
            if inv.id == invoice_id:
                return inv

        return None
