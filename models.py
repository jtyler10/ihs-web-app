from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from db import Base


class Book(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    authors = Column(String(512))
    isbn = Column(String(32), index=True)
    publisher = Column(String(256))
    publisher_city = Column(String(256))
    pub_year = Column(String(10))
    description = Column(Text)
    pages = Column(Integer)
    language = Column(String(64))
    condition = Column(String(32))
    scanned = Column(Boolean, default=False)
    owner = Column(String(256))
    priority = Column(String(16))
    potential_imprint = Column(String(256))
    notes = Column(Text)
    source = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Production(Base):
    __tablename__ = "production"

    id          = Column(Integer, primary_key=True)
    book_id     = Column(Integer, nullable=False, index=True)
    stage       = Column(String(64), nullable=False)
    assigned_to = Column(String(256))
    notes       = Column(Text)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
