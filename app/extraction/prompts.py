RECONCILIATION_PROMPT =  """You are analyzing an invoice to match it with the correct contract and identify any discrepancies.

Invoice Details:
- Vendor: {vendor_name}
- Invoice Number: {invoice_number}
- Invoice Date: {invoice_date}
- PO Number: {po_number}
- Payment Terms: {payment_terms}
- Total: {total}

Available Contracts:
{contracts_listing}

Task:
1. Determine if any of the retrieved contracts plausibly matches this invoice based on:
   - Vendor name matching or similarity
   - PO number or invoice number references
   - Date ranges (invoice date must be within contract validity)
   - Any other relevant identifiers

2. If a match is found, identify discrepancies between invoice and contract, focusing on:
   - Payment terms differences (CRITICAL)
   - Total amount mismatches if contract specifies amounts
   - Vendor name discrepancies
   - Any other obvious conflicts

3. Assess match confidence:
   - 'high': Clear match with strong vendor/PO/identifier alignment
   - 'medium': Probable match with some uncertainty
   - 'low': Weak match, possibly relevant but uncertain
   - 'none': No plausible match found in the provided list

IMPORTANT:
If a match is found, you MUST provide the 'matched_contract_index' corresponding to the position of the contract in the "Available Contracts" list (0-based).

Provide your analysis in the specified format."""

BATCH_RECONCILIATION_PROMPT = """You are an expert auditor analyzing multiple invoices against a set of contracts.

Available Contracts:
{contracts_text}

Invoices to Analyze:
{invoices_text}

Task:
For EACH invoice provided above:
1. Find the most plausible matching contract from the list.
2. Identify discrepancies (Payment terms, Total amounts, Vendor names).
3. Assess match confidence.

Output Format:
Return a JSON object where keys are the filenames of the invoices and values are the reconciliation results.

Example structure:
{
  "results": {
    "invoice_A.pdf": { ... match result ... },
    "invoice_B.xlsx": { ... match result ... }
  }
}
"""