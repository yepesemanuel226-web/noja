"""
backend/database.py
===================
Conexión a base de datos SQLite local.
Usa un archivo horarios.db en la raíz del proyecto.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ── Ruta al archivo SQLite (siempre en la raíz del proyecto) ─────────────────
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH   = os.path.join(_BASE_DIR, "horarios.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False es necesario para FastAPI (múltiples threads)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
