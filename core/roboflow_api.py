import base64
import httpx
import json
import os
import sys

# ── Path para encontrar config.py en la raíz ──────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import GROQ_API_KEY, GROQ_MODEL_VISION

ROBOFLOW_API_KEY  = "oceK61twCXIqNSqyLB8q"
ROBOFLOW_MODEL_ID = "horarios-deteccion/3"
ROBOFLOW_URL      = f"https://serverless.roboflow.com/{ROBOFLOW_MODEL_ID}"
GROQ_URL          = "https://api.groq.com/openai/v1/chat/completions"


async def _detectar_con_roboflow(imagen_b64: str) -> list:
    """Paso 1: Roboflow detecta regiones/objetos en la imagen."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            ROBOFLOW_URL,
            params={"api_key": ROBOFLOW_API_KEY},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=imagen_b64
        )
    data = resp.json()
    print("RESPUESTA ROBOFLOW:", json.dumps(data, indent=2))
    return data.get("predictions", [])


async def _analizar_con_groq(imagen_b64: str, media_type: str, detecciones_roboflow: list) -> str:
    """Paso 2: Groq Vision extrae y analiza el contenido del horario."""
    contexto_roboflow = ""
    if detecciones_roboflow:
        items = [f"- {p['class']} ({round(p['confidence']*100,1)}%)" for p in detecciones_roboflow]
        contexto_roboflow = (
            f"\n\nNota: Roboflow detectó previamente estos elementos en la imagen:\n"
            + "\n".join(items)
        )

    payload = {
        "model": GROQ_MODEL_VISION,
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{imagen_b64}"}
                    },
                    {
                        "type": "text",
                        "text": (
                            "Eres un asistente especializado en horarios académicos universitarios. "
                            "Analiza esta imagen y extrae toda la información del horario.\n\n"
                            "Lista de forma clara y estructurada:\n"
                            "📚 Materias o asignaturas\n"
                            "📅 Días y horas de cada clase\n"
                            "👤 Docentes (si aparecen)\n"
                            "🏫 Aulas o salones (si aparecen)\n"
                            "⚠️ Posibles conflictos o cruces de horario\n"
                            + contexto_roboflow +
                            "\n\nResponde siempre en español."
                        )
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)

    if resp.status_code != 200:
        error_msg = resp.json().get("error", {}).get("message", resp.text[:200])
        return f"❌ Error Groq ({resp.status_code}): {error_msg}"

    return resp.json()["choices"][0]["message"]["content"]


async def analizar_horario(ruta_imagen: str) -> str:
    """
    Pipeline completo:
    1. Roboflow detecta elementos visuales en la imagen
    2. Groq Vision extrae y analiza el contenido del horario
    """
    with open(ruta_imagen, "rb") as f:
        imagen_b64 = base64.b64encode(f.read()).decode("utf-8")

    media_type = "image/png" if ruta_imagen.lower().endswith(".png") else "image/jpeg"

    # Paso 1: Roboflow
    try:
        detecciones = await _detectar_con_roboflow(imagen_b64)
        if detecciones:
            resumen_roboflow = (
                f"🔍 Roboflow detectó {len(detecciones)} elemento(s):\n"
                + "\n".join(f"  - {p['class']} ({round(p['confidence']*100,1)}%)" for p in detecciones)
                + "\n\n"
            )
        else:
            resumen_roboflow = "🔍 Roboflow procesó la imagen (modelo en entrenamiento).\n\n"
    except Exception as e:
        detecciones      = []
        resumen_roboflow = f"🔍 Roboflow no disponible: {str(e)}\n\n"

    # Paso 2: Groq Vision
    try:
        analisis = await _analizar_con_groq(imagen_b64, media_type, detecciones)
        return f"{resumen_roboflow}📋 Análisis del horario:\n\n{analisis}"
    except Exception as e:
        return f"{resumen_roboflow}❌ Error al analizar con Groq: {str(e)}"