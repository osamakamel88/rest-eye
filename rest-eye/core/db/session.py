from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from ..config import config
from .models import Base

# Determine connect args (e.g. check_same_thread for SQLite)
connect_args = {}
if config.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    config.database_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes all database tables"""
    Base.metadata.create_all(bind=engine)
    print(f"[Database] Tables initialized successfully on: {config.database_url.split('@')[-1] if '@' in config.database_url else config.database_url}")

def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
