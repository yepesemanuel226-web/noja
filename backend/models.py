import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Docente(Base):
    __tablename__ = "docentes"
    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    disponibilidades = relationship("Disponibilidad", back_populates="docente", cascade="all, delete-orphan")
    asignaciones = relationship("Asignacion", back_populates="docente", cascade="all, delete-orphan")

class Programa(Base):
    __tablename__ = "programas"
    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    codigo = Column(String, unique=True, nullable=False)
    activo = Column(Boolean, default=True)
    materias = relationship("Materia", back_populates="programa")

class Materia(Base):
    __tablename__ = "materias"
    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    codigo = Column(String, nullable=False)
    horas_semanales = Column(String, default="2")
    programa_id = Column(String, ForeignKey("programas.id"))
    activo = Column(Boolean, default=True)
    programa = relationship("Programa", back_populates="materias")

class Salon(Base):
    __tablename__ = "salones"
    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    capacidad = Column(String, default="30")
    edificio = Column(String)
    activo = Column(Boolean, default=True)
    asignaciones = relationship("Asignacion", back_populates="salon")

class Grupo(Base):
    __tablename__ = "grupos"
    id = Column(String, primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    periodo = Column(String, nullable=False)
    programa_id = Column(String, ForeignKey("programas.id"))
    activo = Column(Boolean, default=True)
    asignaciones = relationship("Asignacion", back_populates="grupo")

class Disponibilidad(Base):
    __tablename__ = "disponibilidades"
    id = Column(String, primary_key=True, default=gen_uuid)
    docente_id = Column(String, ForeignKey("docentes.id"), nullable=False)
    dia = Column(String, nullable=False)
    hora_inicio = Column(String, nullable=False)
    hora_fin = Column(String, nullable=False)
    docente = relationship("Docente", back_populates="disponibilidades")

class Asignacion(Base):
    __tablename__ = "asignaciones"
    id = Column(String, primary_key=True, default=gen_uuid)
    docente_id = Column(String, ForeignKey("docentes.id"), nullable=False)
    grupo_id = Column(String, ForeignKey("grupos.id"), nullable=False)
    salon_id = Column(String, ForeignKey("salones.id"), nullable=False)
    materia_id = Column(String, ForeignKey("materias.id"))
    dia = Column(String, nullable=False)
    hora_inicio = Column(String, nullable=False)
    hora_fin = Column(String, nullable=False)
    periodo = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    docente = relationship("Docente", back_populates="asignaciones")
    grupo = relationship("Grupo", back_populates="asignaciones")
    salon = relationship("Salon", back_populates="asignaciones")
    materia = relationship("Materia")

class Conflicto(Base):
    __tablename__ = "conflictos"
    id = Column(String, primary_key=True, default=gen_uuid)
    tipo = Column(String, nullable=False)
    descripcion = Column(Text)
    asignacion_id = Column(String, ForeignKey("asignaciones.id"))
    resuelto = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class SolicitudCambio(Base):
    __tablename__ = "solicitudes_cambio"
    id = Column(String, primary_key=True, default=gen_uuid)
    asignacion_id = Column(String, ForeignKey("asignaciones.id"), nullable=False)
    docente_id = Column(String, ForeignKey("docentes.id"), nullable=False)
    motivo = Column(Text)
    nuevo_dia = Column(String)
    nueva_hora_inicio = Column(String)
    nueva_hora_fin = Column(String)
    nuevo_salon_id = Column(String, ForeignKey("salones.id"))
    estado = Column(String, default="pendiente")
    created_at = Column(DateTime, server_default=func.now())
