> **WARNING**: This is a Proof of Concept (PoC). The codebase is currently untested and intended for demonstration purposes only.

# Extraction & Reconciliation Workflow

This application implements an automated document processing pipeline using event-driven workflows. It ingests documents, classifies them into categories (e.g., Invoices, Contracts), extracts structured metadata, and audits invoices against available contracts to identify discrepancies in payment terms or amounts.

## Features

- **Ingestion**: Asynchronous file processing via WebSocket.
- **Classification**: AI-driven categorization of documents.
- **Extraction**: Structured data extraction from unstructured text.
- **Reconciliation**: Logic to match invoices with contracts and flag anomalies.
- **Real-time Dashboard**: HTMX-based interface for monitoring processing status and viewing results.

## Installation

Requires Python 3.10+.

1. **Install Dependencies**
   Using `uv` or `pip`:
   ```bash
   pip install -e .
   ```

2. **Configuration**
   Set the following environment variables:
   ```bash
   export OPENAI_API_KEY=sk-...
   export LLAMA_CLOUD_API_KEY=llx-...
   ```

3. **Execution**
   Run the FastAPI server:
   ```bash
   fastapi dev app/main.py
   ```
