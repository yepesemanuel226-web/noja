from sqlalchemy.orm import Session
from backend.models import Asignacion, Conflicto
import uuid

def hora_a_minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)

def hay_solapamiento(ini1, fin1, ini2, fin2) -> bool:
    return hora_a_minutos(ini1) < hora_a_minutos(fin2) and hora_a_minutos(ini2) < hora_a_minutos(fin1)

def detectar_conflictos(db: Session, nueva: Asignacion) -> list:
    conflictos = []
    asignaciones = db.query(Asignacion).filter(
        Asignacion.dia == nueva.dia,
        Asignacion.periodo == nueva.periodo,
        Asignacion.id != nueva.id
    ).all()
    for a in asignaciones:
        if hay_solapamiento(nueva.hora_inicio, nueva.hora_fin, a.hora_inicio, a.hora_fin):
            if a.docente_id == nueva.docente_id:
                c = Conflicto(id=str(uuid.uuid4()), tipo="DOCENTE_DUPLICADO",
                    descripcion=f"Docente tiene dos clases el {nueva.dia} entre {nueva.hora_inicio}-{nueva.hora_fin}",
                    asignacion_id=nueva.id, resuelto=False)
                db.add(c); conflictos.append(c)
            if a.salon_id == nueva.salon_id:
                c = Conflicto(id=str(uuid.uuid4()), tipo="SALON_DUPLICADO",
                    descripcion=f"Salón ocupado el {nueva.dia} entre {nueva.hora_inicio}-{nueva.hora_fin}",
                    asignacion_id=nueva.id, resuelto=False)
                db.add(c); conflictos.append(c)
            if a.grupo_id == nueva.grupo_id:
                c = Conflicto(id=str(uuid.uuid4()), tipo="GRUPO_DUPLICADO",
                    descripcion=f"Grupo tiene dos clases el {nueva.dia} entre {nueva.hora_inicio}-{nueva.hora_fin}",
                    asignacion_id=nueva.id, resuelto=False)
                db.add(c); conflictos.append(c)
    if conflictos:
        db.commit()
    return conflictos
