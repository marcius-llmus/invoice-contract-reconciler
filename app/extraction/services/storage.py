from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Document
from app.extraction.schemas import CacheField, DocumentCategory


class StorageService:
    """Service for all database interactions regarding Documents."""

    async def get_cached_doc(self, db: AsyncSession, file_id: str, field: CacheField) -> Document | None:
        """Retrieves a document if the specified cache field is populated."""
        stmt = select(Document).where(Document.id == file_id).where(text(f"{field.value} IS NOT NULL"))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_doc(self, db: AsyncSession, file_id: str) -> Document | None:
        result = await db.execute(select(Document).where(Document.id == file_id))
        return result.scalars().first()

    async def update_doc(self, db: AsyncSession, file_id: str, **kwargs) -> None:
        """Updates specific fields of a document."""
        result = await db.execute(select(Document).where(Document.id == file_id))
        if doc := result.scalars().first():
            for key, value in kwargs.items():
                setattr(doc, key, value)

    async def get_contracts_for_matching(self, db: AsyncSession) -> list[dict]:
        """Fetches all processed contracts for reconciliation context."""
        result = await db.execute(
            select(Document).where(Document.category == DocumentCategory.CONTRACT.value)
        )
        return [
            {"id": c.id, "filename": c.filename, "text_content": c.text_content}
            for c in result.scalars().all()
        ]

    async def get_pending_invoices(self, db: AsyncSession) -> list[Document]:
        """Fetches invoices that have been extracted but not reconciled."""
        stmt = select(Document).where(
            Document.category == DocumentCategory.INVOICE.value,
            Document.extracted_data.is_not(None)
        )
        result = await db.execute(stmt)
        return [doc for doc in result.scalars().all() if not doc.extracted_data.get('matched_contract_id')]

    async def get_dashboard_view_data(self, db: AsyncSession) -> tuple[list[Document], dict[str, list[Document]]]:
        """Retrieves and organizes documents for the dashboard view."""
        result = await db.execute(select(Document).order_by(Document.created_at.desc()))
        all_docs = result.scalars().all()

        contracts = {d.id: d for d in all_docs if d.category == 'contract'}
        children_map = {k: [] for k in contracts}
        root_docs = []

        for doc in all_docs:
            if doc.category == 'contract':
                root_docs.append(doc)
            else:
                matched_id = doc.extracted_data.get('matched_contract_id') if doc.extracted_data else None
                if matched_id and matched_id in contracts:
                    children_map[matched_id].append(doc)
                else:
                    root_docs.append(doc)
        
        return root_docs, children_map

    async def create_document(self, db: AsyncSession, file_id: str, filename: str) -> Document:
        """Creates a new document record or returns existing one."""
        # Check existence
        result = await db.execute(select(Document).where(Document.filename == filename))
        if existing := result.scalars().first():
            return existing
        
        # Create new
        new_doc = Document(id=file_id, filename=filename, category="processing")
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)
        return new_doc

    async def get_file_ids_by_filenames(self, db: AsyncSession, filenames: list[str]) -> list[str]:
        """Retrieves file IDs for a list of filenames."""
        result = await db.execute(select(Document).where(Document.filename.in_(filenames)))
        return [d.id for d in result.scalars().all()]