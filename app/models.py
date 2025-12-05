from datetime import datetime
from sqlalchemy import Column, String, JSON, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, backref
from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)  # This matches the LlamaCloud file_id (dw, it is a PoC xd)
    filename = Column(String, index=True, unique=True)
    # todo category should not be 'processing' or 'failed'.. update this hack later
    category = Column(String)  # 'invoice', 'contract', 'other'
    contract_id = Column(String, ForeignKey("documents.id"), nullable=True)
    extracted_data = Column(JSON, nullable=True)
    text_content = Column(Text, nullable=True)
    discrepancies = Column(JSON, nullable=True)
    reconciliation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    linked_invoices = relationship(
        "Document",
        backref=backref("contract", remote_side=[id]),
        order_by="desc(Document.created_at)"
    )

    @property
    def is_contract(self):
        return self.category == 'contract'

    @property
    def is_invoice(self):
        return self.category == 'invoice'