from pathlib import Path
from llama_cloud import ClassifierRule
from sqlalchemy.ext.asyncio import AsyncSession
from app.extraction.clients import get_classifier_client
from app.extraction.events import FileInfo
from app.extraction.services.storage import StorageService
from app.extraction.schemas import DocumentClassification, DocumentCategory


class ClassificationService:
    """Service for determining document types and categories."""

    def __init__(self, storage_service: StorageService = None):
        self.storage = storage_service or StorageService()

    async def classify_files(self, db: AsyncSession, files: list[FileInfo]) -> dict[str, DocumentClassification]:
        """Classifies a batch of files using extensions or LlamaCloud Classifier."""
        results = {}
        pdfs_to_classify = []

        for f in files:
            # 1. Check Cache
            cached = await self._check_cache(db, f)
            if cached:
                results[f.file_id] = cached
                continue
            
            # 2. Check Extension
            by_ext = self._classify_by_extension(f)
            if by_ext:
                results[f.file_id] = by_ext
            elif f.filename.lower().endswith(".pdf"):
                pdfs_to_classify.append(f)
            else:
                # Unknown
                results[f.file_id] = DocumentClassification(
                    file_type="unknown",
                    document_category=DocumentCategory.OTHER,
                    confidence=0.0
                )

        if pdfs_to_classify:
            llm_results = await self._classify_via_llm(pdfs_to_classify)
            results.update(llm_results)

        return results

    async def _check_cache(self, db: AsyncSession, file_info: FileInfo) -> DocumentClassification | None:
        if doc := await self.storage.get_doc(db, file_info.file_id):
            if doc.category and doc.category not in ["processing", "unknown"]:
                try:
                    cat = DocumentCategory(doc.category)
                    return DocumentClassification(
                        file_type="pdf" if file_info.filename.lower().endswith(".pdf") else "xlsx",
                        document_category=cat,
                        confidence=1.0,
                        summary="Retrieved from cache"
                    )
                except ValueError:
                    pass
        return None

    @staticmethod
    def _classify_by_extension(file_info: FileInfo) -> DocumentClassification | None:
        ext = Path(file_info.filename).suffix.lower()
        if ext == ".xlsx":
            return DocumentClassification(
                file_type="xlsx",
                document_category=DocumentCategory.INVOICE,
                confidence=1.0,
                summary="Excel Spreadsheet",
            )
        return None

    @staticmethod
    async def _classify_via_llm(files: list[FileInfo]) -> dict[str, DocumentClassification]:
        classifier = get_classifier_client()
        rules = [
            ClassifierRule(type="invoice", description="Commercial document issued by seller to buyer."),
            ClassifierRule(type="contract", description="Legally binding agreement between parties."),
        ]
        
        cls_response = await classifier.aclassify_file_ids(
            rules=rules,
            file_ids=[f.file_id for f in files]
        )

        results = {}
        for item in cls_response.items:
            if (category := item.result.type) is None:
                classification = DocumentClassification(
                    file_type="pdf", document_category=DocumentCategory.OTHER, confidence=0.0
                )
            else:
                classification = DocumentClassification(
                    file_type="pdf",
                    document_category=DocumentCategory(category),
                    confidence=1.0,
                    reasoning=item.result.reasoning
                )
            results[item.file_id] = classification
        
        return results
