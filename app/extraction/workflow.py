from workflows import Context, Workflow, step
from workflows.events import StopEvent

from app.extraction.events import (
    FilesUploadedEvent,
    StatusEvent,
    FileClassifiedEvent,
    ExtractionFinishedEvent,
    ReconcileInvoiceEvent,
    ProcessingCompleteEvent,
    BatchIngestionCompletedEvent,
)
from app.extraction.schemas import (
    CacheField,
    DocumentCategory,
    DocumentClassification,
    InvoiceData,
    ProcessingResult,
    Discrepancy,
)
from app.db import sessionmanager
from app.extraction.services.storage import StorageService
from app.extraction.services.ingestion import IngestionService
from app.extraction.services.classification import ClassificationService
from app.extraction.services.extraction import ExtractionService
from app.extraction.services.reconciliation import ReconciliationService


class DocumentAutomationWorkflow(Workflow):
    """
    Clean, service-oriented workflow for document processing.
    Flow: Ingest -> Classify -> Extract -> (Branch) -> Reconcile.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ingestion = IngestionService()
        self.classification = ClassificationService()
        self.extraction = ExtractionService()
        self.reconciliation = ReconciliationService()
        self.storage = StorageService()

    @step
    async def ingest(self, event: FilesUploadedEvent, ctx: Context) -> BatchIngestionCompletedEvent | None:
        """Downloads files using IngestionService."""
        ctx.write_event_to_stream(StatusEvent(message=f"Starting processing for {len(event.file_ids)} files"))

        downloaded_files = []
        for file_id in event.file_ids:
            try:
                file_info = await self.ingestion.download_file(file_id)
                ctx.write_event_to_stream(StatusEvent(file_id=file_id, message=f"Downloaded {file_info.filename}"))
                downloaded_files.append(file_info)
            except Exception as e:
                ctx.write_event_to_stream(StatusEvent(file_id=file_id, message=f"Download failed: {e}", level="error"))
                pass

        if downloaded_files:
            await ctx.store.set("num_files", len(downloaded_files))
            return BatchIngestionCompletedEvent(files=downloaded_files)
        return None

    @step
    async def classify(self, event: BatchIngestionCompletedEvent, ctx: Context) -> FileClassifiedEvent | ExtractionFinishedEvent | None:
        """Classifies files using ClassificationService."""
        ctx.write_event_to_stream(StatusEvent(message=f"Classifying batch of {len(event.files)} files..."))

        for f in event.files:
            ctx.write_event_to_stream(StatusEvent(file_id=f.file_id, message="Classifying..."))

        results = {}
        async with sessionmanager.session() as db:
            try:
                results = await self.classification.classify_files(db, event.files)
            except Exception as e:
                ctx.write_event_to_stream(StatusEvent(message=f"Batch classification error: {e}", level="error"))

        for f_info in event.files:
            classification = results.get(f_info.file_id)
            if not classification:
                ctx.write_event_to_stream(StatusEvent(file_id=f_info.file_id, message="Classification failed.", level="error"))
                async with sessionmanager.session() as db:
                    await self.storage.update_doc(db, f_info.file_id, category="failed", reconciliation_notes="Classification failed.")
                ctx.send_event(ExtractionFinishedEvent(
                    file_id=f_info.file_id,
                    status="skipped",
                    filename=f_info.filename,
                    result=ProcessingResult(
                        file_id=f_info.file_id,
                        filename=f_info.filename,
                        classification=DocumentClassification(
                            file_type="unknown",
                            document_category=DocumentCategory.OTHER,
                            confidence=0.0
                        ),
                        reconciliation_notes="Skipped: Classification failed."
                    )
                ))
                continue

            ctx.write_event_to_stream(
                StatusEvent(
                    file_id=f_info.file_id,
                    message=f"Classified as {classification.document_category.value} ({classification.file_type})"
                )
            )

            async with sessionmanager.session() as db:
                await self.storage.update_doc(
                    db, 
                    f_info.file_id, 
                    category=classification.document_category.value
                )

            if classification.document_category == DocumentCategory.OTHER:
                async with sessionmanager.session() as db:
                    await self.storage.update_doc(db, f_info.file_id, category="other", reconciliation_notes="Skipped: Unsupported category.")
                ctx.send_event(ExtractionFinishedEvent(
                    file_id=f_info.file_id,
                    status="skipped",
                    result=ProcessingResult(
                        file_id=f_info.file_id,
                        filename=f_info.filename,
                        classification=classification,
                        reconciliation_notes="Skipped: Unsupported category."
                    )))
            else:
                ctx.send_event(FileClassifiedEvent(
                    file_id=f_info.file_id,
                    filename=f_info.filename,
                    file_path=f_info.file_path,
                    classification=classification
                ))

    @step(num_workers=4)
    async def extract(self, event: FileClassifiedEvent, ctx: Context) -> ExtractionFinishedEvent:
        """Extracts data using ExtractionService based on classification."""

        # hacky
        field = CacheField.TEXT_CONTENT if event.classification.document_category == DocumentCategory.CONTRACT else CacheField.EXTRACTED_DATA
        
        async with sessionmanager.session() as db:
            if doc := await self.storage.get_cached_doc(db, event.file_id, field):
                ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message="Using cached data..."))
                data = doc.text_content if field == CacheField.TEXT_CONTENT else InvoiceData(**doc.extracted_data).model_dump()
                return ExtractionFinishedEvent(
                    file_id=event.file_id, filename=event.filename,
                    status="success",
                    classification=event.classification, category=event.classification.document_category,
                    data=data
                )

            ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message="Extracting content..."))

        try:
            result_data = await self.extraction.extract(event.file_path, event.classification)

            # Handle Contract (Composite Result: Text + Data) vs Invoice (Data only)
            if event.classification.document_category == DocumentCategory.CONTRACT:
                # result_data is {"text_content": str, "extracted_data": dict}
                text_content = result_data.get("text_content")
                extracted_data = result_data.get("extracted_data")

                await self.storage.update_doc(
                    db,
                    event.file_id,
                    text_content=text_content,
                    extracted_data=extracted_data
                )
                final_data = extracted_data
            else:
                await self.storage.update_doc(
                    db,
                    event.file_id,
                    extracted_data=result_data
                )
                final_data = result_data

            return ExtractionFinishedEvent(
                file_id=event.file_id, filename=event.filename,
                status="success",
                classification=event.classification, category=event.classification.document_category,
                data=final_data
            )
        except Exception as e:
            ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message=f"Extraction error: {e}", level="error"))
            async with sessionmanager.session() as db:
                await self.storage.update_doc(db, event.file_id, category="failed", reconciliation_notes=f"Extraction failed: {e}")
            return ExtractionFinishedEvent(
                file_id=event.file_id,
                status="skipped",
                result=ProcessingResult(
                    file_id=event.file_id, filename=event.filename, classification=event.classification,
                    reconciliation_notes=f"Extraction failed: {e}"
                )
            )

    @step
    async def prepare_reconciliation(
        self,
        ctx: Context,
        event: ExtractionFinishedEvent
    ) -> ReconcileInvoiceEvent | ProcessingCompleteEvent | None:
        """
        Barrier step: Collects all results, triggers reconciliation for invoices.
        """
        num_files = await ctx.store.get("num_files")
        events = ctx.collect_events(event, [ExtractionFinishedEvent] * num_files)

        if events is None:
            return None

        ctx.write_event_to_stream(StatusEvent(message="Processing complete. Preparing Reconciliation..."))

        completed_count = 0
        for ev in events:
            if ev.status == "skipped":
                ctx.write_event_to_stream(ProcessingCompleteEvent(result=ev.result))
                ctx.send_event(ProcessingCompleteEvent(result=ev.result))
                completed_count += 1
            elif ev.status == "success" and ev.category == DocumentCategory.CONTRACT:
                res = ProcessingResult(
                    file_id=ev.file_id, filename=ev.filename, classification=ev.classification,
                    reconciliation_notes="Contract indexed."
                )
                ctx.write_event_to_stream(ProcessingCompleteEvent(result=res))
                ctx.send_event(ProcessingCompleteEvent(result=res))
                completed_count += 1

        async with sessionmanager.session() as db:
            invoices_to_reconcile = await self.storage.get_pending_invoices(db)

            for inv in invoices_to_reconcile:
                ctx.send_event(ReconcileInvoiceEvent(
                    file_id=inv.id,
                    filename=inv.filename,
                    classification=DocumentClassification(
                        file_type="pdf", document_category=DocumentCategory.INVOICE, confidence=1.0
                    ),
                    invoice_data=InvoiceData(**inv.extracted_data)
                ))

        # we also reprocess invoices that were pending (from other workflows)
        new_total = completed_count + len(invoices_to_reconcile)
        await ctx.store.set("num_files", new_total)

        return None

    @step(num_workers=4)
    async def reconcile(self, ctx: Context, event: ReconcileInvoiceEvent) -> ProcessingCompleteEvent:
        """Reconciles invoice against all contracts using ReconciliationService."""

        async with sessionmanager.session() as db:
            doc = await self.storage.get_cached_doc(db, event.file_id, CacheField.RECONCILIATION_NOTES)
            if doc and "No matching contract" not in (doc.reconciliation_notes or ""):
                ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message="Using cached Reconciliation results..."))
                result = ProcessingResult(
                    file_id=event.file_id,
                    filename=event.filename,
                    classification=event.classification,
                    matched_contract_id=doc.extracted_data.get("matched_contract_id") if doc.extracted_data else None,
                    extracted_data=event.invoice_data.model_dump(),
                    reconciliation_notes=doc.reconciliation_notes,
                    discrepancies=[Discrepancy(**d) for d in (doc.discrepancies or [])]
                )
                return ProcessingCompleteEvent(result=result)

            ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message="Reconciling..."))

            contracts = await self.storage.get_contracts_for_matching(db)
            matched_id, notes, discrepancies = await self.reconciliation.reconcile(
                event.invoice_data, contracts
            )

            final_data = event.invoice_data.model_dump()
            if matched_id:
                final_data["matched_contract_id"] = matched_id

            result = ProcessingResult(
                file_id=event.file_id,
                filename=event.filename,
                classification=event.classification,
                matched_contract_id=matched_id,
                extracted_data=final_data,
                reconciliation_notes=notes,
                discrepancies=[d.model_dump() for d in discrepancies],
            )

            await self.storage.update_doc(
                db,
                event.file_id,
                extracted_data=final_data,
                reconciliation_notes=notes,
                discrepancies=[d.model_dump() for d in discrepancies],
                contract_id=matched_id
            )

        msg = "Match confirmed." if not discrepancies else f"{len(discrepancies)} discrepancies."
        ctx.write_event_to_stream(StatusEvent(file_id=event.file_id, message=msg))

        completion_event = ProcessingCompleteEvent(result=result)
        ctx.write_event_to_stream(completion_event)
        return completion_event

    @step
    async def finalize(
        self, ctx: Context, event: ProcessingCompleteEvent
    ) -> StopEvent | None:
        """Waits for all files to be processed and returns final list."""
        num_files = await ctx.store.get("num_files")
        results = ctx.collect_events(event, [ProcessingCompleteEvent] * num_files)
        if results is None:
            return None

        final_results = [ev.result for ev in results]
        return StopEvent(result=final_results)