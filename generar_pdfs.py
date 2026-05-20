"""
generar_pdfs.py
===============
Regenera todos los PDFs en reportes_pdf/ desde la BD SQLite ya poblada.
Esos PDFs son la fuente de conocimiento del RAG, chatbot y bot de Telegram.

Ejecutar DESPUÉS de seed_database.py:
    python generar_pdfs.py
"""
import os
import sys

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

from backend.database import engine, Base, SessionLocal
import backend.models
Base.metadata.create_all(bind=engine)

from backend.models import Docente, Programa, Grupo, Asignacion
from backend.reportes import (
    generar_horario_docente,
    generar_carga_academica,
    generar_reporte_conflictos,
    generar_horario_programa,
)

REPORTES_DIR = os.path.join(ROOT_DIR, "reportes_pdf")
os.makedirs(REPORTES_DIR, exist_ok=True)

db = SessionLocal()
generados = 0
errores   = 0

def guardar(nombre_archivo, contenido_bytes):
    global generados
    ruta = os.path.join(REPORTES_DIR, nombre_archivo)
    with open(ruta, "wb") as f:
        f.write(contenido_bytes)
    print(f"  ✅ {nombre_archivo}")
    generados += 1

def error(nombre, e):
    global errores
    print(f"  ❌ {nombre}: {e}")
    errores += 1

# ── 1. Carga académica por periodo ──────────────────────────────────────────
print("\n📄 Generando reportes de carga académica...")
for periodo in ["2025-2", "2026-1"]:
    try:
        pdf = generar_carga_academica(db, periodo)
        guardar(f"carga_{periodo}.pdf", pdf)
    except Exception as e:
        error(f"carga_{periodo}.pdf", e)

# ── 2. Conflictos ────────────────────────────────────────────────────────────
print("\n📄 Generando reporte de conflictos...")
try:
    pdf = generar_reporte_conflictos(db)
    guardar("conflictos_2026-1.pdf", pdf)
except Exception as e:
    error("conflictos_2026-1.pdf", e)

# ── 3. Horario por docente (todos los docentes, periodo 2026-1) ──────────────
print("\n📄 Generando horarios individuales de docentes...")
docentes = db.query(Docente).filter(Docente.activo == True).all()
for doc in docentes:
    nombre_safe = doc.nombre.replace(" ", "_").replace(".", "").replace("/", "-")
    try:
        pdf = generar_horario_docente(db, doc.id, "2026-1")
        guardar(f"horario_{nombre_safe}_2026-1.pdf", pdf)
    except Exception as e:
        error(f"horario_{nombre_safe}_2026-1.pdf", e)

# ── 4. Horario por programa (todos los programas, periodo 2026-1) ────────────
print("\n📄 Generando horarios por programa...")
programas = db.query(Programa).filter(Programa.activo == True).all()
for prog in programas:
    try:
        pdf = generar_horario_programa(db, prog.id, "2026-1")
        guardar(f"horario_programa_{prog.codigo}_2026-1.pdf", pdf)
    except Exception as e:
        error(f"horario_programa_{prog.codigo}_2026-1.pdf", e)

# ── 5. Horario consolidado de todos los docentes (periodo 2025-2) ────────────
print("\n📄 Generando carga académica 2025-2...")
try:
    pdf = generar_carga_academica(db, "2025-2")
    guardar("carga_2025-2.pdf", pdf)
except Exception as e:
    error("carga_2025-2.pdf", e)

db.close()

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("  GENERACIÓN DE PDFs COMPLETADA")
print("="*55)
print(f"  PDFs generados : {generados}")
print(f"  Errores        : {errores}")
print(f"  Carpeta        : {REPORTES_DIR}")
print("="*55)
print("\n🔄 Ahora reinicia la base vectorial ChromaDB:")
print("   En la app → Chatbot RAG → botón '🔄 Reiniciar base'")
print("   O desde terminal: python -c \"import core.rag as r; r.reiniciar_bd()\"")
print()
