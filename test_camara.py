"""
test_camara.py
--------------
Demo de prueba desde terminal.

1. Abre la camara en una ventana OpenCV
2. Presiona ESPACIO para capturar un frame
3. Envia la captura a Roboflow (deteccion visual)
4. Envia la captura a Groq Vision + consulta el RAG con el PDF
5. Imprime todo en terminal

Controles:
  ESPACIO  → capturar y analizar
  Q        → salir
"""

import cv2
import base64
import asyncio
import httpx
import os
import sys
from datetime import datetime

# ── Path para encontrar módulos en la raíz y en core/ ─────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import GROQ_API_KEY, GROQ_MODEL_VISION
import core.rag as rag_module

ROBOFLOW_API_KEY  = "oceK61twCXIqNSqyLB8q"
ROBOFLOW_MODEL_ID = "horarios-deteccion/2"
ROBOFLOW_URL      = f"https://detect.roboflow.com/{ROBOFLOW_MODEL_ID}"
GROQ_URL          = "https://api.groq.com/openai/v1/chat/completions"

# ── Roboflow ──────────────────────────────────────────────────────────────────

async def detectar_roboflow(img_b64: str) -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            ROBOFLOW_URL,
            params={"api_key": ROBOFLOW_API_KEY, "confidence": 25},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=img_b64,
        )
    if resp.status_code != 200:
        print(f"  [Roboflow] Error {resp.status_code}")
        return []
    return resp.json().get("predictions", [])


# ── Groq Vision ───────────────────────────────────────────────────────────────

async def describir_imagen(img_b64: str) -> str:
    payload = {
        "model": GROQ_MODEL_VISION,
        "max_tokens": 800,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                },
                {
                    "type": "text",
                    "text": (
                        "Analiza esta imagen. Si contiene un horario académico, "
                        "extrae: materias, días, horas, docentes y aulas visibles. "
                        "Si no es un horario, describe brevemente lo que ves. "
                        "Responde en español."
                    )
                }
            ]
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)

    if resp.status_code != 200:
        return f"Error Groq Vision ({resp.status_code})"
    return resp.json()["choices"][0]["message"]["content"]


# ── RAG ───────────────────────────────────────────────────────────────────────

def consultar_rag(cadena, descripcion_imagen: str) -> str:
    pregunta = (
        f"Basándote en el documento de horarios, busca información relacionada con "
        f"lo siguiente que se observa en una imagen capturada: {descripcion_imagen[:300]}"
    )
    return rag_module.consultar(cadena, pregunta, user_id="test_camara")


# ── Dibujar detecciones sobre frame ──────────────────────────────────────────

def dibujar_detecciones(frame, predicciones: list):
    colores = [(0,255,0),(255,100,0),(0,100,255),(255,0,200),(0,220,220)]
    for i, p in enumerate(predicciones):
        x1 = int(p["x"] - p["width"]  / 2)
        y1 = int(p["y"] - p["height"] / 2)
        x2 = int(p["x"] + p["width"]  / 2)
        y2 = int(p["y"] + p["height"] / 2)
        color = colores[i % len(colores)]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        etiqueta = f"{p['class']} {p['confidence']*100:.0f}%"
        cv2.putText(frame, etiqueta, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame


# ── Pipeline completo ─────────────────────────────────────────────────────────

async def analizar_captura(frame, cadena_rag):
    os.makedirs("assets/fotos", exist_ok=True)
    nombre = datetime.now().strftime("captura_%Y%m%d_%H%M%S.jpg")
    ruta   = os.path.join("assets/fotos", nombre)
    cv2.imwrite(ruta, frame)
    print(f"\n📸 Captura guardada: {ruta}")

    _, buf  = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    img_b64 = base64.b64encode(buf).decode("utf-8")

    print("\n🔍 Analizando con Roboflow...")
    predicciones = await detectar_roboflow(img_b64)
    if predicciones:
        print(f"  Roboflow detectó {len(predicciones)} elemento(s):")
        for p in predicciones:
            print(f"    • {p['class']}  ({p['confidence']*100:.1f}%)")
    else:
        print("  Roboflow: sin detecciones (modelo en entrenamiento).")

    print("\n👁️  Describiendo imagen con Vision IA...")
    descripcion = await describir_imagen(img_b64)
    print(f"\n  Descripción:\n{descripcion}")

    print("\n📚 Consultando base de conocimiento (RAG)...")
    respuesta_rag = consultar_rag(cadena_rag, descripcion)
    print(f"\n  Información relacionada:\n{respuesta_rag}")

    frame_anotado = dibujar_detecciones(frame.copy(), predicciones)
    cv2.imshow("Captura analizada", frame_anotado)

    print("\n" + "="*60)
    print("Presiona ESPACIO para otra captura o Q para salir.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("  TEST CÁMARA — Sistema de Gestión de Horarios")
    print("="*60)
    print("Inicializando RAG (puede tardar la primera vez)...")

    cadena_rag = rag_module.inicializar_rag()
    print("✅ RAG listo.\n")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara. Verifica que esté conectada.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("📷 Cámara abierta.")
    print("  → Apunta a una imagen/horario impreso o en pantalla")
    print("  → ESPACIO para capturar y analizar")
    print("  → Q para salir\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("❌ Error leyendo cámara.")
            break

        cv2.putText(frame, "ESPACIO=Capturar  Q=Salir",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Camara YOLO - Horarios", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord(' '):
            print("\n⏳ Procesando captura...")
            cv2.putText(frame, "Procesando...", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            cv2.imshow("Camara YOLO - Horarios", frame)
            cv2.waitKey(1)
            asyncio.run(analizar_captura(frame, cadena_rag))

    cap.release()
    cv2.destroyAllWindows()
    print("\nSesion terminada.")


if __name__ == "__main__":
    main()