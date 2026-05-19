import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.models import (Docente, Programa, Materia, Salon, Grupo,
                              Disponibilidad, Asignacion, Conflicto, SolicitudCambio)
from backend.schemas import *
from backend.utils_conflicts import detectar_conflictos

router = APIRouter()

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
DIA_HOY = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}

# ===================== DOCENTES =====================
@router.get("/docentes", response_model=List[DocenteOut], tags=["Docentes"])
def listar_docentes(db: Session = Depends(get_db)):
    return db.query(Docente).filter(Docente.activo == True).all()

@router.get("/docentes/{id}", response_model=DocenteOut, tags=["Docentes"])
def obtener_docente(id: str, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == id).first()
    if not d: raise HTTPException(404, "Docente no encontrado")
    return d

@router.post("/docentes", response_model=DocenteOut, status_code=201, tags=["Docentes"])
def crear_docente(data: DocenteCreate, db: Session = Depends(get_db)):
    d = Docente(id=str(uuid.uuid4()), **data.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return d

@router.put("/docentes/{id}", response_model=DocenteOut, tags=["Docentes"])
def actualizar_docente(id: str, data: DocenteUpdate, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == id).first()
    if not d: raise HTTPException(404, "Docente no encontrado")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    db.commit(); db.refresh(d)
    return d

@router.delete("/docentes/{id}", tags=["Docentes"])
def eliminar_docente(id: str, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == id).first()
    if not d: raise HTTPException(404, "Docente no encontrado")
    d.activo = False; db.commit()
    return {"mensaje": "Docente desactivado"}

@router.get("/docentes/{id}/horario", tags=["Docentes"])
def horario_docente(id: str, db: Session = Depends(get_db)):
    asigs = db.query(Asignacion).filter(Asignacion.docente_id == id).all()
    return asigs

@router.get("/docentes/{id}/carga", tags=["Docentes"])
def carga_docente(id: str, db: Session = Depends(get_db)):
    asigs = db.query(Asignacion).filter(Asignacion.docente_id == id).all()
    total_horas = sum(
        (int(a.hora_fin.split(":")[0]) * 60 + int(a.hora_fin.split(":")[1])) -
        (int(a.hora_inicio.split(":")[0]) * 60 + int(a.hora_inicio.split(":")[1]))
        for a in asigs
    ) // 60
    return {"docente_id": id, "total_clases": len(asigs), "total_horas_semanales": total_horas}

@router.get("/docentes/{id}/horario/hoy", tags=["Docentes"])
def horario_hoy(id: str, db: Session = Depends(get_db)):
    hoy = DIA_HOY[date.today().weekday()]
    asigs = db.query(Asignacion).filter(
        Asignacion.docente_id == id,
        Asignacion.dia == hoy
    ).all()
    return {"dia": hoy, "asignaciones": asigs}

# ===================== PROGRAMAS =====================
@router.get("/programas", response_model=List[ProgramaOut], tags=["Programas"])
def listar_programas(db: Session = Depends(get_db)):
    return db.query(Programa).filter(Programa.activo == True).all()

@router.get("/programas/{id}", response_model=ProgramaOut, tags=["Programas"])
def obtener_programa(id: str, db: Session = Depends(get_db)):
    p = db.query(Programa).filter(Programa.id == id).first()
    if not p: raise HTTPException(404, "Programa no encontrado")
    return p

@router.post("/programas", response_model=ProgramaOut, status_code=201, tags=["Programas"])
def crear_programa(data: ProgramaCreate, db: Session = Depends(get_db)):
    p = Programa(id=str(uuid.uuid4()), **data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return p

@router.put("/programas/{id}", response_model=ProgramaOut, tags=["Programas"])
def actualizar_programa(id: str, data: ProgramaCreate, db: Session = Depends(get_db)):
    p = db.query(Programa).filter(Programa.id == id).first()
    if not p: raise HTTPException(404, "Programa no encontrado")
    for k, v in data.model_dump().items(): setattr(p, k, v)
    db.commit(); db.refresh(p); return p

@router.delete("/programas/{id}", tags=["Programas"])
def eliminar_programa(id: str, db: Session = Depends(get_db)):
    p = db.query(Programa).filter(Programa.id == id).first()
    if not p: raise HTTPException(404, "Programa no encontrado")
    p.activo = False; db.commit()
    return {"mensaje": "Programa desactivado"}

# ===================== MATERIAS =====================
@router.get("/materias", response_model=List[MateriaOut], tags=["Materias"])
def listar_materias(programa_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Materia).filter(Materia.activo == True)
    if programa_id: q = q.filter(Materia.programa_id == programa_id)
    return q.all()

@router.get("/materias/{id}", response_model=MateriaOut, tags=["Materias"])
def obtener_materia(id: str, db: Session = Depends(get_db)):
    m = db.query(Materia).filter(Materia.id == id).first()
    if not m: raise HTTPException(404, "Materia no encontrada")
    return m

@router.post("/materias", response_model=MateriaOut, status_code=201, tags=["Materias"])
def crear_materia(data: MateriaCreate, db: Session = Depends(get_db)):
    m = Materia(id=str(uuid.uuid4()), **data.model_dump())
    db.add(m); db.commit(); db.refresh(m); return m

@router.put("/materias/{id}", response_model=MateriaOut, tags=["Materias"])
def actualizar_materia(id: str, data: MateriaCreate, db: Session = Depends(get_db)):
    m = db.query(Materia).filter(Materia.id == id).first()
    if not m: raise HTTPException(404, "Materia no encontrada")
    for k, v in data.model_dump().items(): setattr(m, k, v)
    db.commit(); db.refresh(m); return m

@router.delete("/materias/{id}", tags=["Materias"])
def eliminar_materia(id: str, db: Session = Depends(get_db)):
    m = db.query(Materia).filter(Materia.id == id).first()
    if not m: raise HTTPException(404, "Materia no encontrada")
    m.activo = False; db.commit()
    return {"mensaje": "Materia desactivada"}

# ===================== SALONES =====================
@router.get("/salones", response_model=List[SalonOut], tags=["Salones"])
def listar_salones(db: Session = Depends(get_db)):
    return db.query(Salon).filter(Salon.activo == True).all()

@router.get("/salones/disponibles", tags=["Salones"])
def salones_disponibles(dia: str, hora_inicio: str, hora_fin: str, db: Session = Depends(get_db)):
    ocupados_ids = [
        a.salon_id for a in db.query(Asignacion).filter(Asignacion.dia == dia).all()
        if (int(a.hora_inicio.replace(":", "")) < int(hora_fin.replace(":", "")) and
            int(a.hora_fin.replace(":", "")) > int(hora_inicio.replace(":", "")))
    ]
    return db.query(Salon).filter(Salon.activo == True, ~Salon.id.in_(ocupados_ids)).all()

@router.get("/salones/{id}", response_model=SalonOut, tags=["Salones"])
def obtener_salon(id: str, db: Session = Depends(get_db)):
    s = db.query(Salon).filter(Salon.id == id).first()
    if not s: raise HTTPException(404, "Salón no encontrado")
    return s

@router.post("/salones", response_model=SalonOut, status_code=201, tags=["Salones"])
def crear_salon(data: SalonCreate, db: Session = Depends(get_db)):
    s = Salon(id=str(uuid.uuid4()), **data.model_dump())
    db.add(s); db.commit(); db.refresh(s); return s

@router.put("/salones/{id}", response_model=SalonOut, tags=["Salones"])
def actualizar_salon(id: str, data: SalonCreate, db: Session = Depends(get_db)):
    s = db.query(Salon).filter(Salon.id == id).first()
    if not s: raise HTTPException(404, "Salón no encontrado")
    for k, v in data.model_dump().items(): setattr(s, k, v)
    db.commit(); db.refresh(s); return s

@router.delete("/salones/{id}", tags=["Salones"])
def eliminar_salon(id: str, db: Session = Depends(get_db)):
    s = db.query(Salon).filter(Salon.id == id).first()
    if not s: raise HTTPException(404, "Salón no encontrado")
    s.activo = False; db.commit()
    return {"mensaje": "Salón desactivado"}

# ===================== GRUPOS =====================
@router.get("/grupos", response_model=List[GrupoOut], tags=["Grupos"])
def listar_grupos(periodo: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Grupo).filter(Grupo.activo == True)
    if periodo: q = q.filter(Grupo.periodo == periodo)
    return q.all()

@router.get("/grupos/{id}", response_model=GrupoOut, tags=["Grupos"])
def obtener_grupo(id: str, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter(Grupo.id == id).first()
    if not g: raise HTTPException(404, "Grupo no encontrado")
    return g

@router.post("/grupos", response_model=GrupoOut, status_code=201, tags=["Grupos"])
def crear_grupo(data: GrupoCreate, db: Session = Depends(get_db)):
    g = Grupo(id=str(uuid.uuid4()), **data.model_dump())
    db.add(g); db.commit(); db.refresh(g); return g

@router.put("/grupos/{id}", response_model=GrupoOut, tags=["Grupos"])
def actualizar_grupo(id: str, data: GrupoCreate, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter(Grupo.id == id).first()
    if not g: raise HTTPException(404, "Grupo no encontrado")
    for k, v in data.model_dump().items(): setattr(g, k, v)
    db.commit(); db.refresh(g); return g

@router.delete("/grupos/{id}", tags=["Grupos"])
def eliminar_grupo(id: str, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter(Grupo.id == id).first()
    if not g: raise HTTPException(404, "Grupo no encontrado")
    g.activo = False; db.commit()
    return {"mensaje": "Grupo desactivado"}

# ===================== DISPONIBILIDAD =====================
@router.get("/disponibilidad/{docente_id}", response_model=List[DisponibilidadOut], tags=["Disponibilidad"])
def disponibilidad_docente(docente_id: str, db: Session = Depends(get_db)):
    return db.query(Disponibilidad).filter(Disponibilidad.docente_id == docente_id).all()

@router.post("/disponibilidad", response_model=DisponibilidadOut, status_code=201, tags=["Disponibilidad"])
def crear_disponibilidad(data: DisponibilidadCreate, db: Session = Depends(get_db)):
    d = Disponibilidad(id=str(uuid.uuid4()), **data.model_dump())
    db.add(d); db.commit(); db.refresh(d); return d

@router.put("/disponibilidad/{id}", response_model=DisponibilidadOut, tags=["Disponibilidad"])
def actualizar_disponibilidad(id: str, data: DisponibilidadCreate, db: Session = Depends(get_db)):
    d = db.query(Disponibilidad).filter(Disponibilidad.id == id).first()
    if not d: raise HTTPException(404, "Franja no encontrada")
    for k, v in data.model_dump().items(): setattr(d, k, v)
    db.commit(); db.refresh(d); return d

@router.delete("/disponibilidad/{id}", tags=["Disponibilidad"])
def eliminar_disponibilidad(id: str, db: Session = Depends(get_db)):
    d = db.query(Disponibilidad).filter(Disponibilidad.id == id).first()
    if not d: raise HTTPException(404, "Franja no encontrada")
    db.delete(d); db.commit()
    return {"mensaje": "Franja eliminada"}

@router.get("/disponibilidad/check", tags=["Disponibilidad"])
def verificar_disponibilidad(docente_id: str, dia: str, hora_inicio: str, hora_fin: str,
                              db: Session = Depends(get_db)):
    franjas = db.query(Disponibilidad).filter(
        Disponibilidad.docente_id == docente_id,
        Disponibilidad.dia == dia
    ).all()
    for f in franjas:
        if f.hora_inicio <= hora_inicio and f.hora_fin >= hora_fin:
            return {"disponible": True}
    return {"disponible": False}

# ===================== ASIGNACIONES =====================
@router.get("/asignaciones", response_model=List[AsignacionOut], tags=["Asignaciones"])
def listar_asignaciones(periodo: Optional[str] = None, docente_id: Optional[str] = None,
                         dia: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Asignacion)
    if periodo: q = q.filter(Asignacion.periodo == periodo)
    if docente_id: q = q.filter(Asignacion.docente_id == docente_id)
    if dia: q = q.filter(Asignacion.dia == dia)
    return q.all()

@router.get("/asignaciones/{id}", response_model=AsignacionOut, tags=["Asignaciones"])
def obtener_asignacion(id: str, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter(Asignacion.id == id).first()
    if not a: raise HTTPException(404, "Asignación no encontrada")
    return a

@router.post("/asignaciones", response_model=AsignacionOut, status_code=201, tags=["Asignaciones"])
def crear_asignacion(data: AsignacionCreate, db: Session = Depends(get_db)):
    a = Asignacion(id=str(uuid.uuid4()), **data.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    detectar_conflictos(db, a)
    return a

@router.put("/asignaciones/{id}", response_model=AsignacionOut, tags=["Asignaciones"])
def actualizar_asignacion(id: str, data: AsignacionCreate, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter(Asignacion.id == id).first()
    if not a: raise HTTPException(404, "Asignación no encontrada")
    for k, v in data.model_dump().items(): setattr(a, k, v)
    db.commit(); db.refresh(a); return a

@router.delete("/asignaciones/{id}", tags=["Asignaciones"])
def eliminar_asignacion(id: str, db: Session = Depends(get_db)):
    a = db.query(Asignacion).filter(Asignacion.id == id).first()
    if not a: raise HTTPException(404, "Asignación no encontrada")
    db.delete(a); db.commit()
    return {"mensaje": "Asignación eliminada"}

@router.get("/asignaciones/docente/{id}/hoy", tags=["Asignaciones"])
def asignaciones_hoy(id: str, db: Session = Depends(get_db)):
    hoy = DIA_HOY[date.today().weekday()]
    asigs = db.query(Asignacion).filter(
        Asignacion.docente_id == id, Asignacion.dia == hoy
    ).all()
    return {"dia": hoy, "asignaciones": asigs}

# ===================== CONFLICTOS =====================
@router.get("/conflictos", response_model=List[ConflictoOut], tags=["Conflictos"])
def listar_conflictos(resuelto: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(Conflicto)
    if resuelto is not None: q = q.filter(Conflicto.resuelto == resuelto)
    return q.all()

@router.get("/conflictos/{id}", response_model=ConflictoOut, tags=["Conflictos"])
def obtener_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter(Conflicto.id == id).first()
    if not c: raise HTTPException(404, "Conflicto no encontrado")
    return c

@router.patch("/conflictos/{id}/resolver", response_model=ConflictoOut, tags=["Conflictos"])
def resolver_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter(Conflicto.id == id).first()
    if not c: raise HTTPException(404, "Conflicto no encontrado")
    c.resuelto = True; db.commit(); db.refresh(c); return c

@router.post("/conflictos/detectar", tags=["Conflictos"])
def detectar_todos(db: Session = Depends(get_db)):
    asignaciones = db.query(Asignacion).all()
    total = 0
    for a in asignaciones:
        conflictos = detectar_conflictos(db, a)
        total += len(conflictos)
    return {"conflictos_detectados": total}

@router.delete("/conflictos/{id}", tags=["Conflictos"])
def eliminar_conflicto(id: str, db: Session = Depends(get_db)):
    c = db.query(Conflicto).filter(Conflicto.id == id).first()
    if not c: raise HTTPException(404, "Conflicto no encontrado")
    db.delete(c); db.commit()
    return {"mensaje": "Conflicto eliminado"}

# ===================== SOLICITUDES DE CAMBIO =====================
@router.get("/solicitudes-cambio", response_model=List[SolicitudCambioOut], tags=["Solicitudes"])
def listar_solicitudes(estado: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(SolicitudCambio)
    if estado: q = q.filter(SolicitudCambio.estado == estado)
    return q.all()

@router.get("/solicitudes-cambio/{id}", response_model=SolicitudCambioOut, tags=["Solicitudes"])
def obtener_solicitud(id: str, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter(SolicitudCambio.id == id).first()
    if not s: raise HTTPException(404, "Solicitud no encontrada")
    return s

@router.post("/solicitudes-cambio", response_model=SolicitudCambioOut, status_code=201, tags=["Solicitudes"])
def crear_solicitud(data: SolicitudCambioCreate, db: Session = Depends(get_db)):
    s = SolicitudCambio(id=str(uuid.uuid4()), **data.model_dump())
    db.add(s); db.commit(); db.refresh(s); return s

@router.patch("/solicitudes-cambio/{id}/aprobar", response_model=SolicitudCambioOut, tags=["Solicitudes"])
def aprobar_solicitud(id: str, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter(SolicitudCambio.id == id).first()
    if not s: raise HTTPException(404, "Solicitud no encontrada")
    s.estado = "aprobada"; db.commit(); db.refresh(s); return s

@router.patch("/solicitudes-cambio/{id}/rechazar", response_model=SolicitudCambioOut, tags=["Solicitudes"])
def rechazar_solicitud(id: str, db: Session = Depends(get_db)):
    s = db.query(SolicitudCambio).filter(SolicitudCambio.id == id).first()
    if not s: raise HTTPException(404, "Solicitud no encontrada")
    s.estado = "rechazada"; db.commit(); db.refresh(s); return s

# ===================== REPORTES PDF =====================
from fastapi.responses import Response
from backend.reportes import (generar_horario_docente, generar_carga_academica,
                         generar_reporte_conflictos, generar_horario_programa)

@router.get("/reportes", tags=["Reportes"])
def listar_reportes():
    return {
        "endpoints_disponibles": [
            "POST /reportes/horario-docente?docente_id=&periodo=",
            "POST /reportes/horario-programa?programa_id=&periodo=",
            "POST /reportes/carga-academica?periodo=",
            "POST /reportes/conflictos",
        ]
    }

@router.post("/reportes/horario-docente", tags=["Reportes"])
def reporte_horario_docente(docente_id: str, periodo: str, db: Session = Depends(get_db)):
    try:
        pdf_bytes = generar_horario_docente(db, docente_id, periodo)
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=horario_docente_{periodo}.pdf"})
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")

@router.post("/reportes/horario-programa", tags=["Reportes"])
def reporte_horario_programa(programa_id: str, periodo: str, db: Session = Depends(get_db)):
    try:
        pdf_bytes = generar_horario_programa(db, programa_id, periodo)
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=horario_programa_{periodo}.pdf"})
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")

@router.post("/reportes/carga-academica", tags=["Reportes"])
def reporte_carga(periodo: str, db: Session = Depends(get_db)):
    try:
        pdf_bytes = generar_carga_academica(db, periodo)
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=carga_academica_{periodo}.pdf"})
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")

@router.post("/reportes/conflictos", tags=["Reportes"])
def reporte_conflictos(db: Session = Depends(get_db)):
    try:
        pdf_bytes = generar_reporte_conflictos(db)
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=reporte_conflictos.pdf"})
    except Exception as e:
        raise HTTPException(500, f"Error generando PDF: {e}")
