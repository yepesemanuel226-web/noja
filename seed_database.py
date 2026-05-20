"""
seed_database.py
================
Pobla la BD SQLite con datos académicos realistas.
Genera ~1200 asignaciones + todos los datos relacionados.

Ejecutar: python seed_database.py
"""
import os
import sys
import uuid
import sqlite3
import random
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

DB_PATH = os.path.join(ROOT_DIR, "horarios.db")

# ── Asegurar que las tablas existan ──────────────────────────────────────────
from backend.database import engine, Base
import backend.models
Base.metadata.create_all(bind=engine)
print("✅ Tablas verificadas/creadas")

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import (Docente, Programa, Materia, Salon, Grupo,
                              Disponibilidad, Asignacion, Conflicto, SolicitudCambio)

db: Session = SessionLocal()

def gen_id():
    return str(uuid.uuid4())

# ── Limpiar datos previos ────────────────────────────────────────────────────
print("🗑  Limpiando datos previos...")
db.query(SolicitudCambio).delete()
db.query(Conflicto).delete()
db.query(Asignacion).delete()
db.query(Disponibilidad).delete()
db.query(Grupo).delete()
db.query(Materia).delete()
db.query(Salon).delete()
db.query(Programa).delete()
db.query(Docente).delete()
db.commit()
print("✅ BD limpia")

# ════════════════════════════════════════════════════════════════
# 1. PROGRAMAS ACADÉMICOS
# ════════════════════════════════════════════════════════════════
print("\n📚 Insertando programas...")
programas_data = [
    ("Ingeniería en Tecnologías de la Información y Comunicación", "ITE"),
    ("Ingeniería en Sistemas Computacionales",                     "ISC"),
    ("Ingeniería Industrial",                                      "IIN"),
    ("Ingeniería Electrónica",                                     "IEL"),
    ("Ingeniería Mecatrónica",                                     "IMT"),
    ("Licenciatura en Administración",                             "LAD"),
    ("Ingeniería en Gestión Empresarial",                          "IGE"),
    ("Ingeniería Ambiental",                                       "IAM"),
]
programas = []
for nombre, codigo in programas_data:
    p = Programa(id=gen_id(), nombre=nombre, codigo=codigo, activo=True)
    db.add(p)
    programas.append(p)
db.commit()
print(f"  ✅ {len(programas)} programas")

# ════════════════════════════════════════════════════════════════
# 2. DOCENTES (30 docentes)
# ════════════════════════════════════════════════════════════════
print("\n👨‍🏫 Insertando docentes...")
docentes_data = [
    ("Dr. Carlos Ramírez Torres",       "c.ramirez@utcaribe.edu.co",    "3001234567"),
    ("Ing. Jorge Gutiérrez Soto",       "j.gutierrez@utcaribe.edu.co",  "3012345678"),
    ("Dra. María López Herrera",        "m.lopez@utcaribe.edu.co",      "3023456789"),
    ("MSc. Andrés Martínez Peña",       "a.martinez@utcaribe.edu.co",   "3034567890"),
    ("Ing. Laura Sánchez Díaz",         "l.sanchez@utcaribe.edu.co",    "3045678901"),
    ("Dr. Roberto Vargas Mora",         "r.vargas@utcaribe.edu.co",     "3056789012"),
    ("MSc. Patricia Gómez Ruiz",        "p.gomez@utcaribe.edu.co",      "3067890123"),
    ("Ing. Felipe Torres Castillo",     "f.torres@utcaribe.edu.co",     "3078901234"),
    ("Dra. Claudia Herrera Jiménez",    "c.herrera@utcaribe.edu.co",    "3089012345"),
    ("MSc. Diego Morales Vega",         "d.morales@utcaribe.edu.co",    "3090123456"),
    ("Ing. Sandra Ríos Mendoza",        "s.rios@utcaribe.edu.co",       "3101234567"),
    ("Dr. Hernán Castillo Pardo",       "h.castillo@utcaribe.edu.co",   "3112345678"),
    ("MSc. Valentina Cruz Ospina",      "v.cruz@utcaribe.edu.co",       "3123456789"),
    ("Ing. Mauricio Peña Salcedo",      "m.pena@utcaribe.edu.co",       "3134567890"),
    ("Dra. Natalia Rojas Fuentes",      "n.rojas@utcaribe.edu.co",      "3145678901"),
    ("MSc. Camilo Suárez Blanco",       "c.suarez@utcaribe.edu.co",     "3156789012"),
    ("Ing. Alejandra Medina Cano",      "a.medina@utcaribe.edu.co",     "3167890123"),
    ("Dr. Gustavo Lozano Arango",       "g.lozano@utcaribe.edu.co",     "3178901234"),
    ("MSc. Isabel Reyes Montoya",       "i.reyes@utcaribe.edu.co",      "3189012345"),
    ("Ing. Sebastián Ortiz Palacio",    "s.ortiz@utcaribe.edu.co",      "3190123456"),
    ("Dra. Marcela Agudelo Ríos",       "m.agudelo@utcaribe.edu.co",    "3201234567"),
    ("MSc. Julián Cardona Vélez",       "j.cardona@utcaribe.edu.co",    "3212345678"),
    ("Ing. Paola Giraldo Zapata",       "p.giraldo@utcaribe.edu.co",    "3223456789"),
    ("Dr. Ernesto Muñoz Castaño",       "e.munoz@utcaribe.edu.co",      "3234567890"),
    ("MSc. Liliana Ospina Betancur",    "l.ospina@utcaribe.edu.co",     "3245678901"),
    ("Ing. Ricardo Bermúdez Hoyos",     "r.bermudez@utcaribe.edu.co",   "3256789012"),
    ("Dra. Adriana Cárdenas Mejía",     "a.cardenas@utcaribe.edu.co",   "3267890123"),
    ("MSc. Nicolás Arboleda Patiño",    "n.arboleda@utcaribe.edu.co",   "3278901234"),
    ("Ing. Gloria Henao Londoño",       "g.henao@utcaribe.edu.co",      "3289012345"),
    ("Dr. Álvaro Quintero Salazar",     "a.quintero@utcaribe.edu.co",   "3290123456"),
]
docentes = []
for nombre, email, tel in docentes_data:
    d = Docente(id=gen_id(), nombre=nombre, email=email, telefono=tel, activo=True)
    db.add(d)
    docentes.append(d)
db.commit()
print(f"  ✅ {len(docentes)} docentes")

# ════════════════════════════════════════════════════════════════
# 3. SALONES (20 salones)
# ════════════════════════════════════════════════════════════════
print("\n🏫 Insertando salones...")
salones_data = [
    ("Aula 101",        "35",  "Edificio A"),
    ("Aula 102",        "35",  "Edificio A"),
    ("Aula 103",        "40",  "Edificio A"),
    ("Aula 201",        "35",  "Edificio A"),
    ("Aula 202",        "35",  "Edificio A"),
    ("Aula 203",        "40",  "Edificio A"),
    ("Aula 301",        "30",  "Edificio B"),
    ("Aula 302",        "30",  "Edificio B"),
    ("Aula 303",        "30",  "Edificio B"),
    ("Lab. Cómputo 1",  "25",  "Edificio B"),
    ("Lab. Cómputo 2",  "25",  "Edificio B"),
    ("Lab. Cómputo 3",  "25",  "Edificio C"),
    ("Lab. Electrónica","20",  "Edificio C"),
    ("Lab. Mecatrónica","20",  "Edificio C"),
    ("Lab. Ambiental",  "20",  "Edificio C"),
    ("Auditorio A",     "80",  "Edificio D"),
    ("Auditorio B",     "60",  "Edificio D"),
    ("Sala de Conf. 1", "20",  "Edificio D"),
    ("Sala de Conf. 2", "20",  "Edificio D"),
    ("Aula Virtual 1",  "30",  "Edificio E"),
]
salones = []
for nombre, cap, edif in salones_data:
    s = Salon(id=gen_id(), nombre=nombre, capacidad=cap, edificio=edif, activo=True)
    db.add(s)
    salones.append(s)
db.commit()
print(f"  ✅ {len(salones)} salones")

# ════════════════════════════════════════════════════════════════
# 4. MATERIAS por programa
# ════════════════════════════════════════════════════════════════
print("\n📖 Insertando materias...")
materias_por_programa = {
    "ITE": [
        ("Fundamentos de Programación",       "ITE-101", "4"),
        ("Bases de Datos I",                  "ITE-102", "4"),
        ("Redes de Computadores",             "ITE-103", "4"),
        ("Sistemas Operativos",               "ITE-104", "4"),
        ("Ingeniería de Software",            "ITE-201", "4"),
        ("Bases de Datos II",                 "ITE-202", "4"),
        ("Seguridad Informática",             "ITE-203", "4"),
        ("Desarrollo Web",                    "ITE-204", "4"),
        ("Inteligencia Artificial",           "ITE-301", "4"),
        ("Gestión de Proyectos TI",           "ITE-302", "4"),
        ("Arquitectura de Software",          "ITE-303", "4"),
        ("Computación en la Nube",            "ITE-304", "4"),
    ],
    "ISC": [
        ("Programación Orientada a Objetos",  "ISC-101", "4"),
        ("Estructuras de Datos",              "ISC-102", "4"),
        ("Algoritmos y Complejidad",          "ISC-103", "4"),
        ("Compiladores",                      "ISC-201", "4"),
        ("Sistemas Distribuidos",             "ISC-202", "4"),
        ("Inteligencia Artificial",           "ISC-203", "4"),
        ("Minería de Datos",                  "ISC-204", "4"),
        ("Desarrollo Móvil",                  "ISC-301", "4"),
        ("Visión por Computadora",            "ISC-302", "4"),
        ("Aprendizaje Automático",            "ISC-303", "4"),
    ],
    "IIN": [
        ("Investigación de Operaciones",      "IIN-101", "4"),
        ("Control de Calidad",                "IIN-102", "4"),
        ("Gestión de Producción",             "IIN-103", "4"),
        ("Logística y Cadena de Suministro",  "IIN-201", "4"),
        ("Ergonomía Industrial",              "IIN-202", "4"),
        ("Simulación de Sistemas",            "IIN-203", "4"),
        ("Gestión Ambiental Industrial",      "IIN-301", "4"),
        ("Automatización Industrial",         "IIN-302", "4"),
    ],
    "IEL": [
        ("Circuitos Eléctricos I",            "IEL-101", "4"),
        ("Circuitos Eléctricos II",           "IEL-102", "4"),
        ("Electrónica Analógica",             "IEL-201", "4"),
        ("Electrónica Digital",               "IEL-202", "4"),
        ("Sistemas de Control",               "IEL-203", "4"),
        ("Comunicaciones Digitales",          "IEL-301", "4"),
        ("Procesamiento de Señales",          "IEL-302", "4"),
        ("Instrumentación Electrónica",       "IEL-303", "4"),
    ],
    "IMT": [
        ("Mecánica Clásica",                  "IMT-101", "4"),
        ("Robótica Industrial",               "IMT-102", "4"),
        ("Sistemas Embebidos",                "IMT-201", "4"),
        ("Control Automático",                "IMT-202", "4"),
        ("Visión Artificial",                 "IMT-203", "4"),
        ("Manufactura Avanzada",              "IMT-301", "4"),
    ],
    "LAD": [
        ("Fundamentos de Administración",     "LAD-101", "4"),
        ("Contabilidad General",              "LAD-102", "4"),
        ("Economía Empresarial",              "LAD-103", "4"),
        ("Gestión del Talento Humano",        "LAD-201", "4"),
        ("Marketing Estratégico",             "LAD-202", "4"),
        ("Finanzas Corporativas",             "LAD-203", "4"),
        ("Derecho Empresarial",               "LAD-301", "4"),
        ("Emprendimiento e Innovación",       "LAD-302", "4"),
    ],
    "IGE": [
        ("Gestión Empresarial I",             "IGE-101", "4"),
        ("Gestión Empresarial II",            "IGE-102", "4"),
        ("Planeación Estratégica",            "IGE-201", "4"),
        ("Gestión de Proyectos",              "IGE-202", "4"),
        ("Innovación y Tecnología",           "IGE-203", "4"),
        ("Comercio Internacional",            "IGE-301", "4"),
    ],
    "IAM": [
        ("Ecología General",                  "IAM-101", "4"),
        ("Química Ambiental",                 "IAM-102", "4"),
        ("Gestión de Residuos",               "IAM-201", "4"),
        ("Evaluación de Impacto Ambiental",   "IAM-202", "4"),
        ("Legislación Ambiental",             "IAM-203", "4"),
        ("Sistemas de Gestión Ambiental",     "IAM-301", "4"),
    ],
}

prog_map = {p.codigo: p for p in programas}
materias = []
for codigo_prog, lista in materias_por_programa.items():
    prog = prog_map.get(codigo_prog)
    for nombre, codigo, horas in lista:
        m = Materia(id=gen_id(), nombre=nombre, codigo=codigo,
                    horas_semanales=horas, programa_id=prog.id if prog else None, activo=True)
        db.add(m)
        materias.append(m)
db.commit()
print(f"  ✅ {len(materias)} materias")

# ════════════════════════════════════════════════════════════════
# 5. GRUPOS (semestres por programa, 2 periodos)
# ════════════════════════════════════════════════════════════════
print("\n👥 Insertando grupos...")
periodos = ["2025-2", "2026-1"]
semestres = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B", "5A", "6A", "7A", "8A"]
grupos = []
for prog in programas:
    for periodo in periodos:
        for sem in semestres[:6]:   # 6 grupos por programa por periodo
            nombre = f"{prog.codigo}-{sem}-{periodo}"
            g = Grupo(id=gen_id(), nombre=nombre, periodo=periodo,
                      programa_id=prog.id, activo=True)
            db.add(g)
            grupos.append(g)
db.commit()
print(f"  ✅ {len(grupos)} grupos")

# ════════════════════════════════════════════════════════════════
# 6. DISPONIBILIDADES (cada docente tiene 4-5 franjas/semana)
# ════════════════════════════════════════════════════════════════
print("\n📅 Insertando disponibilidades...")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
FRANJAS_MANANA  = [("06:00","08:00"),("08:00","10:00"),("10:00","12:00")]
FRANJAS_TARDE   = [("12:00","14:00"),("14:00","16:00"),("16:00","18:00")]
FRANJAS_NOCHE   = [("18:00","20:00"),("20:00","22:00")]

random.seed(42)
disponibilidades = []
for i, doc in enumerate(docentes):
    # Cada docente tiene disponibilidad en 4-5 días
    dias_disp = random.sample(DIAS[:5], k=random.randint(4, 5))
    for dia in dias_disp:
        # Turno preferido según índice del docente
        if i % 3 == 0:
            franjas = FRANJAS_MANANA
        elif i % 3 == 1:
            franjas = FRANJAS_TARDE
        else:
            franjas = FRANJAS_MANANA + FRANJAS_TARDE[:1]
        for hi, hf in franjas:
            d = Disponibilidad(id=gen_id(), docente_id=doc.id,
                               dia=dia, hora_inicio=hi, hora_fin=hf)
            db.add(d)
            disponibilidades.append(d)
db.commit()
print(f"  ✅ {len(disponibilidades)} franjas de disponibilidad")

# ════════════════════════════════════════════════════════════════
# 7. ASIGNACIONES (~1200 registros, sin conflictos la mayoría)
# ════════════════════════════════════════════════════════════════
print("\n📋 Generando asignaciones (~1200)...")

def hora_a_min(h):
    p = h.split(":")
    return int(p[0]) * 60 + int(p[1])

def hay_solapamiento(hi1, hf1, hi2, hf2):
    return hora_a_min(hi1) < hora_a_min(hf2) and hora_a_min(hi2) < hora_a_min(hf1)

BLOQUES_HORARIOS = [
    ("06:00", "08:00"),
    ("08:00", "10:00"),
    ("10:00", "12:00"),
    ("12:00", "14:00"),
    ("14:00", "16:00"),
    ("16:00", "18:00"),
    ("18:00", "20:00"),
    ("20:00", "22:00"),
]

asignaciones = []
# Rastrear ocupación para evitar conflictos masivos
# clave: (docente_id, dia, hi, hf, periodo) y (salon_id, dia, hi, hf, periodo)
ocupado_docente = set()
ocupado_salon   = set()
ocupado_grupo   = set()

# Agrupar materias por programa
materias_por_prog_id = {}
for m in materias:
    pid = m.programa_id or "sin_prog"
    materias_por_prog_id.setdefault(pid, []).append(m)

# Agrupar grupos por (programa_id, periodo)
grupos_por_prog_periodo = {}
for g in grupos:
    key = (g.programa_id, g.periodo)
    grupos_por_prog_periodo.setdefault(key, []).append(g)

random.seed(99)
intentos_totales = 0
asigs_creadas    = 0
TARGET           = 1200

# Iterar sobre programas y periodos para distribuir bien
for prog in programas:
    for periodo in periodos:
        grps = grupos_por_prog_periodo.get((prog.id, periodo), [])
        mats = materias_por_prog_id.get(prog.id, [])
        if not grps or not mats:
            continue

        for grupo in grps:
            # Cada grupo recibe entre 5 y 8 materias por periodo
            n_materias = random.randint(5, 8)
            mats_grupo = random.sample(mats, min(n_materias, len(mats)))

            for materia in mats_grupo:
                if asigs_creadas >= TARGET:
                    break
                # Intentar asignar en un slot libre
                dias_shuffle = random.sample(DIAS[:5], len(DIAS[:5]))
                asignado = False
                for dia in dias_shuffle:
                    bloques_shuffle = random.sample(BLOQUES_HORARIOS, len(BLOQUES_HORARIOS))
                    for hi, hf in bloques_shuffle:
                        # Elegir docente disponible en ese slot
                        docs_shuffle = random.sample(docentes, len(docentes))
                        for doc in docs_shuffle:
                            k_doc   = (doc.id,    dia, hi, hf, periodo)
                            # Buscar salon libre
                            salones_shuffle = random.sample(salones, len(salones))
                            for salon in salones_shuffle:
                                k_sal   = (salon.id,  dia, hi, hf, periodo)
                                k_grp   = (grupo.id,  dia, hi, hf, periodo)
                                if k_doc in ocupado_docente:
                                    continue
                                if k_sal in ocupado_salon:
                                    continue
                                if k_grp in ocupado_grupo:
                                    continue
                                # Slot libre — crear asignación
                                a = Asignacion(
                                    id=gen_id(),
                                    docente_id=doc.id,
                                    grupo_id=grupo.id,
                                    salon_id=salon.id,
                                    materia_id=materia.id,
                                    dia=dia,
                                    hora_inicio=hi,
                                    hora_fin=hf,
                                    periodo=periodo,
                                )
                                db.add(a)
                                ocupado_docente.add(k_doc)
                                ocupado_salon.add(k_sal)
                                ocupado_grupo.add(k_grp)
                                asignaciones.append(a)
                                asigs_creadas += 1
                                asignado = True
                                break
                            if asignado:
                                break
                        if asignado:
                            break
                    if asignado:
                        break

            if asigs_creadas >= TARGET:
                break
        if asigs_creadas >= TARGET:
            break
    if asigs_creadas >= TARGET:
        break

db.commit()
print(f"  ✅ {asigs_creadas} asignaciones creadas")

# ════════════════════════════════════════════════════════════════
# 8. CONFLICTOS INTENCIONALES (para que el sistema tenga datos)
# ════════════════════════════════════════════════════════════════
print("\n⚠️  Generando conflictos intencionales...")
conflictos_creados = 0

# Tomar 15 asignaciones del periodo 2026-1 y crear conflictos reales
asigs_2026 = [a for a in asignaciones if a.periodo == "2026-1"][:15]
for a in asigs_2026:
    tipo = random.choice(["DOCENTE_DUPLICADO", "SALON_DUPLICADO", "GRUPO_DUPLICADO"])
    if tipo == "DOCENTE_DUPLICADO":
        desc = (f"Docente asignado dos veces el {a.dia} "
                f"entre {a.hora_inicio}-{a.hora_fin} en periodo {a.periodo}")
    elif tipo == "SALON_DUPLICADO":
        desc = (f"Salón ocupado doble el {a.dia} "
                f"entre {a.hora_inicio}-{a.hora_fin} en periodo {a.periodo}")
    else:
        desc = (f"Grupo con dos clases simultáneas el {a.dia} "
                f"entre {a.hora_inicio}-{a.hora_fin} en periodo {a.periodo}")

    resuelto = random.choice([True, True, False])  # 2/3 resueltos
    c = Conflicto(id=gen_id(), tipo=tipo, descripcion=desc,
                  asignacion_id=a.id, resuelto=resuelto)
    db.add(c)
    conflictos_creados += 1

db.commit()
print(f"  ✅ {conflictos_creados} conflictos registrados")

# ════════════════════════════════════════════════════════════════
# 9. SOLICITUDES DE CAMBIO
# ════════════════════════════════════════════════════════════════
print("\n📝 Generando solicitudes de cambio...")
motivos = [
    "Conflicto con otra asignación en el mismo horario",
    "El docente tiene cita médica ese día",
    "El salón no tiene el equipamiento necesario",
    "Solicitud del estudiante por traslape con otra materia",
    "El docente solicita cambio por viaje académico",
    "Mantenimiento programado del laboratorio",
    "Actividad institucional que ocupa el espacio",
    "El grupo solicita cambio de horario por transporte",
]
estados = ["pendiente", "aprobada", "rechazada"]
solicitudes_creadas = 0
asigs_sample = random.sample(asignaciones, min(25, len(asignaciones)))
for a in asigs_sample:
    nuevo_dia = random.choice([d for d in DIAS[:5] if d != a.dia])
    nuevo_salon = random.choice(salones)
    s = SolicitudCambio(
        id=gen_id(),
        asignacion_id=a.id,
        docente_id=a.docente_id,
        motivo=random.choice(motivos),
        nuevo_dia=nuevo_dia,
        nueva_hora_inicio=a.hora_inicio,
        nueva_hora_fin=a.hora_fin,
        nuevo_salon_id=nuevo_salon.id,
        estado=random.choice(estados),
    )
    db.add(s)
    solicitudes_creadas += 1

db.commit()
print(f"  ✅ {solicitudes_creadas} solicitudes de cambio")

# ════════════════════════════════════════════════════════════════
# 10. RESUMEN FINAL
# ════════════════════════════════════════════════════════════════
db.close()

print("\n" + "="*55)
print("  ✅ SEED COMPLETADO")
print("="*55)
print(f"  Programas       : {len(programas)}")
print(f"  Docentes        : {len(docentes)}")
print(f"  Salones         : {len(salones)}")
print(f"  Materias        : {len(materias)}")
print(f"  Grupos          : {len(grupos)}")
print(f"  Disponibilidades: {len(disponibilidades)}")
print(f"  Asignaciones    : {asigs_creadas}")
print(f"  Conflictos      : {conflictos_creados}")
print(f"  Solicitudes     : {solicitudes_creadas}")
print("="*55)
print("\n🔄 Ahora ejecuta: python generar_pdfs.py")
print("   para regenerar los PDFs que alimentan el RAG.\n")
