from llama_index.core.prompts import PromptTemplate
from llama_cloud_services.beta.sheets import SpreadsheetParsingConfig

from app.extraction.clients import get_sheets_client, get_parser, get_llm
from app.extraction.schemas import DocumentClassification, DocumentCategory, InvoiceData, LineItem, ContractData


class ExtractionService:
    """Service for extracting structured data or text from documents."""

    async def extract(self, file_path: str, classification: DocumentClassification) -> dict | str:
        """Strategy dispatcher for extraction based on classification."""
        if classification.file_type == "xlsx":
            return await self._extract_xlsx(file_path)
        
        if classification.document_category == DocumentCategory.CONTRACT:
            return await self._extract_contract(file_path)
        
        if classification.document_category == DocumentCategory.INVOICE:
            return await self._extract_pdf_invoice(file_path)
            
        return "Unsupported document type for extraction."

    @staticmethod
    async def _extract_xlsx(file_path: str) -> dict:
        """Extracts invoice data from Excel using LlamaSheets."""
        client = get_sheets_client()
        file_response = await client.upload_file(file_path)
        
        config = SpreadsheetParsingConfig(sheet_names=None, generate_additional_metadata=True)
        job = await client.acreate_job(file_id=file_response.id, config=config)
        job_result = await client.await_for_completion(job_id=job.id)

        extracted_items = []
        if job_result.regions:
            for region in job_result.regions:
                df = await client.adownload_region_as_dataframe(
                    job_id=job.id,
                    region_id=region.region_id,
                    result_type=region.region_type or "table"
                )
                extracted_items.extend(df.to_dict(orient="records"))

        line_items = []
        for item in extracted_items:
            item_lower = {str(k).lower(): v for k, v in item.items()}
            
            description = item_lower.get("description") or item_lower.get("desc") or item_lower.get("item") or str(item)
            quantity = item_lower.get("quantity") or item_lower.get("qty")
            unit_price = item_lower.get("unit_price") or item_lower.get("price") or item_lower.get("rate")
            amount = item_lower.get("amount") or item_lower.get("total")

            line_items.append(LineItem(
                description=str(description) if description else None,
                quantity=float(quantity) if quantity else 0.0,
                unit_price=float(unit_price) if unit_price else 0.0,
                amount=float(amount) if amount else 0.0
            ))

        return InvoiceData(
            vendor_name=f"Spreadsheet Import",
            line_items=line_items,
        ).model_dump()

    @staticmethod
    async def _parse_text(file_path: str) -> str:
        """Parses document to raw text using LlamaParse."""
        parser = get_parser()
        documents = await parser.aload_data(file_path)
        return "\n\n".join([d.text for d in documents])

    @staticmethod
    async def _extract_contract(self, file_path: str) -> dict:
        """Extracts text AND structured data from a contract."""
        full_text = await self._parse_text(file_path)
        
        prompt = PromptTemplate("Extract key contract details from the following text:\n{text}\n")
        llm = get_llm()
        
        contract_data = await llm.astructured_predict(
            ContractData, prompt, text=full_text
        )
        return {"text_content": full_text, "extracted_data": contract_data.model_dump()}

    async def _extract_pdf_invoice(self, file_path: str) -> dict:
        """Extracts structured invoice data from PDF using LLM."""
        full_text = await self._parse_text(file_path)
        
        prompt = PromptTemplate("Extract invoice data from the following text:\n{text}\n")
        llm = get_llm()
        
        invoice_data = await llm.astructured_predict(
            InvoiceData, prompt, text=full_text
        )
        return invoice_data.model_dump()
