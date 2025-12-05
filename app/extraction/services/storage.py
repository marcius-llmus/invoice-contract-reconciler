from sqlalchemy import select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Document
from app.extraction.schemas import CacheField, DocumentCategory


class StorageService:
    """Service for all database interactions regarding Documents."""

    @staticmethod
    async def get_cached_doc(db: AsyncSession, file_id: str, field: CacheField) -> Document | None:
        """Retrieves a document if the specified cache field is populated."""
        stmt = select(Document).where(Document.id == file_id).where(text(f"{field.value} IS NOT NULL"))
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_doc(db: AsyncSession, file_id: str) -> Document | None:
        result = await db.execute(select(Document).where(Document.id == file_id))
        return result.scalars().first()

    @staticmethod
    async def update_doc(db: AsyncSession, file_id: str, **kwargs) -> None:
        """Updates specific fields of a document."""
        result = await db.execute(select(Document).where(Document.id == file_id))
        if doc := result.scalars().first():
            for key, value in kwargs.items():
                setattr(doc, key, value)

    @staticmethod
    async def get_contracts_for_matching(db: AsyncSession) -> list[dict]:
        """Fetches all processed contracts for reconciliation context."""
        result = await db.execute(
            select(Document).where(Document.category == DocumentCategory.CONTRACT.value)
        )
        return [
            {"id": c.id, "filename": c.filename, "text_content": c.text_content}
            for c in result.scalars().all()
        ]

    @staticmethod
    async def get_pending_invoices(db: AsyncSession) -> list[Document]:
        """Fetches invoices that have been extracted but not reconciled."""
        stmt = select(Document).where(
            Document.category == DocumentCategory.INVOICE.value,
            Document.extracted_data.is_not(None)
        )
        result = await db.execute(stmt)
        return [doc for doc in result.scalars().all() if not doc.extracted_data.get('matched_contract_id')]

    @staticmethod
    async def get_dashboard_view_data(db: AsyncSession) -> list[Document]:
        """Retrieves and organizes documents for the dashboard view."""
        stmt = (
            select(Document)
            .where(or_(
                Document.contract_id.is_(None),
                Document.category == DocumentCategory.CONTRACT.value
            ))
            .options(selectinload(Document.linked_invoices))
            .order_by(Document.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_or_create_document(db: AsyncSession, file_id: str, filename: str) -> Document:
        """Creates a new document record or returns existing one."""
        # Check existence
        result = await db.execute(select(Document).where(Document.filename == filename))
        if existing := result.scalars().first():
            return existing

        # Create new
        new_doc = Document(id=file_id, filename=filename, category="processing")
        db.add(new_doc)
        return new_doc

    @staticmethod
    async def get_file_ids_by_filenames(db: AsyncSession, filenames: list[str]) -> list[str]:
        """Retrieves file IDs for a list of filenames."""
        result = await db.execute(select(Document).where(Document.filename.in_(filenames)))
        return [d.id for d in result.scalars().all()]

    @staticmethod
    async def get_incomplete_file_ids(db: AsyncSession) -> list[str]:
        """Retrieves IDs of documents that are failed, stuck processing, or unmatched invoices."""
        result = await db.execute(select(Document))
        docs = result.scalars().all()
        ids = []
        for d in docs:
            if d.category in ["processing", "failed", "unknown", "other"]:
                ids.append(d.id)
            elif d.category == "invoice":
                if not d.extracted_data or not d.extracted_data.get("matched_contract_id"):
                    ids.append(d.id)
        return ids