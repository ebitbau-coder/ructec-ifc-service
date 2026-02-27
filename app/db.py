import os
from datetime import datetime

from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")

# Railway liefert oft postgres:// oder postgresql://
# Wir erzwingen hier den psycopg v3 Treiber.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModelRecord(Base):
    __tablename__ = "models"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="uploaded", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
