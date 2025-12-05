from typing import List, Literal, Any, Dict
from pydantic import BaseModel
from workflows.events import Event, StartEvent
from app.extraction.schemas import DocumentClassification, ProcessingResult, InvoiceData, DocumentCategory


class FilesUploadedEvent(StartEvent):
    file_ids: List[str]


class FileInfo(BaseModel):
    file_id: str
    file_path: str
    filename: str


class BatchIngestionCompletedEvent(Event):
    files: List[FileInfo]


class FileIngestedEvent(Event):
    file_info: FileInfo


class FileClassifiedEvent(Event):
    file_id: str
    filename: str
    file_path: str
    classification: DocumentClassification


class ExtractionFinishedEvent(Event):
    """Unified event for when a file has finished the extraction phase (success or skip)."""
    file_id: str
    status: Literal["success", "skipped"]
    filename: str | None = None
    classification: DocumentClassification | None = None
    category: DocumentCategory | None = None
    data: Dict[str, Any] | str | None = None
    result: ProcessingResult | None = None


class ReconcileInvoiceEvent(Event):
    file_id: str
    filename: str
    classification: DocumentClassification
    invoice_data: InvoiceData


class ProcessingCompleteEvent(Event):
    result: ProcessingResult


class StatusEvent(Event):
    file_id: str | None = None
    message: str
    level: str = "info"