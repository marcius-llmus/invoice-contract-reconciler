from llama_index.core.prompts import PromptTemplate
from app.extraction.clients import get_llm
from app.extraction.prompts import RECONCILIATION_PROMPT
from app.extraction.schemas import InvoiceData, ContractMatchResult, Discrepancy


class ReconciliationService:
    """Service for matching invoices against contracts."""

    @staticmethod
    async def reconcile(invoice: InvoiceData, contracts: list[dict]) -> tuple[str | None, str, list[Discrepancy]]:
        """
        Analyzes invoice against a list of contracts.
        Returns: (matched_contract_id, notes, discrepancies)
        """
        if not contracts:
            return None, "No contracts available for matching.", []

        contracts_text_block = "\n\n".join(
            [f"[{i}] Contract File: {c['filename']}\n{c['text_content'][:2000]}..." 
             for i, c in enumerate(contracts)]
        )

        prompt_template = PromptTemplate(RECONCILIATION_PROMPT)
        llm = get_llm()
        
        match_result = await llm.astructured_predict(
            ContractMatchResult,
            prompt_template,
            **{
                "vendor_name": invoice.vendor_name or "N/A",
                "invoice_number": invoice.invoice_number or "N/A",
                "invoice_date": invoice.date or "N/A",
                "po_number": invoice.purchase_order_number or "N/A",
                "payment_terms": invoice.payment_terms or "N/A",
                "total": invoice.total_amount or "N/A",
                "contracts_listing": contracts_text_block,
            },
        )

        matched_contract_id = None
        notes = "No matching contract found."
        discrepancies = []

        if match_result.is_match and match_result.matched_contract_index is not None:
            idx = match_result.matched_contract_index
            if 0 <= idx < len(contracts):
                matched_contract_id = contracts[idx]['id']
                notes = f"Match ({match_result.match_confidence}): {match_result.match_rationale}"
                discrepancies = match_result.discrepancies

        return matched_contract_id, notes, discrepancies