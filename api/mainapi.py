import os, sys, uuid, hashlib, re
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import (
    create_engine, Column, String, Boolean,
    Integer, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from pydantic import BaseModel

# ── Path para encontrar config.py en la raíz ──────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from config import DATABASE_URL as _CFG_URL

# ══════════════════════════════════════════════════════
# BASE DE DATOS — Supabase PostgreSQL (Session Pooler puerto 6543)
# ══════════════════════════════════════════════════════
os.makedirs("reportes_pdf", exist_ok=True)

# 1. Variable de entorno tiene prioridad
# 2. Si no, usamos config.py tal cual (ya apunta al pooler IPv4)
_env_url = os.getenv("DATABASE_URL")
DATABASE_URL = _env_url if _env_url else _CFG_URL

# Eliminar pgbouncer=true si existe (psycopg2 no lo acepta)
DATABASE_URL = re.sub(r'[&?]pgbouncer=true', '', DATABASE_URL)

# Agregar sslmode=require si no está
if "pooler.supabase.com" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + sep + "sslmode=require"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 10},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def new_id():
    return str(uuid.uuid4())

# ══════════════════════════════════════════════════════
# MODELOS (tablas)
# ══════════════════════════════════════════════════════
class Docente(Base):
    __tablename__ = "docentes"
    id          = Column(String, primary_key=True, default=new_id)
    nombre      = Column(String(120), nullable=False)
    email       = Column(String(120), unique=True, nullable=False)
    telefono    = Column(String(20))
    telegram_id = Column(String(50))
    horas_min   = Column(Integer, default=4)
    horas_max   = Column(Integer, default=20)
    activo      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    disponibilidad = relationship("Disponibilidad", back_populates="docente", cascade="all,delete")
    asignaciones   = relationship("Asignacion",     back_populates="docente", cascade="all,delete")
    solicitudes    = relationship("SolicitudCambio", back_populates="docente")

class Programa(Base):
    __tablename__ = "programas"
    id         = Column(String, primary_key=True, default=new_id)
    nombre     = Column(String(120), nullable=False)
    codigo     = Column(String(20),  unique=True, nullable=False)
    activo     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    materias   = relationship("Materia", back_populates="programa")
    grupos     = relationship("Grupo",   back_populates="programa")

class Materia(Base):
    __tablename__ = "materias"
    id          = Column(String, primary_key=True, default=new_id)
    nombre      = Column(String(120), nullable=False)
    codigo      = Column(String(20),  unique=True, nullable=False)
    creditos    = Column(Integer, default=3)
    horas_sem   = Column(Integer, default=3)
    programa_id = Column(String, ForeignKey("programas.id"), nullable=False)
    activo      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    programa     = relationship("Programa",   back_populates="materias")
    asignaciones = relationship("Asignacion", back_populates="materia")

class Salon(Base):
    __tablename__ = "salones"
    id         = Column(String, primary_key=True, default=new_id)
    nombre     = Column(String(80),  nullable=False)
    codigo     = Column(String(20),  unique=True, nullable=False)
    capacidad  = Column(Integer, default=30)
    tipo       = Column(String(50),  default="aula")
    activo     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    asignaciones = relationship("Asignacion", back_populates="salon")

class Grupo(Base):
    __tablename__ = "grupos"
    id          = Column(String, primary_key=True, default=new_id)
    nombre      = Column(String(80),  nullable=False)
    periodo     = Column(String(20),  nullable=False)
    programa_id = Column(String, ForeignKey("programas.id"), nullable=False)
    activo      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    programa     = relationship("Programa",   back_populates="grupos")
    asignaciones = relationship("Asignacion", back_populates="grupo")

class Disponibilidad(Base):
    __tablename__ = "disponibilidad"
    __table_args__ = (UniqueConstraint("docente_id", "dia", "hora_inicio", name="uq_disp"),)
    id          = Column(String, primary_key=True, default=new_id)
    docente_id  = Column(String, ForeignKey("docentes.id"), nullable=False)
    dia         = Column(String(15), nullable=False)
    hora_inicio = Column(String(5),  nullable=False)
    hora_fin    = Column(String(5),  nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    docente     = relationship("Docente", back_populates="disponibilidad")

class Asignacion(Base):
    __tablename__ = "asignaciones"
    id          = Column(String, primary_key=True, default=new_id)
    docente_id  = Column(String, ForeignKey("docentes.id"),  nullable=False)
    materia_id  = Column(String, ForeignKey("materias.id"),  nullable=False)
    grupo_id    = Column(String, ForeignKey("grupos.id"),    nullable=False)
    salon_id    = Column(String, ForeignKey("salones.id"),   nullable=False)
    dia         = Column(String(15), nullable=False)
    hora_inicio = Column(String(5),  nullable=False)
    hora_fin    = Column(String(5),  nullable=False)
    periodo     = Column(String(20), nullable=False)
    activo      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    docente     = relationship("Docente",       back_populates="asignaciones")
    materia     = relationship("Materia",       back_populates="asignaciones")
    grupo       = relationship("Grupo",         back_populates="asignaciones")
    salon       = relationship("Salon",         back_populates="asignaciones")
    conflictos  = relationship("Conflicto",      back_populates="asignacion", cascade="all,delete")
    solicitudes = relationship("SolicitudCambio", back_populates="asignacion")

class Conflicto(Base):
    __tablename__ = "conflictos"
    id            = Column(String, primary_key=True, default=new_id)
    asignacion_id = Column(String, ForeignKey("asignaciones.id"), nullable=False)
    tipo             = Column(String(50), nullable=False)
    descripcion      = Column(Text,       nullable=False)
    docente_recurso  = Column(String(120))
    dia              = Column(String(20))
    hora             = Column(String(20))
    estado_conflicto = Column(String(20), default="Pendiente")
    resuelto         = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)
    asignacion       = relationship("Asignacion", back_populates="conflictos")

class SolicitudCambio(Base):
    __tablename__ = "solicitudes_cambio"
    id            = Column(String, primary_key=True, default=new_id)
    asignacion_id = Column(String, ForeignKey("asignaciones.id"), nullable=False)
    docente_id    = Column(String, ForeignKey("docentes.id"),     nullable=False)
    motivo        = Column(Text, nullable=False)
    estado        = Column(String(20), default="pendiente")
    respuesta     = Column(Text)
    created_at    = Column(DateTime, default=datetime.utcnow)
    asignacion    = relationship("Asignacion",    back_populates="solicitudes")
    docente       = relationship("Docente",        back_populates="solicitudes")

class Reporte(Base):
    __tablename__ = "reportes"
    id         = Column(String, primary_key=True, default=new_id)
    tipo       = Column(String(60), nullable=False)
    ruta_pdf   = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class UsuarioSistema(Base):
    __tablename__ = "usuarios_sistema"
    id         = Column(String, primary_key=True, default=new_id)
    email      = Column(String(120), unique=True, nullable=False)
    nombre     = Column(String(120), nullable=False)
    password   = Column(String(255), nullable=False)
    rol        = Column(String(30),  default="coordinador")
    activo     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ══════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════
class DocenteIn(BaseModel):
    nombre: str; email: str
    telefono: Optional[str] = None; telegram_id: Optional[str] = None
    horas_min: int = 4; horas_max: int = 20

class DocenteOut(DocenteIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class ProgramaIn(BaseModel):
    nombre: str; codigo: str

class ProgramaOut(ProgramaIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class MateriaIn(BaseModel):
    nombre: str; codigo: str; creditos: int = 3; horas_sem: int = 3; programa_id: str

class MateriaOut(MateriaIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class SalonIn(BaseModel):
    nombre: str; codigo: str; capacidad: int = 30; tipo: str = "aula"

class SalonOut(SalonIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class GrupoIn(BaseModel):
    nombre: str; periodo: str; programa_id: str

class GrupoOut(GrupoIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class DisponibilidadIn(BaseModel):
    docente_id: str; dia: str; hora_inicio: str; hora_fin: str

class DisponibilidadOut(DisponibilidadIn):
    id: str; created_at: datetime
    class Config: from_attributes = True

class AsignacionIn(BaseModel):
    docente_id: str; materia_id: str; grupo_id: str; salon_id: str
    dia: str; hora_inicio: str; hora_fin: str; periodo: str

class AsignacionOut(AsignacionIn):
    id: str; activo: bool; created_at: datetime
    class Config: from_attributes = True

class ConflictoIn(BaseModel):
    asignacion_id: str
    tipo: str
    descripcion: str
    docente_recurso: Optional[str] = None
    dia: Optional[str] = None
    hora: Optional[str] = None
    estado_conflicto: Optional[str] = "Pendiente"
    resuelto: bool = False

class ConflictoOut(BaseModel):
    id: str; asignacion_id: str; tipo: str; descripcion: str
    docente_recurso: Optional[str] = None
    dia: Optional[str] = None
    hora: Optional[str] = None
    estado_conflicto: Optional[str] = "Pendiente"
    resuelto: bool; created_at: datetime
    class Config: from_attributes = True

class SolicitudIn(BaseModel):
    asignacion_id: str; docente_id: str; motivo: str

class SolicitudOut(SolicitudIn):
    id: str; estado: str; respuesta: Optional[str] = None; created_at: datetime
    class Config: from_attributes = True

class SolicitudResp(BaseModel):
    respuesta: Optional[str] = None

class ReporteOut(BaseModel):
    id: str; tipo: str
    ruta_pdf: Optional[str] = None; created_at: datetime
    class Config: from_attributes = True

class LoginIn(BaseModel):
    email: str; password: str

class LoginOut(BaseModel):
    access_token: str; token_type: str = "bearer"; usuario: str; rol: str

# ══════════════════════════════════════════════════════
# LÓGICA DE NEGOCIO
# ══════════════════════════════════════════════════════
def _min(h: str) -> int:
    a, b = h.split(":"); return int(a) * 60 + int(b)

def _solapan(ia, fa, ib, fb) -> bool:
    return _min(ia) < _min(fb) and _min(fa) > _min(ib)

def _detectar_conflictos(db: Session, asig: Asignacion) -> list:
    res = []
    for o in db.query(Asignacion).filter(
        Asignacion.docente_id == asig.docente_id, Asignacion.dia == asig.dia,
        Asignacion.activo == True, Asignacion.id != asig.id
    ).all():
        if _solapan(asig.hora_inicio, asig.hora_fin, o.hora_inicio, o.hora_fin):
            res.append({"tipo": "docente_cruce", "descripcion":
                f"Docente doble asignación el {asig.dia}: {asig.hora_inicio}-{asig.hora_fin} y {o.hora_inicio}-{o.hora_fin}."})
    for o in db.query(Asignacion).filter(
        Asignacion.salon_id == asig.salon_id, Asignacion.dia == asig.dia,
        Asignacion.activo == True, Asignacion.id != asig.id
    ).all():
        if _solapan(asig.hora_inicio, asig.hora_fin, o.hora_inicio, o.hora_fin):
            res.append({"tipo": "salon_cruce", "descripcion":
                f"Salón ocupado el {asig.dia} {asig.hora_inicio}-{asig.hora_fin}."})
    doc = db.query(Docente).filter_by(id=asig.docente_id).first()
    if doc:
        total = sum(_min(a.hora_fin) - _min(a.hora_inicio)
            for a in db.query(Asignacion).filter_by(
                docente_id=doc.id, periodo=asig.periodo, activo=True).all()) / 60
        if total > doc.horas_max:
            res.append({"tipo": "sobrecarga", "descripcion":
                f"Docente lleva {total:.1f}h, supera máximo de {doc.horas_max}h."})
    return res

def _carga(db: Session, docente_id: str, periodo: str) -> dict:
    doc = db.query(Docente).filter_by(id=docente_id).first()
    if not doc: return {}
    asigs = db.query(Asignacion).filter_by(docente_id=docente_id, periodo=periodo, activo=True).all()
    total = sum(_min(a.hora_fin) - _min(a.hora_inicio) for a in asigs) / 60
    return {
        "docente_id": doc.id, "nombre_docente": doc.nombre,
        "horas_asignadas": round(total, 2), "horas_min": doc.horas_min, "horas_max": doc.horas_max,
        "estado": "sobrecarga" if total > doc.horas_max else "subcarga" if total < doc.horas_min else "ok"
    }

def _dia_hoy() -> str:
    return ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][datetime.now().weekday()]

# ── PDFs ──────────────────────────────────────────────────────────────────────
PDF_DIR = "reportes_pdf"

def _pdf_horario_docente(db: Session, docente_id: str, periodo: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    doc = db.query(Docente).filter_by(id=docente_id).first()
    if not doc: raise ValueError("Docente no encontrado")
    asigs = db.query(Asignacion).filter_by(docente_id=docente_id, periodo=periodo, activo=True)\
              .order_by(Asignacion.dia, Asignacion.hora_inicio).all()
    fname = f"{PDF_DIR}/horario_{doc.nombre.replace(' ','_')}_{periodo}.pdf"
    d = SimpleDocTemplate(fname, pagesize=A4)
    s = getSampleStyleSheet()
    story = [Paragraph(f"Horario: {doc.nombre}", s["Title"]),
             Paragraph(f"Período: {periodo}", s["Normal"]), Spacer(1, 12)]
    data = [["Día", "Inicio", "Fin", "Materia", "Grupo", "Salón"]]
    for a in asigs:
        data.append([a.dia, a.hora_inicio, a.hora_fin,
                     a.materia.nombre if a.materia else "-",
                     a.grupo.nombre   if a.grupo   else "-",
                     a.salon.nombre   if a.salon   else "-"])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",  (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t); d.build(story)
    return fname

def _pdf_horario_programa(db: Session, programa_id: str, periodo: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    prog = db.query(Programa).filter_by(id=programa_id).first()
    if not prog: raise ValueError("Programa no encontrado")
    grupos = db.query(Grupo).filter_by(programa_id=programa_id, activo=True).all()
    grupo_ids = [g.id for g in grupos]
    asigs = db.query(Asignacion).filter(
        Asignacion.grupo_id.in_(grupo_ids), Asignacion.periodo == periodo, Asignacion.activo == True
    ).order_by(Asignacion.dia, Asignacion.hora_inicio).all()
    fname = f"{PDF_DIR}/horario_programa_{prog.codigo}_{periodo}.pdf"
    d = SimpleDocTemplate(fname, pagesize=A4)
    s = getSampleStyleSheet()
    story = [Paragraph(f"Horario Programa: {prog.nombre}", s["Title"]),
             Paragraph(f"Período: {periodo}", s["Normal"]), Spacer(1, 12)]
    data = [["Día", "Inicio", "Fin", "Materia", "Docente", "Grupo", "Salón"]]
    for a in asigs:
        data.append([a.dia, a.hora_inicio, a.hora_fin,
                     a.materia.nombre if a.materia else "-",
                     a.docente.nombre if a.docente else "-",
                     a.grupo.nombre   if a.grupo   else "-",
                     a.salon.nombre   if a.salon   else "-"])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",  (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t); d.build(story)
    return fname

def _pdf_carga(db: Session, periodo: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    fname = f"{PDF_DIR}/carga_{periodo}.pdf"
    d = SimpleDocTemplate(fname, pagesize=A4)
    s = getSampleStyleSheet()
    story = [Paragraph(f"Carga Académica — {periodo}", s["Title"]), Spacer(1, 12)]
    data = [["Docente", "Horas", "Mín", "Máx", "Estado"]]
    for doc in db.query(Docente).filter_by(activo=True).all():
        c = _carga(db, doc.id, periodo)
        data.append([doc.nombre, f"{c.get('horas_asignadas', 0):.1f}",
                     str(doc.horas_min), str(doc.horas_max), c.get("estado", "").upper()])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",  (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t); d.build(story)
    return fname

def _pdf_conflictos(db: Session, periodo: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    fname = f"{PDF_DIR}/conflictos_{periodo}.pdf"
    d = SimpleDocTemplate(fname, pagesize=A4)
    s = getSampleStyleSheet()
    story = [Paragraph(f"Conflictos — {periodo}", s["Title"]),
             Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", s["Normal"]),
             Spacer(1, 12)]
    # Filtrar conflictos por periodo a través de la asignación relacionada
    conflictos = (
        db.query(Conflicto)
        .join(Asignacion, Conflicto.asignacion_id == Asignacion.id)
        .filter(Asignacion.periodo == periodo)
        .all()
    )
    if not conflictos:
        story.append(Paragraph(f"Sin conflictos detectados para el período {periodo}.", s["Normal"]))
    else:
        data = [["Tipo", "Descripción", "Día", "Hora", "Estado"]]
        for c in conflictos:
            data.append([
                c.tipo,
                c.descripcion[:60] + ("..." if len(c.descripcion) > 60 else ""),
                c.dia or "-",
                c.hora or "-",
                "✓ Resuelto" if c.resuelto else "✗ Pendiente"
            ])
        t = Table(data, colWidths=[90, 240, 60, 60, 70], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#c0392b")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fdf0f0")]),
            ("GRID",    (0,0), (-1,-1), 0.5, colors.grey),
            ("FONTSIZE",(0,0), (-1,-1), 9),
            ("PADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(t)
    d.build(story)
    return fname

# ══════════════════════════════════════════════════════
# APP FASTAPI
# ══════════════════════════════════════════════════════
app = FastAPI(title="NOJA — Gestión de Horarios", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

P = "/api/v1"

# ── STARTUP — create_all va aquí, NO en nivel de módulo ───────────────────────
@app.on_event("startup")
async def startup_event():
    print("=" * 55)
    print("  Iniciando NOJA — API de Gestión de Horarios")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("  ✅ Tablas verificadas en Supabase")
    except Exception as e:
        print(f"  ⚠️  create_all falló (puede ignorarse si las tablas ya existen): {e}")
    try:
        host_info = DATABASE_URL.split("@")[1].split("/")[0]
    except Exception:
        host_info = "desconocido"
    print(f"  DB host: {host_info}")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 55)

# ── DOCENTES ──────────────────────────────────────────────────────────────────
@app.get(P+"/docentes", response_model=List[DocenteOut])
def get_docentes(db: Session = Depends(get_db)):
    return db.query(Docente).filter_by(activo=True).all()

@app.get(P+"/docentes/{id}", response_model=DocenteOut)
def get_docente(id: str, db: Session = Depends(get_db)):
    d = db.query(Docente).filter_by(id=id).first()
    if not d: raise HTTPException(404)
    return d

@app.post(P+"/docentes", response_model=DocenteOut, status_code=201)
def post_docente(data: DocenteIn, db: Session = Depends(get_db)):
    d = Docente(**data.model_dump()); db.add(d); db.commit(); db.refresh(d); return d

@app.put(P+"/docentes/{id}", response_model=DocenteOut)
def put_docente(id: str, data: DocenteIn, db: Session = Depends(get_db)):
    d = db.query(Docente).filter_by(id=id).first()
    if not d: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(d, k, v)
    db.commit(); db.refresh(d); return d

@app.delete(P+"/docentes/{id}")
def del_docente(id: str, db: Session = Depends(get_db)):
    d = db.query(Docente).filter_by(id=id).first()
    if not d: raise HTTPException(404)
    d.activo = False; db.commit(); return {"ok": True}

@app.get(P+"/docentes/{id}/horario", response_model=List[AsignacionOut])
def get_horario_docente(id: str, periodo: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Asignacion).filter_by(docente_id=id, activo=True)
    if periodo: q = q.filter_by(periodo=periodo)
    return q.order_by(Asignacion.dia, Asignacion.hora_inicio).all()

@app.get(P+"/docentes/{id}/carga")
def get_carga_docente(id: str, periodo: str = Query(...), db: Session = Depends(get_db)):
    c = _carga(db, id, periodo)
    if not c: raise HTTPException(404)
    return c

@app.get(P+"/docentes/{id}/horario/hoy", response_model=List[AsignacionOut])
def get_horario_hoy(id: str, periodo: str = Query(...), db: Session = Depends(get_db)):
    return db.query(Asignacion).filter_by(
        docente_id=id, dia=_dia_hoy(), periodo=periodo, activo=True
    ).order_by(Asignacion.hora_inicio).all()

# ── PROGRAMAS ─────────────────────────────────────────────────────────────────
@app.get(P+"/programas", response_model=List[ProgramaOut])
def get_programas(db: Session = Depends(get_db)):
    return db.query(Programa).filter_by(activo=True).all()

@app.get(P+"/programas/{id}", response_model=ProgramaOut)
def get_programa(id: str, db: Session = Depends(get_db)):
    p = db.query(Programa).filter_by(id=id).first()
    if not p: raise HTTPException(404)
    return p

@app.post(P+"/programas", response_model=ProgramaOut, status_code=201)
def post_programa(data: ProgramaIn, db: Session = Depends(get_db)):
    p = Programa(**data.model_dump()); db.add(p); db.commit(); db.refresh(p); return p

@app.put(P+"/programas/{id}", response_model=ProgramaOut)
def put_programa(id: str, data: ProgramaIn, db: Session = Depends(get_db)):
    p = db.query(Programa).filter_by(id=id).first()
    if not p: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(p, k, v)
    db.commit(); db.refresh(p); return p

@app.delete(P+"/programas/{id}")
def del_programa(id: str, db: Session = Depends(get_db)):
    p = db.query(Programa).filter_by(id=id).first()
    if not p: raise HTTPException(404)
    p.activo = False; db.commit(); return {"ok": True}

# ── MATERIAS ──────────────────────────────────────────────────────────────────
@app.get(P+"/materias", response_model=List[MateriaOut])
def get_materias(programa_id: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Materia).filter_by(activo=True)
    if programa_id: q = q.filter_by(programa_id=programa_id)
    return q.all()

@app.get(P+"/materias/{id}", response_model=MateriaOut)
def get_materia(id: str, db: Session = Depends(get_db)):
    m = db.query(Materia).filter_by(id=id).first()
    if not m: raise HTTPException(404)
    return m

@app.post(P+"/materias", response_model=MateriaOut, status_code=201)
def post_materia(data: MateriaIn, db: Session = Depends(get_db)):
    m = Materia(**data.model_dump()); db.add(m); db.commit(); db.refresh(m); return m

@app.put(P+"/materias/{id}", response_model=MateriaOut)
def put_materia(id: str, data: MateriaIn, db: Session = Depends(get_db)):
    m = db.query(Materia).filter_by(id=id).first()
    if not m: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(m, k, v)
    db.commit(); db.refresh(m); return m

@app.delete(P+"/materias/{id}")
def del_materia(id: str, db: Session = Depends(get_db)):
    m = db.query(Materia).filter_by(id=id).first()
    if not m: raise HTTPException(404)
    m.activo = False; db.commit(); return {"ok": True}

# ── SALONES ───────────────────────────────────────────────────────────────────
@app.get(P+"/salones/disponibles", response_model=List[SalonOut])
def get_salones_disponibles(dia: str, hora_inicio: str, hora_fin: str, db: Session = Depends(get_db)):
    todos = db.query(Salon).filter_by(activo=True).all()
    libres = []
    for s in todos:
        asigs = db.query(Asignacion).filter_by(salon_id=s.id, dia=dia, activo=True).all()
        if not any(_solapan(hora_inicio, hora_fin, a.hora_inicio, a.hora_fin) for a in asigs):
            libres.append(s)
    return libres

@app.get(P+"/salones", response_model=List[SalonOut])
def get_salones(db: Session = Depends(get_db)):
    return db.query(Salon).filter_by(activo=True).all()

@app.get(P+"/salones/{id}", response_model=SalonOut)
def get_salon(id: str, db: Session = Depends(get_db)):
    s = db.query(Salon).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    return s

@app.post(P+"/salones", response_model=SalonOut, status_code=201)
def post_salon(data: SalonIn, db: Session = Depends(get_db)):
    s = Salon(**data.model_dump()); db.add(s); db.commit(); db.refresh(s); return s

@app.put(P+"/salones/{id}", response_model=SalonOut)
def put_salon(id: str, data: SalonIn, db: Session = Depends(get_db)):
    s = db.query(Salon).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(s, k, v)
    db.commit(); db.refresh(s); return s

@app.delete(P+"/salones/{id}")
def del_salon(id: str, db: Session = Depends(get_db)):
    s = db.query(Salon).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    s.activo = False; db.commit(); return {"ok": True}

# ── GRUPOS ────────────────────────────────────────────────────────────────────
@app.get(P+"/grupos", response_model=List[GrupoOut])
def get_grupos(periodo: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Grupo).filter_by(activo=True)
    if periodo: q = q.filter_by(periodo=periodo)
    return q.all()

@app.get(P+"/grupos/{id}", response_model=GrupoOut)
def get_grupo(id: str, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter_by(id=id).first()
    if not g: raise HTTPException(404)
    return g

@app.post(P+"/grupos", response_model=GrupoOut, status_code=201)
def post_grupo(data: GrupoIn, db: Session = Depends(get_db)):
    g = Grupo(**data.model_dump()); db.add(g); db.commit(); db.refresh(g); return g

@app.put(P+"/grupos/{id}", response_model=GrupoOut)
def put_grupo(id: str, data: GrupoIn, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter_by(id=id).first()
    if not g: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(g, k, v)
    db.commit(); db.refresh(g); return g

@app.delete(P+"/grupos/{id}")
def del_grupo(id: str, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter_by(id=id).first()
    if not g: raise HTTPException(404)
    g.activo = False; db.commit(); return {"ok": True}

# ── DISPONIBILIDAD ────────────────────────────────────────────────────────────
@app.get(P+"/disponibilidad/check")
def check_disponibilidad(docente_id: str, dia: str, hora_inicio: str, hora_fin: str,
                          db: Session = Depends(get_db)):
    franjas = db.query(Disponibilidad).filter_by(docente_id=docente_id, dia=dia).all()
    return {"disponible": any(_solapan(hora_inicio, hora_fin, f.hora_inicio, f.hora_fin) for f in franjas)}

@app.get(P+"/disponibilidad/{docente_id}", response_model=List[DisponibilidadOut])
def get_disponibilidad(docente_id: str, db: Session = Depends(get_db)):
    return db.query(Disponibilidad).filter_by(docente_id=docente_id).all()

@app.post(P+"/disponibilidad", response_model=DisponibilidadOut, status_code=201)
def post_disponibilidad(data: DisponibilidadIn, db: Session = Depends(get_db)):
    d = Disponibilidad(**data.model_dump()); db.add(d); db.commit(); db.refresh(d); return d

@app.put(P+"/disponibilidad/{id}", response_model=DisponibilidadOut)
def put_disponibilidad(id: str, data: DisponibilidadIn, db: Session = Depends(get_db)):
    d = db.query(Disponibilidad).filter_by(id=id).first()
    if not d: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(d, k, v)
    db.commit(); db.refresh(d); return d

@app.delete(P+"/disponibilidad/{id}")
def del_disponibilidad(id: str, db: Session = Depends(get_db)):
    d = db.query(Disponibilidad).filter_by(id=id).first()
    if not d: raise HTTPException(404)
    db.delete(d); db.commit(); return {"ok": True}

# ── ASIGNACIONES ──────────────────────────────────────────────────────────────
@app.get(P+"/asignaciones", response_model=List[AsignacionOut])
def get_asignaciones(periodo: str = Query(None), docente_id: str = Query(None),
                     dia: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Asignacion).filter_by(activo=True)
    if periodo:    q = q.filter_by(periodo=periodo)
    if docente_id: q = q.filter_by(docente_id=docente_id)
    if dia:        q = q.filter_by(dia=dia)
    return q.order_by(Asignacion.dia, Asignacion.hora_inicio).all()

@app.get(P+"/asignaciones/docente/{id}/hoy", response_model=List[AsignacionOut])
def get_asignaciones_hoy(id: str, periodo: str = Query(...), db: Session = Depends(get_db)):
    return db.query(Asignacion).filter_by(
        docente_id=id, dia=_dia_hoy(), periodo=periodo, activo=True
    ).order_by(Asignacion.hora_inicio).all()

@app.get(P+"/asignaciones/{id}", response_model=AsignacionOut)
def get_asignacion(id: str, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter_by(id=id).first()
    if not a: raise HTTPException(404)
    return a

@app.post(P+"/asignaciones", response_model=AsignacionOut, status_code=201)
def post_asignacion(data: AsignacionIn, db: Session = Depends(get_db)):
    a = Asignacion(**data.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    for c in _detectar_conflictos(db, a):
        db.add(Conflicto(asignacion_id=a.id, **c))
    db.commit(); return a

@app.put(P+"/asignaciones/{id}", response_model=AsignacionOut)
def put_asignacion(id: str, data: AsignacionIn, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter_by(id=id).first()
    if not a: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(a, k, v)
    db.commit(); db.refresh(a)
    db.query(Conflicto).filter_by(asignacion_id=id).delete()
    for c in _detectar_conflictos(db, a):
        db.add(Conflicto(asignacion_id=a.id, **c))
    db.commit(); return a

@app.delete(P+"/asignaciones/{id}")
def del_asignacion(id: str, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter_by(id=id).first()
    if not a: raise HTTPException(404)
    a.activo = False; db.commit(); return {"ok": True}

# ── CONFLICTOS ────────────────────────────────────────────────────────────────
@app.get(P+"/conflictos", response_model=List[ConflictoOut])
def get_conflictos(resuelto: bool = Query(None), db: Session = Depends(get_db)):
    q = db.query(Conflicto)
    if resuelto is not None: q = q.filter_by(resuelto=resuelto)
    return q.all()

@app.post(P+"/conflictos", response_model=ConflictoOut, status_code=201)
def post_conflicto(data: ConflictoIn, db: Session = Depends(get_db)):
    c = Conflicto(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c); return c

@app.get(P+"/conflictos/{id}", response_model=ConflictoOut)
def get_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter_by(id=id).first()
    if not c: raise HTTPException(404)
    return c

@app.patch(P+"/conflictos/{id}/resolver")
def resolver_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter_by(id=id).first()
    if not c: raise HTTPException(404)
    c.resuelto = True; db.commit(); return {"ok": True}

@app.post(P+"/conflictos/detectar")
def detectar_conflictos_todos(db: Session = Depends(get_db)):
    db.query(Conflicto).filter_by(resuelto=False).delete(); db.commit()
    count = 0
    for a in db.query(Asignacion).filter_by(activo=True).all():
        for c in _detectar_conflictos(db, a):
            db.add(Conflicto(asignacion_id=a.id, **c)); count += 1
    db.commit(); return {"detectados": count}

@app.delete(P+"/conflictos/{id}")
def del_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter_by(id=id).first()
    if not c: raise HTTPException(404)
    db.delete(c); db.commit(); return {"ok": True}

# ── SOLICITUDES ───────────────────────────────────────────────────────────────
@app.get(P+"/solicitudes-cambio", response_model=List[SolicitudOut])
def get_solicitudes(estado: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(SolicitudCambio)
    if estado: q = q.filter_by(estado=estado)
    return q.all()

@app.get(P+"/solicitudes-cambio/{id}", response_model=SolicitudOut)
def get_solicitud(id: str, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    return s

@app.post(P+"/solicitudes-cambio", response_model=SolicitudOut, status_code=201)
def post_solicitud(data: SolicitudIn, db: Session = Depends(get_db)):
    s = SolicitudCambio(**data.model_dump()); db.add(s); db.commit(); db.refresh(s); return s

@app.patch(P+"/solicitudes-cambio/{id}/aprobar")
def aprobar_solicitud(id: str, body: SolicitudResp, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    s.estado = "aprobada"; s.respuesta = body.respuesta; db.commit(); return {"ok": True}

@app.patch(P+"/solicitudes-cambio/{id}/rechazar")
def rechazar_solicitud(id: str, body: SolicitudResp, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter_by(id=id).first()
    if not s: raise HTTPException(404)
    s.estado = "rechazada"; s.respuesta = body.respuesta; db.commit(); return {"ok": True}

# ── REPORTES ──────────────────────────────────────────────────────────────────
@app.get(P+"/reportes", response_model=List[ReporteOut])
def get_reportes(db: Session = Depends(get_db)):
    return db.query(Reporte).order_by(Reporte.created_at.desc()).all()

@app.post(P+"/reportes/horario-docente")
def reporte_horario_docente(docente_id: str = Query(...), periodo: str = Query(...),
                             db: Session = Depends(get_db)):
    ruta = _pdf_horario_docente(db, docente_id, periodo)
    r = Reporte(tipo="horario_docente", ruta_pdf=ruta); db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ruta": ruta}

@app.post(P+"/reportes/horario-programa")
def reporte_horario_programa(programa_id: str = Query(...), periodo: str = Query(...),
                              db: Session = Depends(get_db)):
    ruta = _pdf_horario_programa(db, programa_id, periodo)
    r = Reporte(tipo="horario_programa", ruta_pdf=ruta); db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ruta": ruta}

@app.post(P+"/reportes/carga-academica")
def reporte_carga(periodo: str = Query(...), db: Session = Depends(get_db)):
    ruta = _pdf_carga(db, periodo)
    r = Reporte(tipo="carga_academica", ruta_pdf=ruta); db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ruta": ruta}

@app.post(P+"/reportes/conflictos")
def reporte_conflictos(periodo: str = Query(...), db: Session = Depends(get_db)):
    ruta = _pdf_conflictos(db, periodo)
    r = Reporte(tipo="conflictos", ruta_pdf=ruta); db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ruta": ruta}

@app.get(P+"/reportes/{id}/descargar")
def descargar_reporte(id: str, db: Session = Depends(get_db)):
    r = db.query(Reporte).filter_by(id=id).first()
    if not r or not r.ruta_pdf or not os.path.exists(r.ruta_pdf):
        raise HTTPException(404, "PDF no encontrado")
    return FileResponse(r.ruta_pdf, media_type="application/pdf",
                        filename=os.path.basename(r.ruta_pdf))

# ── AUTH ──────────────────────────────────────────────────────────────────────
def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

@app.post(P+"/auth/login", response_model=LoginOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(UsuarioSistema).filter_by(email=data.email, activo=True).first()
    if not u or u.password != _hash(data.password):
        raise HTTPException(401, "Credenciales incorrectas")
    token = hashlib.sha256(f"{u.id}{datetime.utcnow()}".encode()).hexdigest()
    return {"access_token": token, "token_type": "bearer", "usuario": u.nombre, "rol": u.rol}

@app.post(P+"/auth/logout")
def logout():
    return {"ok": True}

@app.get(P+"/auth/me")
def me():
    return {"message": "Implementar con Supabase JWT"}

@app.post(P+"/auth/refresh")
def refresh():
    return {"message": "Implementar con Supabase JWT"}

@app.post(P+"/auth/registro-inicial", include_in_schema=False)
def registro_inicial(data: LoginIn, nombre: str = Query("Admin"),
                     db: Session = Depends(get_db)):
    if db.query(UsuarioSistema).count() > 0:
        raise HTTPException(403, "Ya existe un usuario registrado")
    u = UsuarioSistema(email=data.email, nombre=nombre,
                       password=_hash(data.password), rol="admin")
    db.add(u); db.commit()
    return {"ok": True, "mensaje": "Usuario admin creado"}

# ── ROOT ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"sistema": "NOJA — Gestión de Horarios", "docs": "/docs", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok"}