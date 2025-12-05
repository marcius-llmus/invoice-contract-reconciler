from datetime import datetime
from sqlalchemy import Column, String, JSON, Text, DateTime
from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)  # This matches the LlamaCloud file_id (dw, it is a PoC xd)
    filename = Column(String, index=True, unique=True)
    category = Column(String)  # 'invoice', 'contract', 'other'
    extracted_data = Column(JSON, nullable=True)
    text_content = Column(Text, nullable=True)
    discrepancies = Column(JSON, nullable=True)
    reconciliation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)