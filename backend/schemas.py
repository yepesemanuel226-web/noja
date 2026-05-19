from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# ---- Docente ----
class DocenteCreate(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None

class DocenteUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    activo: Optional[bool] = None

class DocenteOut(BaseModel):
    id: str
    nombre: str
    email: str
    telefono: Optional[str]
    activo: bool
    class Config: from_attributes = True

# ---- Programa ----
class ProgramaCreate(BaseModel):
    nombre: str
    codigo: str

class ProgramaOut(BaseModel):
    id: str
    nombre: str
    codigo: str
    activo: bool
    class Config: from_attributes = True

# ---- Materia ----
class MateriaCreate(BaseModel):
    nombre: str
    codigo: str
    horas_semanales: Optional[str] = "2"
    programa_id: Optional[str] = None

class MateriaOut(BaseModel):
    id: str
    nombre: str
    codigo: str
    horas_semanales: str
    programa_id: Optional[str]
    activo: bool
    class Config: from_attributes = True

# ---- Salon ----
class SalonCreate(BaseModel):
    nombre: str
    capacidad: Optional[str] = "30"
    edificio: Optional[str] = None

class SalonOut(BaseModel):
    id: str
    nombre: str
    capacidad: str
    edificio: Optional[str]
    activo: bool
    class Config: from_attributes = True

# ---- Grupo ----
class GrupoCreate(BaseModel):
    nombre: str
    periodo: str
    programa_id: Optional[str] = None

class GrupoOut(BaseModel):
    id: str
    nombre: str
    periodo: str
    programa_id: Optional[str]
    activo: bool
    class Config: from_attributes = True

# ---- Disponibilidad ----
class DisponibilidadCreate(BaseModel):
    docente_id: str
    dia: str
    hora_inicio: str
    hora_fin: str

class DisponibilidadOut(BaseModel):
    id: str
    docente_id: str
    dia: str
    hora_inicio: str
    hora_fin: str
    class Config: from_attributes = True

# ---- Asignacion ----
class AsignacionCreate(BaseModel):
    docente_id: str
    grupo_id: str
    salon_id: str
    materia_id: Optional[str] = None
    dia: str
    hora_inicio: str
    hora_fin: str
    periodo: str

class AsignacionOut(BaseModel):
    id: str
    docente_id: str
    grupo_id: str
    salon_id: str
    materia_id: Optional[str]
    dia: str
    hora_inicio: str
    hora_fin: str
    periodo: str
    class Config: from_attributes = True

# ---- Conflicto ----
class ConflictoOut(BaseModel):
    id: str
    tipo: str
    descripcion: Optional[str]
    asignacion_id: Optional[str]
    resuelto: bool
    class Config: from_attributes = True

# ---- Solicitud Cambio ----
class SolicitudCambioCreate(BaseModel):
    asignacion_id: str
    docente_id: str
    motivo: Optional[str] = None
    nuevo_dia: Optional[str] = None
    nueva_hora_inicio: Optional[str] = None
    nueva_hora_fin: Optional[str] = None
    nuevo_salon_id: Optional[str] = None

class SolicitudCambioOut(BaseModel):
    id: str
    asignacion_id: str
    docente_id: str
    motivo: Optional[str]
    nuevo_dia: Optional[str]
    nueva_hora_inicio: Optional[str]
    nueva_hora_fin: Optional[str]
    estado: str
    class Config: from_attributes = True
