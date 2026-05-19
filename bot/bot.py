import logging
import os
import sys
import re
from datetime import datetime

# ── Path para encontrar módulos en la raíz y en core/ ─────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import core.rag as rag_module
from core import roboflow_api                          # ← import movido aquí arriba

from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "8725214258:AAFXK3a2HrlurqmdJYk4nIhhcU5BkMC8fg4"

# Ruta absoluta de fotos (funciona sin importar desde dónde se corra)
FOTOS_DIR = os.path.join(ROOT_DIR, "assets", "fotos")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

cadena_rag = None

# ============================================
# Normalización de texto
# ============================================

CORRECCIONES = {
    "manana":        "mañana",
    "maniana":       "mañana",
    "horario hoy":   "horario hoy",
    "profe":         "profesor",
    "profes":        "profesores",
    "materia":       "asignatura",
    "salon":         "salón",
    "conflicto":     "conflicto",
    "horaro":        "horario",
    "horarios":      "horarios",
    "disponibiliad": "disponibilidad",
    "docnete":       "docente",
    "docnetes":      "docentes",
}

DIAS_ES = {
    "lun": "lunes", "mar": "martes", "mie": "miércoles",
    "mié": "miércoles", "jue": "jueves", "vie": "viernes",
    "sab": "sábado", "dom": "domingo",
}

def normalizar(texto: str) -> str:
    t = texto.lower().strip()
    for abr, dia in DIAS_ES.items():
        t = re.sub(rf"\b{abr}\b", dia, t)
    for error, correcto in CORRECCIONES.items():
        t = re.sub(rf"\b{error}\b", correcto, t)
    return t

def dia_semana_hoy() -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return dias[datetime.now().weekday()]

def fecha_hoy() -> str:
    return datetime.now().strftime("%d/%m/%Y")

# ============================================
# Detección de intención
# ============================================

def detectar_intencion(texto: str) -> str:
    t = normalizar(texto)

    if any(p in t for p in ["horario hoy", "clases hoy", "que tengo hoy",
                              "clase hoy", "hoy tengo", "horario de hoy"]):
        return "horario_hoy"
    if any(p in t for p in ["horario", "clase", "asignatura", "materia",
                              "cuando", "qué hora", "que hora"]):
        return "horario"
    if any(p in t for p in ["disponible", "disponibilidad", "libre",
                              "puede", "puedo", "tiempo libre"]):
        return "disponibilidad"
    if any(p in t for p in ["conflicto", "cruce", "choque", "problema",
                              "solapan", "mismo horario", "doble"]):
        return "conflicto"
    if any(p in t for p in ["cambio", "solicito", "solicitar", "mover",
                              "cambiar", "modificar", "reasignar"]):
        return "solicitud"
    if any(p in t for p in ["reglamento", "norma", "politica", "política",
                              "horas maximas", "horas mínimas", "estatuto",
                              "permitido", "permitida"]):
        return "normativa"
    return "general"

def construir_pregunta_enriquecida(texto: str, intencion: str) -> str:
    t_norm = normalizar(texto)
    hoy    = dia_semana_hoy()
    fecha  = fecha_hoy()

    if intencion == "horario_hoy":
        return (
            f"Hoy es {hoy} {fecha}. "
            f"¿Qué clases hay programadas para el día {hoy}? "
            "Lista materias, docentes, aulas y horarios del día de hoy."
        )
    if intencion == "conflicto":
        return (
            f"El usuario pregunta: '{t_norm}'. "
            "Identifica todos los conflictos de horario: cruces de clases, "
            "docentes con doble asignación o aulas ocupadas al mismo tiempo. "
            "Indica con ⚠️ cada conflicto encontrado."
        )
    if intencion == "normativa":
        return (
            f"El usuario pregunta sobre normativa: '{t_norm}'. "
            "Consulta el reglamento docente y responde citando la norma aplicable."
        )
    return t_norm

# ============================================
# RAG
# ============================================

async def obtener_rag():
    global cadena_rag
    if cadena_rag is None:
        cadena_rag = rag_module.inicializar_rag()
    return cadena_rag

async def consultar_pdf(pregunta: str, user_id: str) -> str:
    try:
        rag = await obtener_rag()
        return rag_module.consultar(rag, pregunta, user_id=user_id)
    except Exception as e:
        return f"No pude consultar el documento: {str(e)}"

def get_uid(update: Update) -> str:
    return str(update.effective_user.id)

# ============================================
# Alertas (llamables desde la app de escritorio)
# ============================================

async def enviar_alerta_conflicto(chat_id: str, descripcion: str):
    """
    Llamar desde la app de escritorio:
        import asyncio
        from bot.bot import enviar_alerta_conflicto
        asyncio.run(enviar_alerta_conflicto(chat_id, "Conflicto: ..."))
    """
    bot = Bot(token=TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=f"⚠️ ALERTA DE CONFLICTO\n\n{descripcion}\n\nRevisa tu horario en la app.",
    )

async def enviar_alerta_cambio(chat_id: str, descripcion: str):
    """
    Llamar desde la app de escritorio:
        import asyncio
        from bot.bot import enviar_alerta_cambio
        asyncio.run(enviar_alerta_cambio(chat_id, "Cambio: ..."))
    """
    bot = Bot(token=TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=f"📋 CAMBIO EN TU ASIGNACIÓN\n\n{descripcion}\n\nConsulta los detalles en la app.",
    )

# ============================================
# Comandos Telegram
# ============================================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name or "Docente"
    await update.message.reply_text(
        f"Hola {nombre}! Soy el asistente de Gestión de Horarios.\n\n"
        "Puedes hablarme de forma natural, por ejemplo:\n"
        "  • 'qué clases tengo hoy'\n"
        "  • 'hay conflictos en el horario'\n"
        "  • 'cuál es la disponibilidad del profesor García'\n"
        "  • 'cuántas horas máximo puede tener un docente'\n\n"
        "También puedes enviarme una foto de un horario físico.\n\n"
        "Comandos rápidos:\n"
        "/horario  /disponibilidad  /conflictos  /limpiar  /ayuda"
    )

async def horario(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = get_uid(update)
    hoy = dia_semana_hoy()
    if ctx.args:
        arg = " ".join(ctx.args).lower()
        if arg in ("hoy", "today"):
            pregunta = (
                f"Hoy es {hoy} {fecha_hoy()}. "
                f"¿Qué clases hay programadas para el día {hoy}? "
                "Lista materias, docentes, aulas y horarios."
            )
        else:
            pregunta = f"Muestra el horario de {' '.join(ctx.args)}"
    else:
        pregunta = (
            "Lista todos los horarios de clases del documento. "
            "Incluye materias, dias, horas y aulas."
        )
    await update.message.reply_text("🔍 Consultando horarios...")
    respuesta = await consultar_pdf(pregunta, uid)
    await update.message.reply_text(respuesta, parse_mode=None)

async def disponibilidad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = get_uid(update)
    if ctx.args:
        pregunta = f"¿Cuál es la disponibilidad del docente {' '.join(ctx.args)}?"
    else:
        pregunta = (
            "Lista la disponibilidad de todos los docentes. "
            "Incluye días y horarios disponibles."
        )
    await update.message.reply_text("🔍 Consultando disponibilidad...")
    respuesta = await consultar_pdf(pregunta, uid)
    await update.message.reply_text(respuesta, parse_mode=None)

async def conflictos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = get_uid(update)
    pregunta = (
        "Identifica todos los conflictos de horario: docentes con dos clases "
        "al mismo tiempo, aulas ocupadas doble, o docentes que superan las horas "
        "máximas. Marca cada conflicto con ⚠️. Si no hay conflictos, indícalo."
    )
    await update.message.reply_text("🔍 Analizando conflictos...")
    respuesta = await consultar_pdf(pregunta, uid)
    await update.message.reply_text(respuesta, parse_mode=None)

async def limpiar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = get_uid(update)
    rag_module.limpiar_historial(uid)
    await update.message.reply_text("✅ Historial borrado. Empezamos de nuevo.")

async def reiniciar_bd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global cadena_rag
    await update.message.reply_text("⚙️ Reconstruyendo base de datos... (puede tardar)")
    try:
        cadena_rag = rag_module.reiniciar_bd()
        await update.message.reply_text("✅ Base de datos reconstruida.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Puedes escribirme de forma natural, sin comandos:\n\n"
        "💬 Ejemplos:\n"
        "  'qué clases hay hoy'\n"
        "  'tiene conflicto el horario del lunes'\n"
        "  'disponibilidad del profesor Martínez'\n"
        "  'cuántas horas puede dar un docente'\n"
        "  'solicito cambio de horario del martes'\n\n"
        "📷 También puedes enviar una foto de un horario.\n\n"
        "⚡ Comandos rápidos:\n"
        "/horario [hoy | nombre]  - Consultar horario\n"
        "/disponibilidad [nombre] - Ver disponibilidad\n"
        "/conflictos              - Detectar cruces\n"
        "/limpiar                 - Borrar historial\n"
        "/ayuda                   - Ver esta ayuda"
    )

# ============================================
# Recibir foto
# ============================================

async def recibir_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    os.makedirs(FOTOS_DIR, exist_ok=True)
    await update.message.reply_text("📸 Imagen recibida. Analizando con IA...")

    foto   = update.message.photo[-1]
    file   = await ctx.bot.get_file(foto.file_id)
    nombre = datetime.now().strftime("foto_%Y%m%d_%H%M%S.jpg")
    ruta   = os.path.join(FOTOS_DIR, nombre)          # ← ruta absoluta
    await file.download_to_drive(ruta)

    try:
        msg = await roboflow_api.analizar_horario(ruta)
    except Exception as e:
        msg = f"Error al analizar la imagen: {str(e)}"

    await update.message.reply_text(msg)

# ============================================
# Responder mensajes naturales
# ============================================

async def responder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if not texto:
        return
    uid       = get_uid(update)
    intencion = detectar_intencion(texto)
    pregunta  = construir_pregunta_enriquecida(texto, intencion)
    await update.message.reply_text("🔍 Buscando...")
    respuesta = await consultar_pdf(pregunta, uid)
    await update.message.reply_text(respuesta, parse_mode=None)

# ============================================
# Main
# ============================================

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",          start))
    app.add_handler(CommandHandler("horario",        horario))
    app.add_handler(CommandHandler("disponibilidad", disponibilidad))
    app.add_handler(CommandHandler("conflictos",     conflictos))
    app.add_handler(CommandHandler("limpiar",        limpiar))
    app.add_handler(CommandHandler("reiniciar_bd",   reiniciar_bd))
    app.add_handler(CommandHandler("ayuda",          ayuda))
    app.add_handler(MessageHandler(filters.PHOTO,                   recibir_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("Bot de Gestión de Horarios iniciado. Presiona Ctrl+C para detener.")
    app.run_polling()

if __name__ == "__main__":
    main()