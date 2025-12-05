from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class DocumentCategory(str, Enum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    OTHER = "other"


class CacheField(str, Enum):
    EXTRACTED_DATA = "extracted_data"
    TEXT_CONTENT = "text_content"
    RECONCILIATION_NOTES = "reconciliation_notes"


class DocumentClassification(BaseModel):
    """Result of document classification"""

    file_type: Literal["pdf", "xlsx", "unknown"]
    document_category: DocumentCategory
    confidence: float
    summary: str | None = None
    reasoning: str | None = None


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = Field(default=None, description="Description of the item")
    quantity: float | None = Field(default=None, description="Quantity of the item")
    unit_price: float | None = Field(default=None, description="Unit price of the item")
    amount: float | None = Field(default=None, description="Total amount for the line item")


class Discrepancy(BaseModel):
    field: str
    invoice_value: str
    contract_value: str
    issue: str


class InvoiceData(BaseModel):
    """Structured data extracted from an invoice"""
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    date: str | None = None
    purchase_order_number: str | None = None
    payment_terms: str | None = None
    line_items: list[LineItem] = []


class ContractData(BaseModel):
    """Structured data extracted from a contract"""
    vendor_name: str | None = None
    contract_number: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    payment_terms: str | None = None


class ProcessingResult(BaseModel):
    """Final result for a processed file"""

    file_id: str
    filename: str
    classification: DocumentClassification
    matched_contract_id: str | None = None
    extracted_data: dict[str, Any] | None = None
    reconciliation_notes: str | None = None
    discrepancies: list[Discrepancy] = []


class ContractMatchResult(BaseModel):
    """Result of matching invoice to contract"""

    is_match: bool = Field(
        description="Whether a plausible contract match was found"
    )
    matched_contract_index: int | None = Field(
        default=None,
        description="Index (0-based) of the matched contract in the provided list, or None if no match",
    )
    match_confidence: str = Field(
        description="Confidence level: 'high', 'medium', 'low', or 'none'"
    )
    match_rationale: str = Field(
        description="Explanation of why this contract was or was not matched"
    )
    contract_payment_terms: str | None = Field(
        default=None, description="Payment terms found in the matched contract"
    )
    discrepancies: list[Discrepancy] = Field(
        default_factory=list,
        description="List of discrepancies found between invoice and contract",
    )


class InvoiceReconciliationInput(BaseModel):
    """Input for batch reconciliation"""
    filename: str
    invoice_data: InvoiceData


class BatchContractMatchResult(BaseModel):
    """Batch result containing matches for multiple invoices"""
    results: dict[str, ContractMatchResult] = Field(
        description="Dictionary mapping filename to its contract match result"
    )