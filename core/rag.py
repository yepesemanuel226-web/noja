"""
core/rag.py — Cadena RAG con LangChain + ChromaDB + Groq.
Integra contexto dinámico desde la API local (conflictos, docentes, horarios).
Las rutas vienen absolutas desde config.py; este módulo NO hace os.chdir().
"""
import os
import sys
import re
import requests

# ── Asegurar que la raíz del proyecto esté en sys.path ───────────────────────
_CORE_DIR = os.path.abspath(os.path.dirname(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_CORE_DIR, ".."))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

# ── Imports de LangChain ──────────────────────────────────────────────────────
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
# Paquetes actualizados (reemplazan los deprecados de langchain_community)
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# ── Config (rutas YA son absolutas gracias al nuevo config.py) ────────────────
from config import GROQ_API_KEY, GROQ_MODEL_TEXT, PDF_PATH, DOCS_DIR, CHROMA_DIR

# Garantizar absolutas por si alguien usa config.py viejo
_HERE = _ROOT_DIR
PDF_PATH_ABS   = PDF_PATH   if os.path.isabs(PDF_PATH)   else os.path.join(_HERE, PDF_PATH)
DOCS_DIR_ABS   = DOCS_DIR   if os.path.isabs(DOCS_DIR)   else os.path.join(_HERE, DOCS_DIR)
CHROMA_DIR_ABS = CHROMA_DIR if os.path.isabs(CHROMA_DIR) else os.path.join(_HERE, CHROMA_DIR)

print(f"[RAG] ROOT      : {_HERE}")
print(f"[RAG] DOCS_DIR  : {DOCS_DIR_ABS}  — existe: {os.path.isdir(DOCS_DIR_ABS)}")
print(f"[RAG] CHROMA_DIR: {CHROMA_DIR_ABS} — existe: {os.path.isdir(CHROMA_DIR_ABS)}")
print(f"[RAG] PDF_PATH  : {PDF_PATH_ABS}  — existe: {os.path.isfile(PDF_PATH_ABS)}")

# ── URL base de la API local ──────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/v1"

# ── Historial por usuario ─────────────────────────────────────────────────────
_historiales: dict[str, list] = {}

def obtener_historial(user_id: str) -> list:
    if user_id not in _historiales:
        _historiales[user_id] = []
    return _historiales[user_id]

def limpiar_historial(user_id: str):
    _historiales[user_id] = []

# ══════════════════════════════════════════════════════
# CONTEXTO DINÁMICO DESDE LA API
# Estas funciones consultan Supabase en tiempo real
# para enriquecer las respuestas del chatbot.
# ══════════════════════════════════════════════════════

def _api_get(path: str) -> list | dict | None:
    """Hace GET a la API local. Retorna None si falla (API apagada, etc.)."""
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=3)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def _detectar_intent(pregunta: str) -> set:
    """
    Detecta qué tipo de datos en tiempo real necesita la pregunta.
    Retorna un set con los intents detectados.
    """
    p = pregunta.lower()
    intents = set()

    # Conflictos
    if any(w in p for w in ["conflicto", "cruce", "solapamiento", "problema",
                              "choque", "doble asignación", "pendiente"]):
        intents.add("conflictos")

    # Docentes
    if any(w in p for w in ["docente", "profesor", "quien da", "quién da",
                              "quién dicta", "quien dicta", "planta docente",
                              "disponibilidad"]):
        intents.add("docentes")

    # Horarios / asignaciones
    if any(w in p for w in ["horario", "asignación", "asignacion", "clase",
                              "materia", "cuándo", "cuando", "día", "hora",
                              "lunes", "martes", "miércoles", "jueves", "viernes"]):
        intents.add("asignaciones")

    # Salones
    if any(w in p for w in ["salón", "salon", "aula", "laboratorio", "sala",
                              "disponible", "libre", "espacio"]):
        intents.add("salones")

    # Carga académica / sobrecarga
    if any(w in p for w in ["carga", "horas", "sobrecarga", "subcarga",
                              "cuántas horas", "cuantas horas", "máximo", "minimo"]):
        intents.add("carga")

    return intents


def obtener_contexto_dinamico(pregunta: str) -> str:
    """
    Según la pregunta, consulta los endpoints relevantes de la API
    y devuelve un bloque de texto para inyectar al prompt del LLM.
    """
    intents = _detectar_intent(pregunta)
    if not intents:
        return ""

    bloques = []

    # ── Conflictos activos ────────────────────────────────────────────────────
    if "conflictos" in intents:
        data = _api_get("/conflictos?resuelto=false")
        if data is None:
            bloques.append("⚠️ [Sistema: API no disponible para consultar conflictos en tiempo real]")
        elif not data:
            bloques.append("✅ [Sistema: No hay conflictos activos registrados en este momento]")
        else:
            lines = ["📋 Conflictos activos en el sistema:"]
            for c in data:
                estado = "✅ Resuelto" if c.get("resuelto") else "🔴 Pendiente"
                lines.append(f"  • [{c.get('tipo','?')}] {c.get('descripcion','?')} — {estado}")
            bloques.append("\n".join(lines))

    # ── Lista de docentes ─────────────────────────────────────────────────────
    if "docentes" in intents:
        data = _api_get("/docentes")
        if data:
            lines = ["👨‍🏫 Docentes activos en el sistema:"]
            for d in data:
                lines.append(
                    f"  • {d.get('nombre','?')} | Email: {d.get('email','?')} "
                    f"| Horas: {d.get('horas_min',0)}–{d.get('horas_max',0)}h"
                )
            bloques.append("\n".join(lines))

    # ── Asignaciones del período actual ──────────────────────────────────────
    if "asignaciones" in intents:
        data = _api_get("/asignaciones?periodo=2026-1")
        if data:
            lines = ["📅 Asignaciones período 2026-1:"]
            for a in data[:20]:  # Limitar a 20 para no saturar el contexto
                lines.append(
                    f"  • {a.get('dia','?')} {a.get('hora_inicio','?')}–{a.get('hora_fin','?')}"
                    f" | Docente: {a.get('docente_id','?')[:8]}..."
                    f" | Materia: {a.get('materia_id','?')[:8]}..."
                    f" | Salón: {a.get('salon_id','?')[:8]}..."
                )
            if len(data) > 20:
                lines.append(f"  ... y {len(data)-20} asignaciones más.")
            bloques.append("\n".join(lines))

    # ── Salones disponibles ───────────────────────────────────────────────────
    if "salones" in intents:
        data = _api_get("/salones")
        if data:
            lines = ["🏫 Salones registrados:"]
            for s in data:
                lines.append(
                    f"  • {s.get('nombre','?')} ({s.get('codigo','?')}) "
                    f"| Capacidad: {s.get('capacidad',0)} | Tipo: {s.get('tipo','?')}"
                )
            bloques.append("\n".join(lines))

    # ── Carga académica ───────────────────────────────────────────────────────
    if "carga" in intents:
        docentes = _api_get("/docentes")
        if docentes:
            lines = ["⚖️ Carga académica período 2026-1:"]
            for d in docentes:
                carga = _api_get(f"/docentes/{d['id']}/carga?periodo=2026-1")
                if carga and isinstance(carga, dict):
                    emoji = "🔴" if carga.get("estado") == "sobrecarga" else \
                            "🟡" if carga.get("estado") == "subcarga" else "🟢"
                    lines.append(
                        f"  {emoji} {d.get('nombre','?')}: "
                        f"{carga.get('horas_asignadas',0)}h asignadas "
                        f"(min {d.get('horas_min',0)}h / max {d.get('horas_max',0)}h) "
                        f"— {carga.get('estado','?').upper()}"
                    )
            bloques.append("\n".join(lines))

    return "\n\n".join(bloques) if bloques else ""


# ── Carga de documentos ───────────────────────────────────────────────────────

def _cargar_desde_carpeta() -> list:
    if not os.path.isdir(DOCS_DIR_ABS):
        print(f"[RAG] Docs_Dir no existe: {DOCS_DIR_ABS}")
        return []
    pdfs = [f for f in os.listdir(DOCS_DIR_ABS) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"[RAG] Docs_Dir vacío (sin PDFs): {DOCS_DIR_ABS}")
        return []
    print(f"[RAG] Cargando {len(pdfs)} PDF(s) desde Docs_Dir: {pdfs}")
    loader = DirectoryLoader(
        DOCS_DIR_ABS,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=True,
    )
    docs = loader.load()
    print(f"[RAG] {len(docs)} páginas cargadas desde Docs_Dir.")
    return docs

def _cargar_pdf_legacy() -> list:
    if not os.path.isfile(PDF_PATH_ABS):
        print(f"[RAG] PDF fallback no existe: {PDF_PATH_ABS}")
        return []
    print(f"[RAG] Cargando PDF fallback: {PDF_PATH_ABS}")
    loader = PyPDFLoader(PDF_PATH_ABS)
    docs   = loader.load()
    print(f"[RAG] {len(docs)} páginas cargadas desde PDF fallback.")
    return docs

def cargar_documentos() -> list:
    # Carga AMBAS fuentes: PDFs de Docs_Dir/ Y el PDF externo (si existe)
    docs  = _cargar_desde_carpeta()
    extra = _cargar_pdf_legacy()
    if extra:
        print(f"[RAG] PDF externo añadido: {len(extra)} páginas de {PDF_PATH_ABS}")
        docs = docs + extra
    if not docs:
        raise FileNotFoundError(
            f"No se encontraron documentos.\n"
            f"  Docs_Dir : {DOCS_DIR_ABS}\n"
            f"  PDF      : {PDF_PATH_ABS}\n"
            "Agrega al menos un PDF a Docs_Dir/ o al directorio raíz."
        )
    print(f"[RAG] Total páginas combinadas: {len(docs)}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks   = splitter.split_documents(docs)
    print(f"[RAG] Total fragmentos para indexar: {len(chunks)}")
    return chunks

# ── Base vectorial ────────────────────────────────────────────────────────────

def _embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )

def crear_bd_vectorial(chunks) -> Chroma:
    os.makedirs(CHROMA_DIR_ABS, exist_ok=True)
    print(f"[RAG] Creando ChromaDB en: {CHROMA_DIR_ABS}")
    db = Chroma.from_documents(
        documents=chunks,
        embedding=_embeddings(),
        persist_directory=CHROMA_DIR_ABS,
    )
    print("[RAG] ChromaDB creada y persistida.")
    return db

def cargar_bd_existente() -> Chroma:
    print(f"[RAG] Cargando ChromaDB existente desde: {CHROMA_DIR_ABS}")
    return Chroma(
        persist_directory=CHROMA_DIR_ABS,
        embedding_function=_embeddings(),
    )

# ── Cadena RAG ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres un asistente académico especializado en la gestión de horarios \
y disponibilidad docente de la Universidad NOJA (Universidad Tecnológica del Caribe).

Tu base de conocimiento incluye:
- Reglamento docente institucional
- Estatutos de la universidad
- Normativas de horas mínimas y máximas de carga académica
- Políticas de asignación de materias, salones y grupos
- Horarios actuales de los docentes del período 2026-1

Responde siempre en español, de forma clara y precisa.
Cuando detectes un posible conflicto de horario o violación de normativa, \
indícalo explícitamente con ⚠️.
Si la información no está en los documentos ni en los datos del sistema, \
dilo claramente en lugar de inventar.

--- CONTEXTO DE DOCUMENTOS (PDF/ChromaDB) ---
{context}

--- DATOS EN TIEMPO REAL DEL SISTEMA ---
{contexto_bd}
"""

def _extraer_texto(respuesta) -> str:
    """Extrae texto plano del output del LLM de forma robusta."""
    if isinstance(respuesta, str):
        return respuesta
    if hasattr(respuesta, "content"):
        contenido = respuesta.content
        if isinstance(contenido, str):
            return contenido
        if isinstance(contenido, list):
            partes = []
            for bloque in contenido:
                if isinstance(bloque, str):
                    partes.append(bloque)
                elif isinstance(bloque, dict) and bloque.get("type") == "text":
                    partes.append(bloque.get("text", ""))
            return "\n".join(partes)
    if isinstance(respuesta, dict):
        for clave in ("output", "text", "answer", "result"):
            if clave in respuesta and isinstance(respuesta[clave], str):
                return respuesta[clave]
        return str(respuesta)
    texto = str(respuesta)
    print(f"[RAG] ⚠️ Tipo inesperado: {type(respuesta)} → str()")
    return texto


def crear_cadena_rag(db: Chroma):
    llm = ChatGroq(api_key=GROQ_API_KEY, model_name=GROQ_MODEL_TEXT, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="historial"),
        ("human", "{question}"),
    ])

    def formatear_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    retriever         = db.as_retriever(search_kwargs={"k": 4})
    extraer_question  = RunnableLambda(lambda x: x["question"])
    extraer_historial = RunnableLambda(lambda x: x["historial"])
    extraer_context   = extraer_question | retriever | formatear_docs
    extraer_ctx_bd    = RunnableLambda(lambda x: x.get("contexto_bd", ""))

    # RunnableLambda robusto reemplaza StrOutputParser que falla con langchain-groq
    cadena = (
        {
            "context":     extraer_context,
            "contexto_bd": extraer_ctx_bd,
            "question":    extraer_question,
            "historial":   extraer_historial,
        }
        | prompt
        | llm
        | RunnableLambda(_extraer_texto)
    )
    return cadena

# ── Inicialización ────────────────────────────────────────────────────────────

def inicializar_rag():
    """
    Si ya existe chroma_db/ la carga directamente.
    Si no existe la crea desde los PDFs en Docs_Dir/.
    """
    if os.path.isdir(CHROMA_DIR_ABS) and os.listdir(CHROMA_DIR_ABS):
        db = cargar_bd_existente()
    else:
        print("[RAG] ChromaDB no encontrada o vacía — creando desde documentos...")
        chunks = cargar_documentos()
        db     = crear_bd_vectorial(chunks)
    cadena = crear_cadena_rag(db)
    if not callable(getattr(cadena, "invoke", None)):
        raise RuntimeError("[RAG] La cadena creada no tiene método .invoke(). Verifica LangChain.")
    print("[RAG] ✅ Cadena RAG lista.")
    return cadena

def reiniciar_bd():
    """Elimina la ChromaDB existente y la recrea desde cero."""
    import shutil
    if os.path.isdir(CHROMA_DIR_ABS):
        shutil.rmtree(CHROMA_DIR_ABS)
        print("[RAG] ChromaDB eliminada.")
    chunks = cargar_documentos()
    db     = crear_bd_vectorial(chunks)
    return crear_cadena_rag(db)

# ── Consulta con historial ────────────────────────────────────────────────────

def consultar(cadena, pregunta: str, user_id: str = "default") -> str:
    """
    Invoca la cadena RAG con contexto dinámico de la API.
    Combina ChromaDB (documentos/PDFs) + Supabase (datos en tiempo real).
    """
    if not callable(getattr(cadena, "invoke", None)):
        raise TypeError(
            f"cadena no es un Runnable LangChain válido: {type(cadena)}"
        )

    historial   = obtener_historial(user_id)
    contexto_bd = obtener_contexto_dinamico(pregunta)

    if contexto_bd:
        print(f"[RAG] Contexto dinámico inyectado ({len(contexto_bd)} chars)")

    resultado = cadena.invoke({
        "question":    pregunta,
        "historial":   historial,
        "contexto_bd": contexto_bd,
    })

    # ── Extracción robusta del texto ──────────────────────────────────────────
    respuesta = _extraer_texto(resultado)
    print(f"[RAG] Respuesta obtenida ({len(respuesta)} chars): {respuesta[:80]}...")

    historial.append(HumanMessage(content=pregunta))
    historial.append(AIMessage(content=respuesta))
    if len(historial) > 20:
        _historiales[user_id] = historial[-20:]

    return respuesta