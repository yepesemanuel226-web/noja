from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys

# ── Path para encontrar config.py en la raíz ──────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DATABASE_URL as _CFG_URL

# ─────────────────────────────────────────────────────────────────────────────
# CONEXIÓN A SUPABASE (PostgreSQL)
#
# Supabase desde 2024 usa connection pooler en puerto 6543.
# La URL del config.py usa puerto 5432 (conexión directa) que a veces falla
# por DNS en redes restringidas. Aquí forzamos el puerto 6543 (Session Pooler).
#
# Si tienes variable de entorno DATABASE_URL definida, se usa esa primero.
# ─────────────────────────────────────────────────────────────────────────────

_env_url = os.getenv("DATABASE_URL")

if _env_url:
    DATABASE_URL = _env_url
else:
    # Usar la URL del config pero forzar puerto 6543 (Supabase Session Pooler)
    DATABASE_URL = _CFG_URL.replace(":5432/", ":6543/")

# Parámetros necesarios para Supabase con psycopg2
# pgbouncer=true es requerido por el pooler de Supabase
if "supabase.co" in DATABASE_URL and "pgbouncer" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + sep + "pgbouncer=true&sslmode=require"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # verifica conexión antes de usarla
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": 10,
        "sslmode": "require",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()