import customtkinter as ctk
import requests
import threading
import webbrowser
import os
import sys
import cv2
import base64
import asyncio
import httpx
from tkinter import messagebox, StringVar, simpledialog
from datetime import datetime
from PIL import Image, ImageTk

# ── Paths para importar módulos del proyecto ──────────────────────────────────
# app.py vive en la RAÍZ del proyecto (NOJA_BOT/).
# core/rag.py está en NOJA_BOT/core/rag.py
# config.py está en NOJA_BOT/config.py
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# Asegurarse de que ROOT_DIR esté en sys.path para que
# "import core.rag" y "import config" funcionen correctamente.
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Cambiar el directorio de trabajo a ROOT_DIR para que las rutas
# relativas en config.py (CHROMA_DIR, DOCS_DIR, PDF_PATH) resuelvan bien.
os.chdir(ROOT_DIR)

# Imports del proyecto (se cargan lazy para no bloquear la UI)
rag_module   = None
cadena_rag   = None
CamaraYOLO  = None

BASE_URL = "http://localhost:8000/api/v1"

# Telegram — cambia este username si cambia el bot
TELEGRAM_BOT_URL = "https://t.me/noja_monitor_bot"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Color palette ────────────────────────────────────────────────────────────
C_BG      = "#0f1117"
C_PANEL   = "#1a1d2e"
C_CARD    = "#242738"
C_ACCENT  = "#4f8ef7"
C_ACCENT2 = "#7c3aed"
C_SUCCESS = "#10b981"
C_WARN    = "#f59e0b"
C_DANGER  = "#ef4444"
C_TEXT    = "#e2e8f0"
C_MUTED   = "#64748b"
C_TELE    = "#229ED9"   # color oficial Telegram

GROQ_API_KEY  = None
GROQ_MODEL_VISION = None
ROBOFLOW_API_KEY  = "oceK61twCXIqNSqyLB8q"
ROBOFLOW_MODEL_ID = "horarios-deteccion/2"
ROBOFLOW_URL      = f"https://detect.roboflow.com/{ROBOFLOW_MODEL_ID}"
GROQ_URL          = "https://api.groq.com/openai/v1/chat/completions"


def _cargar_config():
    global GROQ_API_KEY, GROQ_MODEL_VISION
    try:
        from config import GROQ_API_KEY as KEY, GROQ_MODEL_VISION as VISION
        GROQ_API_KEY      = KEY
        GROQ_MODEL_VISION = VISION
    except Exception:
        pass


def _cargar_rag():
    global rag_module, cadena_rag
    try:
        # Asegurar directorio de trabajo antes de importar
        os.chdir(ROOT_DIR)
        import core.rag as _rag
        rag_module = _rag
        print("[RAG] Inicializando cadena RAG...")
        cadena_rag = rag_module.inicializar_rag()
        # Verificar que sea un Runnable LangChain con método invoke
        if not callable(getattr(cadena_rag, "invoke", None)):
            print("[RAG] ADVERTENCIA: cadena_rag no tiene metodo invoke")
            cadena_rag = None
        else:
            print("[RAG] Cadena RAG lista OK")
    except Exception as e:
        import traceback
        print(f"[RAG] Error al inicializar:\n{traceback.format_exc()}")
        cadena_rag = None


def _cargar_camara_module():
    global CamaraYOLO
    try:
        from core.camara_yolo import CamaraYOLO as _C
        CamaraYOLO = _C
    except Exception as e:
        print(f"[CAMARA] Error al importar: {e}")


# ─── API helpers ──────────────────────────────────────────────────────────────
def api_get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "No se puede conectar con la API. ¿Está corriendo el servidor?"}
    except Exception as e:
        return {"error": str(e)}


def api_post(path, data):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=data, timeout=5)
        if not r.ok:
            # Intentar extraer el detalle del error del servidor
            try:
                detalle = r.json()
                msg = detalle.get("detail", detalle.get("message", r.text[:200]))
            except Exception:
                msg = r.text[:200] if r.text else f"Error HTTP {r.status_code}"
            return {"error": f"Error {r.status_code}: {msg}"}
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "No se puede conectar con la API. ¿Está corriendo el servidor?"}
    except Exception as e:
        return {"error": str(e)}


def api_delete(path):
    try:
        r = requests.delete(f"{BASE_URL}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def api_patch(path):
    try:
        r = requests.patch(f"{BASE_URL}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ─── Reusable widgets ─────────────────────────────────────────────────────────
class SectionTitle(ctk.CTkLabel):
    def __init__(self, master, text, **kw):
        super().__init__(master, text=text, font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=C_TEXT, **kw)


class SubTitle(ctk.CTkLabel):
    def __init__(self, master, text, **kw):
        super().__init__(master, text=text, font=ctk.CTkFont(size=13),
                         text_color=C_MUTED, **kw)


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C_CARD, corner_radius=12, **kw)


class PrimaryBtn(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C_ACCENT, hover_color="#3b71d4",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         corner_radius=8, height=36, **kw)


class DangerBtn(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C_DANGER, hover_color="#dc2626",
                         font=ctk.CTkFont(size=12), corner_radius=8, height=32, **kw)


class SuccessBtn(ctk.CTkButton):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C_SUCCESS, hover_color="#059669",
                         font=ctk.CTkFont(size=12), corner_radius=8, height=32, **kw)


class DataTable(ctk.CTkScrollableFrame):
    def __init__(self, master, columns, **kw):
        super().__init__(master, fg_color=C_CARD, **kw)
        self.columns = columns
        self._build_header()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="#1e2235", corner_radius=6)
        hdr.pack(fill="x", padx=4, pady=(4, 2))
        for i, col in enumerate(self.columns):
            ctk.CTkLabel(hdr, text=col, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=C_ACCENT).grid(row=0, column=i, padx=12, pady=6, sticky="w")
            hdr.columnconfigure(i, weight=1)

    def clear(self):
        for w in self.winfo_children()[1:]:
            w.destroy()

    def add_row(self, values, on_delete=None, on_action=None, action_label="✔ Resolver"):
        row = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        for i, val in enumerate(values):
            ctk.CTkLabel(row, text=str(val)[:40], font=ctk.CTkFont(size=12),
                         text_color=C_TEXT, anchor="w").grid(row=0, column=i, padx=12, pady=8, sticky="w")
            row.columnconfigure(i, weight=1)
        btn_col = len(values)
        if on_action:
            SuccessBtn(row, text=action_label, width=90,
                       command=on_action).grid(row=0, column=btn_col, padx=4)
            btn_col += 1
        if on_delete:
            DangerBtn(row, text="🗑 Eliminar", width=90,
                      command=on_delete).grid(row=0, column=btn_col, padx=4)


# ─── Pages ────────────────────────────────────────────────────────────────────
class DashboardPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "📊 Dashboard").pack(anchor="w", padx=20, pady=(20, 4))
        SubTitle(self, "Resumen del sistema de gestión de horarios").pack(anchor="w", padx=20, pady=(0, 20))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=20)
        grid.columnconfigure((0, 1, 2, 3), weight=1)

        self.cards_data = [
            ("👨‍🏫 Docentes",      "/docentes",              C_ACCENT),
            ("🏫 Salones",         "/salones",               C_ACCENT2),
            ("📅 Asignaciones",    "/asignaciones",          C_SUCCESS),
            ("⚠️ Conflictos",     "/conflictos?resuelto=false", C_DANGER),
        ]
        self.stat_labels = []
        for i, (label, path, color) in enumerate(self.cards_data):
            card = ctk.CTkFrame(grid, fg_color=C_CARD, corner_radius=14)
            card.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=color).pack(padx=16, pady=(16, 4))
            lbl = ctk.CTkLabel(card, text="...", font=ctk.CTkFont(size=32, weight="bold"),
                               text_color=C_TEXT)
            lbl.pack(pady=(0, 16))
            self.stat_labels.append(lbl)

        sep = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=12)
        sep.pack(fill="both", expand=True, padx=20, pady=(16, 20))
        ctk.CTkLabel(sep, text="📌 Asignaciones recientes",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=16, pady=12)
        self.recent_frame = ctk.CTkScrollableFrame(sep, fg_color="transparent", height=220)
        self.recent_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.refresh()

    def refresh(self):
        def load():
            for i, (_, path, _) in enumerate(self.cards_data):
                data = api_get(path.split("?")[0],
                               params={"resuelto": "false"} if "resuelto" in path else None)
                count = len(data) if isinstance(data, list) else "!"
                self.stat_labels[i].configure(text=str(count))

            asigs = api_get("/asignaciones")
            for w in self.recent_frame.winfo_children():
                w.destroy()
            if isinstance(asigs, list):
                for a in asigs[:15]:
                    row = ctk.CTkFrame(self.recent_frame, fg_color=C_CARD, corner_radius=8)
                    row.pack(fill="x", pady=3)
                    txt = (f"  {a.get('dia','?').capitalize()}  "
                           f"{a.get('hora_inicio','?')}-{a.get('hora_fin','?')}   "
                           f"Periodo: {a.get('periodo','?')}")
                    ctk.CTkLabel(row, text=txt, font=ctk.CTkFont(size=12),
                                 text_color=C_TEXT, anchor="w").pack(side="left", padx=8, pady=8)

        threading.Thread(target=load, daemon=True).start()


# ─── RAG Chatbot Page ─────────────────────────────────────────────────────────
class ChatbotRAGPage(ctk.CTkFrame):
    """
    Chatbot integrado con LangChain + ChromaDB (RAG).
    Consulta directamente la base vectorial local y los PDFs en Docs_Dir.
    """
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "🤖 Chatbot RAG — Consulta Documental").pack(anchor="w", padx=20, pady=(20, 4))
        SubTitle(self, "Consulta horarios, reglamento y normativas desde los documentos institucionales").pack(
            anchor="w", padx=20, pady=(0, 12))

        # Estado RAG
        self.rag_listo = False
        self.user_id   = "app_desktop"

        # ── Barra de estado RAG ──
        status_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=10)
        status_bar.pack(fill="x", padx=20, pady=(0, 8))
        self.rag_status = ctk.CTkLabel(
            status_bar, text="⏳ Inicializando RAG...",
            font=ctk.CTkFont(size=12), text_color=C_WARN)
        self.rag_status.pack(side="left", padx=14, pady=8)
        ctk.CTkButton(
            status_bar, text="🔄 Reiniciar base", width=130,
            fg_color=C_ACCENT2, hover_color="#6d28d9",
            font=ctk.CTkFont(size=12), corner_radius=8, height=30,
            command=self._reiniciar_bd).pack(side="right", padx=10, pady=6)
        ctk.CTkButton(
            status_bar, text="🗑 Limpiar chat", width=120,
            fg_color=C_MUTED, hover_color="#475569",
            font=ctk.CTkFont(size=12), corner_radius=8, height=30,
            command=self._limpiar_chat).pack(side="right", padx=4, pady=6)

        # ── Historial de chat ──
        self.chat_box = ctk.CTkScrollableFrame(self, fg_color=C_CARD, corner_radius=12, height=420)
        self.chat_box.pack(fill="both", expand=True, padx=20, pady=4)

        # ── Input ──
        inp_row = ctk.CTkFrame(self, fg_color="transparent")
        inp_row.pack(fill="x", padx=20, pady=(4, 16))
        self.entrada = ctk.CTkEntry(
            inp_row, placeholder_text="Escribe tu pregunta aquí...",
            fg_color=C_CARD, height=40, font=ctk.CTkFont(size=13))
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entrada.bind("<Return>", lambda e: self._enviar())
        PrimaryBtn(inp_row, text="Enviar ➤", command=self._enviar, width=100).pack(side="left")

        # Sugerencias rápidas
        sugs = ctk.CTkFrame(self, fg_color="transparent")
        sugs.pack(fill="x", padx=20, pady=(0, 8))
        sugerencias = [
            "¿Qué clases hay hoy?",
            "¿Hay conflictos de horario?",
            "Máx. horas por docente",
            "Disponibilidad Prof. García",
            "Horario del lunes",
        ]
        for s in sugerencias:
            ctk.CTkButton(
                sugs, text=s, height=28,
                fg_color=C_PANEL, hover_color=C_CARD,
                text_color=C_MUTED, font=ctk.CTkFont(size=11),
                corner_radius=6,
                command=lambda t=s: self._enviar_texto(t)
            ).pack(side="left", padx=3)

        # Cargar RAG en background
        threading.Thread(target=self._init_rag, daemon=True).start()

    def _init_rag(self):
        global rag_module, cadena_rag
        try:
            self.rag_status.configure(text="⏳ Cargando base vectorial...", text_color=C_WARN)
            if rag_module is None:
                _cargar_rag()
            if cadena_rag is not None:
                self.rag_listo = True
                self.rag_status.configure(text="✅ RAG listo — Base vectorial cargada", text_color=C_SUCCESS)
                self._agregar_mensaje(
                    "asistente",
                    "✅ Sistema listo. Puedo responder preguntas sobre horarios, "
                    "disponibilidad docente, conflictos y normativas institucionales.\n\n"
                    "Escribe tu pregunta o usa las sugerencias de abajo."
                )
            else:
                self.rag_status.configure(text="❌ RAG no disponible — Revisa core/rag.py", text_color=C_DANGER)
        except Exception as e:
            self.rag_status.configure(text=f"❌ Error RAG: {str(e)[:60]}", text_color=C_DANGER)

    def _reiniciar_bd(self):
        def run():
            global cadena_rag
            self.rag_listo = False
            self.rag_status.configure(text="⏳ Reconstruyendo base...", text_color=C_WARN)
            try:
                cadena_rag = rag_module.reiniciar_bd()
                self.rag_listo = True
                self.rag_status.configure(text="✅ Base reconstruida", text_color=C_SUCCESS)
            except Exception as e:
                self.rag_status.configure(text=f"❌ {str(e)[:60]}", text_color=C_DANGER)
        threading.Thread(target=run, daemon=True).start()

    def _limpiar_chat(self):
        for w in self.chat_box.winfo_children():
            w.destroy()
        if rag_module:
            try:
                rag_module.limpiar_historial(self.user_id)
            except Exception:
                pass

    def _agregar_mensaje(self, rol: str, texto: str):
        """Agrega una burbuja al historial de chat."""
        es_usuario = rol == "usuario"
        color   = C_ACCENT  if es_usuario else C_PANEL
        anchor  = "e"       if es_usuario else "w"
        prefijo = "👤 Tú"  if es_usuario else "🤖 Asistente"

        burbuja = ctk.CTkFrame(self.chat_box, fg_color=color, corner_radius=10)
        burbuja.pack(anchor=anchor, padx=12, pady=4, fill="x")

        ctk.CTkLabel(burbuja, text=prefijo,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=C_TEXT if es_usuario else C_ACCENT).pack(anchor="w", padx=10, pady=(6, 0))
        ctk.CTkLabel(burbuja, text=texto,
                     font=ctk.CTkFont(size=12),
                     text_color=C_TEXT,
                     wraplength=700, justify="left",
                     anchor="w").pack(anchor="w", padx=10, pady=(2, 8))

        # Auto-scroll
        self.chat_box.after(100, lambda: self.chat_box._parent_canvas.yview_moveto(1.0))

    def _enviar_texto(self, texto: str):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self._enviar()

    def _enviar(self):
        texto = self.entrada.get().strip()
        if not texto:
            return
        self.entrada.delete(0, "end")

        if not self.rag_listo or cadena_rag is None:
            messagebox.showwarning("RAG no disponible",
                                   "La base vectorial aún se está cargando. Espera unos segundos.")
            return

        self._agregar_mensaje("usuario", texto)

        # Placeholder mientras carga
        placeholder = ctk.CTkFrame(self.chat_box, fg_color=C_PANEL, corner_radius=10)
        placeholder.pack(anchor="w", padx=12, pady=4, fill="x")
        lbl_load = ctk.CTkLabel(placeholder, text="⏳ Consultando...",
                                font=ctk.CTkFont(size=12), text_color=C_WARN)
        lbl_load.pack(padx=10, pady=8)

        # Diccionario mutable para pasar la respuesta entre hilos de forma segura
        resultado = {"texto": None}

        def run():
            try:
                resultado["texto"] = rag_module.consultar(cadena_rag, texto, user_id=self.user_id)
            except Exception as e:
                resultado["texto"] = f"❌ Error al consultar: {str(e)}"
            # Programar el update en el hilo principal de tkinter
            self.after(0, actualizar_ui)

        def actualizar_ui():
            try:
                placeholder.destroy()
            except Exception:
                pass
            self._agregar_mensaje("asistente", resultado["texto"])

        threading.Thread(target=run, daemon=True).start()


# ─── Cámara / Escaneo Físico Page ─────────────────────────────────────────────
class CamaraPage(ctk.CTkFrame):
    """
    Captura con la cámara del PC, detecta con Roboflow y describe con Groq Vision.
    El resultado del análisis se muestra en la misma página.
    """
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "📷 Lector de Horarios Físicos").pack(anchor="w", padx=20, pady=(20, 4))
        SubTitle(self, "Apunta la cámara a un horario impreso o en pantalla y captura para analizarlo con IA").pack(
            anchor="w", padx=20, pady=(0, 12))

        self._camara_activa = False
        self._cap           = None
        self._hilo_camara   = None

        # Layout principal: izq = cámara, der = resultado
        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=20, pady=4)
        contenido.columnconfigure(0, weight=3)
        contenido.columnconfigure(1, weight=2)
        contenido.rowconfigure(0, weight=1)

        # ── Panel izquierdo: feed de cámara ──
        panel_cam = Card(contenido)
        panel_cam.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="nsew")

        ctk.CTkLabel(panel_cam, text="Vista en tiempo real",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_MUTED).pack(pady=(10, 4))

        self.cam_label = ctk.CTkLabel(panel_cam, text="",
                                       fg_color=C_BG, corner_radius=8,
                                       width=560, height=380)
        self.cam_label.pack(padx=10, pady=4)

        # Placeholder cuando no hay cámara
        self._mostrar_placeholder()

        # Controles
        ctrl = ctk.CTkFrame(panel_cam, fg_color="transparent")
        ctrl.pack(pady=(6, 12))

        self.btn_iniciar = ctk.CTkButton(
            ctrl, text="▶ Iniciar cámara",
            fg_color=C_SUCCESS, hover_color="#059669",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8, height=36, width=150,
            command=self._toggle_camara)
        self.btn_iniciar.pack(side="left", padx=6)

        ctk.CTkButton(
            ctrl, text="📸 Capturar y Analizar",
            fg_color=C_ACCENT, hover_color="#3b71d4",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8, height=36, width=180,
            command=self._capturar).pack(side="left", padx=6)

        self.cam_status = ctk.CTkLabel(panel_cam, text="Cámara detenida",
                                        font=ctk.CTkFont(size=11), text_color=C_MUTED)
        self.cam_status.pack(pady=(0, 8))

        # ── Panel derecho: resultado del análisis ──
        panel_res = Card(contenido)
        panel_res.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="nsew")

        ctk.CTkLabel(panel_res, text="🔍 Resultado del Análisis",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT).pack(pady=(14, 6), padx=14)

        # Detecciones Roboflow
        ctk.CTkLabel(panel_res, text="Detecciones YOLO / Roboflow:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=14)
        self.detecciones_lbl = ctk.CTkLabel(
            panel_res, text="—",
            font=ctk.CTkFont(size=11), text_color=C_TEXT,
            wraplength=320, justify="left")
        self.detecciones_lbl.pack(anchor="w", padx=14, pady=(2, 10))

        # Separador
        ctk.CTkFrame(panel_res, fg_color=C_PANEL, height=2).pack(fill="x", padx=14, pady=4)

        # Descripción Vision IA
        ctk.CTkLabel(panel_res, text="📄 Contenido detectado en la imagen:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=14, pady=(6, 2))

        self.resultado_box = ctk.CTkTextbox(
            panel_res, fg_color=C_BG, text_color=C_TEXT,
            font=ctk.CTkFont(size=11), wrap="word",
            width=340, height=220)
        self.resultado_box.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.resultado_box.insert("1.0", "Captura una imagen para ver el análisis aquí.")
        self.resultado_box.configure(state="disabled")

        # Separador
        ctk.CTkFrame(panel_res, fg_color=C_PANEL, height=2).pack(fill="x", padx=14, pady=4)

        # Respuesta RAG vinculada
        ctk.CTkLabel(panel_res, text="📚 Info relacionada (RAG):",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=14, pady=(4, 2))

        self.rag_box = ctk.CTkTextbox(
            panel_res, fg_color=C_BG, text_color=C_TEXT,
            font=ctk.CTkFont(size=11), wrap="word",
            width=340, height=140)
        self.rag_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.rag_box.insert("1.0", "Se mostrará información del documento relacionada con la imagen.")
        self.rag_box.configure(state="disabled")

        self._ultimo_frame = None
        _cargar_config()

    def _mostrar_placeholder(self):
        ph = Image.new("RGB", (560, 380), color=(30, 33, 50))
        imgtk = ImageTk.PhotoImage(ph)
        self.cam_label.configure(image=imgtk, text="")
        self.cam_label.image = imgtk

    def _toggle_camara(self):
        if self._camara_activa:
            self._detener_camara()
        else:
            self._iniciar_camara()

    def _iniciar_camara(self):
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            messagebox.showerror("Error", "No se pudo abrir la cámara.\nVerifica que esté conectada.")
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._camara_activa = True
        self.btn_iniciar.configure(text="⏹ Detener cámara", fg_color=C_DANGER, hover_color="#b91c1c")
        self.cam_status.configure(text="● Cámara activa", text_color=C_SUCCESS)
        self._hilo_camara = threading.Thread(target=self._loop_camara, daemon=True)
        self._hilo_camara.start()

    def _detener_camara(self):
        self._camara_activa = False
        if self._cap:
            self._cap.release()
        self.btn_iniciar.configure(text="▶ Iniciar cámara", fg_color=C_SUCCESS, hover_color="#059669")
        self.cam_status.configure(text="Cámara detenida", text_color=C_MUTED)
        self._mostrar_placeholder()

    def _loop_camara(self):
        while self._camara_activa:
            ok, frame = self._cap.read()
            if not ok:
                break
            self._ultimo_frame = frame.copy()
            # Dibujar instrucción
            cv2.putText(frame, "ESPACIO=Capturar | Boton Capturar y Analizar",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            self._actualizar_label(frame)
        self._camara_activa = False

    def _actualizar_label(self, frame):
        try:
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            img   = img.resize((560, 380))
            imgtk = ImageTk.PhotoImage(image=img)
            self.cam_label.after(0, self._set_image, imgtk)
        except Exception:
            pass

    def _set_image(self, imgtk):
        try:
            self.cam_label.configure(image=imgtk, text="")
            self.cam_label.image = imgtk
        except Exception:
            pass

    def _capturar(self):
        if self._ultimo_frame is None:
            messagebox.showwarning("Sin imagen", "Inicia la cámara primero y espera a que aparezca el video.")
            return
        frame = self._ultimo_frame.copy()
        self.cam_status.configure(text="⏳ Analizando captura...", text_color=C_WARN)
        threading.Thread(target=self._analizar, args=(frame,), daemon=True).start()

    def _analizar(self, frame):
        # Guardar captura
        fotos_dir = os.path.join(ROOT_DIR, "assets", "fotos")
        os.makedirs(fotos_dir, exist_ok=True)
        nombre = datetime.now().strftime("captura_%Y%m%d_%H%M%S.jpg")
        ruta   = os.path.join(fotos_dir, nombre)
        cv2.imwrite(ruta, frame)

        _, buf  = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buf).decode("utf-8")

        # 1. Roboflow
        self._set_resultado("⏳ Detectando elementos con Roboflow...", self.detecciones_lbl)
        predicciones = self._llamar_roboflow(img_b64)

        if predicciones:
            texto_det = "\n".join(
                f"• {p['class']}  ({p['confidence']*100:.1f}%)" for p in predicciones)
        else:
            texto_det = "Sin detecciones concretas (modelo en entrenamiento o imagen sin horario visible)"
        self._set_resultado(texto_det, self.detecciones_lbl)

        # Dibujar bboxes en el frame mostrado
        frame_det = frame.copy()
        colores = [(0,255,0),(255,100,0),(0,100,255),(255,0,200),(0,220,220)]
        for i, p in enumerate(predicciones):
            x1 = int(p["x"] - p["width"]  / 2)
            y1 = int(p["y"] - p["height"] / 2)
            x2 = int(p["x"] + p["width"]  / 2)
            y2 = int(p["y"] + p["height"] / 2)
            c  = colores[i % len(colores)]
            cv2.rectangle(frame_det, (x1, y1), (x2, y2), c, 2)
            cv2.putText(frame_det, f"{p['class']} {p['confidence']*100:.0f}%",
                        (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2)
        self._actualizar_label(frame_det)

        # 2. Groq Vision
        self._set_textbox("⏳ Describiendo imagen con Vision IA...", self.resultado_box)
        descripcion = self._llamar_vision(img_b64)
        self._set_textbox(descripcion, self.resultado_box)

        # 3. RAG vinculado
        self._set_textbox("⏳ Consultando base documental...", self.rag_box)
        respuesta_rag = self._consultar_rag(descripcion)
        self._set_textbox(respuesta_rag, self.rag_box)

        self.cam_status.configure(text=f"✅ Análisis completado — {nombre}", text_color=C_SUCCESS)

    def _set_resultado(self, texto, label_widget):
        try:
            label_widget.configure(text=texto)
        except Exception:
            pass

    def _set_textbox(self, texto, textbox):
        try:
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.insert("1.0", texto)
            textbox.configure(state="disabled")
        except Exception:
            pass

    def _llamar_roboflow(self, img_b64: str) -> list:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    ROBOFLOW_URL,
                    params={"api_key": ROBOFLOW_API_KEY, "confidence": 25},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    content=img_b64,
                )
            if resp.status_code != 200:
                return []
            return resp.json().get("predictions", [])
        except Exception as e:
            print(f"[Roboflow] {e}")
            return []

    def _llamar_vision(self, img_b64: str) -> str:
        if not GROQ_API_KEY:
            return "⚠️ GROQ_API_KEY no configurado. Revisa config.py"
        if not GROQ_MODEL_VISION:
            return "⚠️ GROQ_MODEL_VISION no configurado. Revisa config.py"
        try:
            payload = {
                "model": GROQ_MODEL_VISION,
                "max_tokens": 800,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text",
                         "text": ("Analiza esta imagen. Si contiene un horario académico, "
                                  "extrae: materias, días, horas, docentes y aulas visibles. "
                                  "Si no es un horario, describe brevemente lo que ves. "
                                  "Responde en español.")}
                    ]
                }]
            }
            headers = {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            }
            resp = httpx.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code != 200:
                return f"Error Groq Vision ({resp.status_code}): {resp.text[:200]}"
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error Vision IA: {str(e)}"

    def _consultar_rag(self, descripcion: str) -> str:
        if cadena_rag is None or rag_module is None:
            return "⚠️ RAG no disponible. Ve a la sección Chatbot RAG para inicializarlo."
        try:
            pregunta = (
                f"Basándote en el documento de horarios, busca información relacionada con "
                f"lo siguiente que se observa en una imagen capturada: {descripcion[:400]}"
            )
            return rag_module.consultar(cadena_rag, pregunta, user_id="camara_desktop")
        except Exception as e:
            return f"Error RAG: {str(e)}"

    def destroy(self):
        self._camara_activa = False
        if self._cap:
            self._cap.release()
        super().destroy()


# ─── Resto de páginas ─────────────────────────────────────────────────────────
class DocentesPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "👨‍🏫 Docentes").pack(anchor="w", padx=20, pady=(20, 4))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=8)

        form = Card(top)
        form.pack(side="left", fill="y", padx=(0, 12), pady=0, ipadx=16, ipady=10)
        ctk.CTkLabel(form, text="Nuevo Docente", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT).pack(pady=(12, 8))

        self.nombre_var = StringVar()
        self.email_var  = StringVar()
        self.tel_var    = StringVar()

        for label, var in [("Nombre completo", self.nombre_var),
                            ("Email", self.email_var),
                            ("Teléfono", self.tel_var)]:
            ctk.CTkLabel(form, text=label, text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
            ctk.CTkEntry(form, textvariable=var, width=240, height=34, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))

        PrimaryBtn(form, text="➕ Agregar Docente", command=self.crear_docente).pack(pady=(4, 16), padx=12, fill="x")

        table_frame = ctk.CTkFrame(top, fg_color="transparent")
        table_frame.pack(side="left", fill="both", expand=True)
        PrimaryBtn(table_frame, text="🔄 Actualizar", command=self.cargar, width=120).pack(anchor="e", pady=(0, 6))
        self.table = DataTable(table_frame, ["Nombre", "Email", "Teléfono", "Estado"], height=340)
        self.table.pack(fill="both", expand=True)
        self.docentes = []
        self.cargar()

    def cargar(self):
        def load():
            data = api_get("/docentes")
            self.table.clear()
            if isinstance(data, list):
                self.docentes = data
                for d in data:
                    did = d["id"]
                    self.table.add_row(
                        [d["nombre"], d["email"], d.get("telefono", "-"),
                         "✅ Activo" if d["activo"] else "❌ Inactivo"],
                        on_delete=lambda i=did: self.eliminar(i))
        threading.Thread(target=load, daemon=True).start()

    def crear_docente(self):
        data = {"nombre": self.nombre_var.get(), "email": self.email_var.get(),
                "telefono": self.tel_var.get()}
        if not data["nombre"] or not data["email"]:
            messagebox.showwarning("Campos requeridos", "Nombre y email son obligatorios")
            return
        res = api_post("/docentes", data)
        if "error" in res:
            messagebox.showerror("Error", res["error"])
        else:
            messagebox.showinfo("Éxito", f"Docente {data['nombre']} creado correctamente")
            self.nombre_var.set(""); self.email_var.set(""); self.tel_var.set("")
            self.cargar()

    def eliminar(self, docente_id):
        if messagebox.askyesno("Confirmar", "¿Desactivar este docente?"):
            res = api_delete(f"/docentes/{docente_id}")
            if "error" not in res:
                self.cargar()


class SalonesPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "🏫 Salones").pack(anchor="w", padx=20, pady=(20, 4))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=8)

        form = Card(top)
        form.pack(side="left", fill="y", padx=(0, 12), ipadx=16, ipady=10)
        ctk.CTkLabel(form, text="Nuevo Salón", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT).pack(pady=(12, 8))

        self.nombre_var = StringVar()
        self.cap_var    = StringVar(value="30")
        self.cod_var    = StringVar()

        for label, var in [("Nombre", self.nombre_var),
                            ("Capacidad", self.cap_var),
                            ("Código (ej: A101)", self.cod_var)]:
            ctk.CTkLabel(form, text=label, text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
            ctk.CTkEntry(form, textvariable=var, width=220, height=34, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))

        PrimaryBtn(form, text="➕ Agregar Salón", command=self.crear_salon).pack(pady=(4, 16), padx=12, fill="x")

        check = Card(top)
        check.pack(side="left", fill="y", padx=(0, 12), ipadx=16, ipady=10)
        ctk.CTkLabel(check, text="🔍 Verificar Disponibilidad",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=C_ACCENT2).pack(pady=(12, 8))

        self.dia_var = StringVar(value="lunes")
        self.hi_var  = StringVar(value="08:00")
        self.hf_var  = StringVar(value="10:00")

        ctk.CTkLabel(check, text="Día", text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
        ctk.CTkOptionMenu(check, values=["lunes","martes","miércoles","jueves","viernes","sábado"],
                          variable=self.dia_var, width=200, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))
        for lbl, var in [("Hora inicio", self.hi_var), ("Hora fin", self.hf_var)]:
            ctk.CTkLabel(check, text=lbl, text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
            ctk.CTkEntry(check, textvariable=var, width=200, height=34, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))
        PrimaryBtn(check, text="🔍 Buscar Disponibles", command=self.verificar_disp).pack(padx=12, pady=(4, 16), fill="x")

        table_f = ctk.CTkFrame(top, fg_color="transparent")
        table_f.pack(side="left", fill="both", expand=True)
        PrimaryBtn(table_f, text="🔄 Actualizar", command=self.cargar, width=120).pack(anchor="e", pady=(0, 6))
        self.table = DataTable(table_f, ["Nombre", "Capacidad", "Código", "Estado"], height=340)
        self.table.pack(fill="both", expand=True)
        self.cargar()

    def cargar(self):
        def load():
            data = api_get("/salones")
            self.table.clear()
            if isinstance(data, list):
                for s in data:
                    sid = s["id"]
                    self.table.add_row(
                        [s["nombre"], s.get("capacidad", "-"), s.get("codigo", "-"),
                         "✅" if s["activo"] else "❌"],
                        on_delete=lambda i=sid: self.eliminar(i))
        threading.Thread(target=load, daemon=True).start()

    def crear_salon(self):
        data = {"nombre": self.nombre_var.get(), "capacidad": self.cap_var.get(),
                "codigo": self.cod_var.get()}
        if not data["nombre"]:
            messagebox.showwarning("Campo requerido", "Ingrese el nombre del salón")
            return
        if not data["codigo"]:
            messagebox.showwarning("Campo requerido", "Ingrese el código del salón")
            return
        res = api_post("/salones", data)
        if "error" in res:
            messagebox.showerror("Error", res["error"])
        else:
            messagebox.showinfo("Éxito", "Salón creado")
            self.cargar()

    def verificar_disp(self):
        data = api_get("/salones/disponibles",
                       params={"dia": self.dia_var.get(), "hora_inicio": self.hi_var.get(),
                               "hora_fin": self.hf_var.get()})
        self.table.clear()
        if isinstance(data, list):
            for s in data:
                self.table.add_row([s["nombre"], s.get("capacidad", "-"),
                                    s.get("codigo", "-"), "✅ Libre"])

    def eliminar(self, sid):
        if messagebox.askyesno("Confirmar", "¿Desactivar este salón?"):
            api_delete(f"/salones/{sid}")
            self.cargar()


class AsignacionesPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "📅 Asignaciones").pack(anchor="w", padx=20, pady=(20, 4))

        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=20, pady=8)

        form = Card(paned)
        form.pack(side="left", fill="y", padx=(0, 14), ipadx=14, ipady=12)
        ctk.CTkLabel(form, text="Nueva Asignación",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=C_ACCENT).pack(pady=(12, 8))

        self.docente_var = StringVar()
        self.grupo_var   = StringVar()
        self.materia_var = StringVar()
        self.salon_var   = StringVar()
        self.dia_var     = StringVar(value="lunes")
        self.hi_var      = StringVar(value="08:00")
        self.hf_var      = StringVar(value="10:00")
        self.periodo_var = StringVar(value="2026-1")

        fields = [("ID Docente", self.docente_var), ("ID Grupo", self.grupo_var),
                  ("ID Materia", self.materia_var), ("ID Salón", self.salon_var), ("Hora inicio", self.hi_var),
                  ("Hora fin", self.hf_var), ("Periodo", self.periodo_var)]
        for lbl, var in fields:
            ctk.CTkLabel(form, text=lbl, text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
            ctk.CTkEntry(form, textvariable=var, width=230, height=34, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))

        ctk.CTkLabel(form, text="Día", text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
        ctk.CTkOptionMenu(form, values=["lunes","martes","miércoles","jueves","viernes","sábado"],
                          variable=self.dia_var, width=230, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))

        PrimaryBtn(form, text="📌 Crear Asignación", command=self.crear).pack(padx=12, pady=(8, 16), fill="x")

        right = ctk.CTkFrame(paned, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        flt = ctk.CTkFrame(right, fg_color=C_PANEL, corner_radius=10)
        flt.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(flt, text="Filtrar:", text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=12, pady=8)
        self.flt_periodo = ctk.CTkEntry(flt, placeholder_text="Periodo (ej. 2026-1)", width=150, height=30, fg_color=C_CARD)
        self.flt_periodo.pack(side="left", padx=6, pady=8)
        self.flt_dia = ctk.CTkEntry(flt, placeholder_text="Día", width=100, height=30, fg_color=C_CARD)
        self.flt_dia.pack(side="left", padx=6)
        PrimaryBtn(flt, text="Buscar", command=self.cargar, width=80).pack(side="left", padx=8)
        PrimaryBtn(flt, text="🔄 Todo", command=lambda: self.cargar(clear=True), width=80).pack(side="left")

        self.table = DataTable(right, ["Día", "Inicio", "Fin", "Periodo", "Docente ID"], height=400)
        self.table.pack(fill="both", expand=True)
        self.cargar()

    def cargar(self, clear=False):
        if clear:
            self.flt_periodo.delete(0, "end")
            self.flt_dia.delete(0, "end")
        def load():
            params = {}
            p = self.flt_periodo.get()
            d = self.flt_dia.get()
            if p: params["periodo"] = p
            if d: params["dia"]     = d
            data = api_get("/asignaciones", params=params if params else None)
            self.table.clear()
            if isinstance(data, list):
                for a in data:
                    aid = a["id"]
                    self.table.add_row(
                        [a.get("dia","?"), a.get("hora_inicio","?"), a.get("hora_fin","?"),
                         a.get("periodo","?"), a.get("docente_id","?")[:8]+"..."],
                        on_delete=lambda i=aid: self.eliminar(i))
        threading.Thread(target=load, daemon=True).start()

    def crear(self):
        data = {"docente_id": self.docente_var.get(), "grupo_id": self.grupo_var.get(),
                "materia_id": self.materia_var.get(), "salon_id": self.salon_var.get(), "dia": self.dia_var.get(),
                "hora_inicio": self.hi_var.get(), "hora_fin": self.hf_var.get(),
                "periodo": self.periodo_var.get()}
        if not all([data["docente_id"], data["grupo_id"], data["materia_id"], data["salon_id"]]):
            messagebox.showwarning("Campos requeridos", "Complete todos los IDs (Docente, Grupo, Materia, Salón)")
            return
        res = api_post("/asignaciones", data)
        if "error" in res:
            messagebox.showerror("Error", res["error"])
        else:
            messagebox.showinfo("✅ Asignación creada", f"ID: {res.get('id','')[:12]}...")
            self.cargar()

    def eliminar(self, aid):
        if messagebox.askyesno("Confirmar", "¿Eliminar esta asignación?"):
            api_delete(f"/asignaciones/{aid}")
            self.cargar()


class ConflictosPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "⚠️ Conflictos").pack(anchor="w", padx=20, pady=(20, 4))
        SubTitle(self, "Detección automática de cruces y sobrecargas").pack(anchor="w", padx=20, pady=(0, 12))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=4)
        PrimaryBtn(bar, text="🔍 Detectar Conflictos", command=self.detectar).pack(side="left", padx=(0, 8))
        PrimaryBtn(bar, text="🔄 Actualizar lista",    command=self.cargar).pack(side="left", padx=(0, 8))
        self.filter_var = StringVar(value="todos")
        ctk.CTkSegmentedButton(bar, values=["todos", "pendientes", "resueltos"],
                               variable=self.filter_var,
                               command=lambda _: self.cargar()).pack(side="left", padx=8)

        self.table = DataTable(self, ["ID", "Tipo", "Docente/Recurso", "Día", "Hora", "Detalle", "Estado"], height=440)
        self.table.pack(fill="both", expand=True, padx=20, pady=12)
        self.cargar()

    def cargar(self):
        def load():
            filtro = self.filter_var.get()
            params = None
            if filtro == "pendientes": params = {"resuelto": "false"}
            elif filtro == "resueltos": params = {"resuelto": "true"}
            data = api_get("/conflictos", params=params)
            self.table.clear()
            if isinstance(data, list):
                for c in data:
                    cid = c["id"]
                    self.table.add_row(
                        [c.get("descripcion","?")[:4],
                         c.get("tipo","?"),
                         c.get("docente_recurso","?"),
                         c.get("dia","?"),
                         c.get("hora","?"),
                         (c.get("descripcion","") or "")[7:57],
                         c.get("estado_conflicto","Pendiente")],
                        on_action=None if c.get("resuelto") else (lambda i=cid: self.resolver(i)),
                        action_label="✔ Resolver",
                        on_delete=lambda i=cid: self.eliminar(i))
        threading.Thread(target=load, daemon=True).start()

    def detectar(self):
        res = api_post("/conflictos/detectar", {})
        if "error" in res:
            messagebox.showerror("Error", res["error"])
        else:
            n = res.get("conflictos_detectados", 0)
            messagebox.showinfo("Detección completa", f"Se detectaron {n} nuevo(s) conflicto(s)")
            self.cargar()

    def resolver(self, cid):
        res = api_patch(f"/conflictos/{cid}/resolver")
        if "error" not in res: self.cargar()

    def eliminar(self, cid):
        if messagebox.askyesno("Confirmar", "¿Eliminar este conflicto?"):
            api_delete(f"/conflictos/{cid}")
            self.cargar()


class HorarioDocentePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "🗓️ Horario por Docente").pack(anchor="w", padx=20, pady=(20, 4))

        bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=10)
        bar.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(bar, text="ID Docente:", text_color=C_MUTED,
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=12, pady=10)
        self.id_entry = ctk.CTkEntry(bar, width=300, height=34, fg_color=C_CARD,
                                      placeholder_text="Pega el UUID del docente aquí")
        self.id_entry.pack(side="left", padx=8)
        PrimaryBtn(bar, text="Ver horario completo", command=self.ver_horario).pack(side="left", padx=8)
        PrimaryBtn(bar, text="📆 Ver horario de hoy", command=self.ver_hoy).pack(side="left", padx=4)
        PrimaryBtn(bar, text="⚖️ Ver carga académica", command=self.ver_carga).pack(side="left", padx=4)

        self.info_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13), text_color=C_SUCCESS)
        self.info_lbl.pack(anchor="w", padx=20, pady=4)

        self.table = DataTable(self, ["Día", "Inicio", "Fin", "Periodo", "Salón ID", "Grupo ID"], height=400)
        self.table.pack(fill="both", expand=True, padx=20, pady=8)

    def ver_horario(self):
        did = self.id_entry.get().strip()
        if not did:
            messagebox.showwarning("Campo vacío", "Ingrese el ID del docente")
            return
        def load():
            data = api_get(f"/docentes/{did}/horario")
            self.table.clear()
            self.info_lbl.configure(text=f"Horario completo — {len(data) if isinstance(data, list) else 0} clases")
            if isinstance(data, list):
                for a in data:
                    self.table.add_row([a.get("dia","?"), a.get("hora_inicio","?"),
                                        a.get("hora_fin","?"), a.get("periodo","?"),
                                        a.get("salon_id","?")[:8]+"...",
                                        a.get("grupo_id","?")[:8]+"..."])
        threading.Thread(target=load, daemon=True).start()

    def ver_hoy(self):
        did = self.id_entry.get().strip()
        if not did: return
        def load():
            data  = api_get(f"/docentes/{did}/horario/hoy")
            asigs = data.get("asignaciones", []) if isinstance(data, dict) else []
            dia   = data.get("dia", "?") if isinstance(data, dict) else "?"
            self.table.clear()
            self.info_lbl.configure(text=f"Hoy ({dia}) — {len(asigs)} clase(s)")
            for a in asigs:
                self.table.add_row([a.get("dia","?"), a.get("hora_inicio","?"),
                                    a.get("hora_fin","?"), a.get("periodo","?"),
                                    a.get("salon_id","?")[:8]+"...",
                                    a.get("grupo_id","?")[:8]+"..."])
        threading.Thread(target=load, daemon=True).start()

    def ver_carga(self):
        did = self.id_entry.get().strip()
        if not did:
            messagebox.showwarning("Campo vacío", "Ingrese el ID del docente")
            return
        periodo = simpledialog.askstring("Periodo", "Ingrese el periodo (ej. 2026-1):", parent=self)
        if not periodo:
            return
        data = api_get(f"/docentes/{did}/carga", params={"periodo": periodo})
        if isinstance(data, dict) and "error" not in data:
            estado = data.get("estado", "?").upper()
            horas  = data.get("horas_asignadas", 0)
            hmin   = data.get("horas_min", 0)
            hmax   = data.get("horas_max", 0)
            nombre = data.get("nombre_docente", did[:12])
            messagebox.showinfo("Carga Académica",
                                f"Docente: {nombre}\n"
                                f"Periodo: {periodo}\n"
                                f"Horas asignadas: {horas}h\n"
                                f"Rango permitido: {hmin}h – {hmax}h\n"
                                f"Estado: {estado}")
        else:
            messagebox.showerror("Error", f"No se pudo obtener la carga: {data.get('error', data)}")


class GruposPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "👥 Grupos").pack(anchor="w", padx=20, pady=(20, 4))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=8)

        form = Card(top)
        form.pack(side="left", fill="y", padx=(0, 12), ipadx=16, ipady=10)
        ctk.CTkLabel(form, text="Nuevo Grupo", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT).pack(pady=(12, 8))
        self.nombre_var  = StringVar()
        self.periodo_var = StringVar(value="2026-1")
        for lbl, var in [("Nombre del grupo", self.nombre_var), ("Periodo", self.periodo_var)]:
            ctk.CTkLabel(form, text=lbl, text_color=C_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12)
            ctk.CTkEntry(form, textvariable=var, width=220, height=34, fg_color=C_PANEL).pack(padx=12, pady=(2, 8))
        PrimaryBtn(form, text="➕ Crear Grupo", command=self.crear).pack(padx=12, pady=(4, 16), fill="x")

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        PrimaryBtn(right, text="🔄 Actualizar", command=self.cargar, width=120).pack(anchor="e", pady=(0, 6))
        self.table = DataTable(right, ["Nombre", "Periodo", "Estado"], height=340)
        self.table.pack(fill="both", expand=True)
        self.cargar()

    def cargar(self):
        def load():
            data = api_get("/grupos")
            self.table.clear()
            if isinstance(data, list):
                for g in data:
                    gid = g["id"]
                    self.table.add_row([g["nombre"], g["periodo"],
                                        "✅" if g["activo"] else "❌"],
                                       on_delete=lambda i=gid: self.eliminar(i))
        threading.Thread(target=load, daemon=True).start()

    def crear(self):
        data = {"nombre": self.nombre_var.get(), "periodo": self.periodo_var.get()}
        if not data["nombre"]:
            messagebox.showwarning("Campo requerido", "Ingrese el nombre del grupo")
            return
        res = api_post("/grupos", data)
        if "error" in res:
            messagebox.showerror("Error", res["error"])
        else:
            messagebox.showinfo("Éxito", "Grupo creado")
            self.cargar()

    def eliminar(self, gid):
        if messagebox.askyesno("Confirmar", "¿Desactivar este grupo?"):
            api_delete(f"/grupos/{gid}")
            self.cargar()


class ReportesPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        SectionTitle(self, "📄 Reportes PDF").pack(anchor="w", padx=20, pady=(20, 4))
        SubTitle(self, "Genera reportes en PDF descargables desde el sistema").pack(anchor="w", padx=20, pady=(0, 16))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=20)
        grid.columnconfigure((0, 1), weight=1)
        grid.rowconfigure((0, 1), weight=1)

        c1 = Card(grid)
        c1.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c1, text="🗓️ Horario por Docente", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT).pack(pady=(16, 8), padx=16)
        ctk.CTkLabel(c1, text="Genera la grilla semanal de un docente\nen un periodo específico.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED, justify="left").pack(padx=16)
        self.doc_id  = ctk.CTkEntry(c1, placeholder_text="UUID del Docente", height=34, fg_color=C_PANEL)
        self.doc_id.pack(padx=16, pady=(12, 4), fill="x")
        self.doc_per = ctk.CTkEntry(c1, placeholder_text="Periodo (ej. 2026-1)", height=34, fg_color=C_PANEL)
        self.doc_per.pack(padx=16, pady=4, fill="x")
        PrimaryBtn(c1, text="⬇ Descargar PDF", command=self.pdf_docente).pack(padx=16, pady=(8, 16), fill="x")

        c2 = Card(grid)
        c2.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c2, text="⚖️ Carga Académica", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_ACCENT2).pack(pady=(16, 8), padx=16)
        ctk.CTkLabel(c2, text="Resumen de horas asignadas por docente\npara un periodo académico.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED, justify="left").pack(padx=16)
        self.carga_per = ctk.CTkEntry(c2, placeholder_text="Periodo (ej. 2026-1)", height=34, fg_color=C_PANEL)
        self.carga_per.pack(padx=16, pady=(24, 4), fill="x")
        ctk.CTkButton(c2, text="⬇ Descargar PDF", fg_color=C_ACCENT2, hover_color="#6d28d9",
                      font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8, height=36,
                      command=self.pdf_carga).pack(padx=16, pady=(8, 16), fill="x")

        c3 = Card(grid)
        c3.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c3, text="⚠️ Reporte de Conflictos", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_DANGER).pack(pady=(16, 8), padx=16)
        ctk.CTkLabel(c3, text="Lista completa de conflictos detectados\ny resueltos en el sistema.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED, justify="left").pack(padx=16)
        self.conf_per = ctk.CTkEntry(c3, placeholder_text="Periodo (ej. 2026-1)", height=34, fg_color=C_PANEL)
        self.conf_per.pack(padx=16, pady=(12, 4), fill="x")
        ctk.CTkButton(c3, text="⬇ Descargar PDF", fg_color=C_DANGER, hover_color="#b91c1c",
                      font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8, height=36,
                      command=self.pdf_conflictos).pack(padx=16, pady=(8, 16), fill="x")

        c4 = Card(grid)
        c4.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c4, text="🎓 Horario por Programa", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_SUCCESS).pack(pady=(16, 8), padx=16)
        ctk.CTkLabel(c4, text="Horario consolidado de todos los grupos\nde un programa académico.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED, justify="left").pack(padx=16)
        self.prog_id  = ctk.CTkEntry(c4, placeholder_text="UUID del Programa", height=34, fg_color=C_PANEL)
        self.prog_id.pack(padx=16, pady=(12, 4), fill="x")
        self.prog_per = ctk.CTkEntry(c4, placeholder_text="Periodo (ej. 2026-1)", height=34, fg_color=C_PANEL)
        self.prog_per.pack(padx=16, pady=4, fill="x")
        ctk.CTkButton(c4, text="⬇ Descargar PDF", fg_color=C_SUCCESS, hover_color="#047857",
                      font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8, height=36,
                      command=self.pdf_programa).pack(padx=16, pady=(8, 16), fill="x")

        self.status_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color=C_SUCCESS)
        self.status_lbl.pack(pady=8)

    def _descargar(self, url, params, filename):
        self.status_lbl.configure(text="⏳ Generando PDF...", text_color=C_WARN)
        try:
            # Paso 1: Generar el PDF en el servidor (devuelve JSON con id y ruta)
            r = requests.post(url, params=params, timeout=15)
            if r.status_code != 200:
                self.status_lbl.configure(text=f"❌ Error {r.status_code}: {r.text[:80]}", text_color=C_DANGER)
                return
            data = r.json()
            reporte_id = data.get("id")
            if not reporte_id:
                self.status_lbl.configure(text="❌ No se obtuvo ID del reporte", text_color=C_DANGER)
                return

            # Paso 2: Descargar el PDF binario real
            dl = requests.get(f"{BASE_URL}/reportes/{reporte_id}/descargar", timeout=15)
            if dl.status_code != 200:
                self.status_lbl.configure(text=f"❌ Error descargando PDF: {dl.status_code}", text_color=C_DANGER)
                return

            save_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(dl.content)
            self.status_lbl.configure(text=f"✅ PDF guardado en: {save_path}", text_color=C_SUCCESS)
        except Exception as e:
            self.status_lbl.configure(text=f"❌ {e}", text_color=C_DANGER)

    def pdf_docente(self):
        did = self.doc_id.get().strip()
        per = self.doc_per.get().strip()
        if not did or not per:
            messagebox.showwarning("Campos requeridos", "Ingrese ID del docente y periodo")
            return
        threading.Thread(target=self._descargar,
                         args=(f"{BASE_URL}/reportes/horario-docente",
                               {"docente_id": did, "periodo": per},
                               f"horario_docente_{per}.pdf"), daemon=True).start()

    def pdf_carga(self):
        per = self.carga_per.get().strip()
        if not per:
            messagebox.showwarning("Campo requerido", "Ingrese el periodo")
            return
        threading.Thread(target=self._descargar,
                         args=(f"{BASE_URL}/reportes/carga-academica",
                               {"periodo": per},
                               f"carga_academica_{per}.pdf"), daemon=True).start()

    def pdf_conflictos(self):
        per = self.conf_per.get().strip()
        if not per:
            messagebox.showwarning("Campo requerido", "Ingrese el periodo")
            return
        threading.Thread(target=self._descargar,
                         args=(f"{BASE_URL}/reportes/conflictos",
                               {"periodo": per},
                               f"reporte_conflictos_{per}.pdf"), daemon=True).start()

    def pdf_programa(self):
        pid = self.prog_id.get().strip()
        per = self.prog_per.get().strip()
        if not pid or not per:
            messagebox.showwarning("Campos requeridos", "Ingrese ID del programa y periodo")
            return
        threading.Thread(target=self._descargar,
                         args=(f"{BASE_URL}/reportes/horario-programa",
                               {"programa_id": pid, "periodo": per},
                               f"horario_programa_{per}.pdf"), daemon=True).start()


# ─── Main App ─────────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self, usuario: str = None):
        super().__init__()
        self.title("🎓 Sistema de Gestión de Horarios — Universidad NOJA")
        self.geometry("1300x820")
        self.minsize(1100, 720)
        self.configure(fg_color=C_BG)

        # ── Sidebar ──
        sidebar = ctk.CTkFrame(self, width=230, fg_color=C_PANEL, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = ctk.CTkFrame(sidebar, fg_color=C_CARD, corner_radius=0, height=80)
        logo.pack(fill="x")
        ctk.CTkLabel(logo, text="🎓", font=ctk.CTkFont(size=32)).pack(side="left", padx=16, pady=16)
        ctk.CTkLabel(logo, text="Horarios\nAcadémicos",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_TEXT, justify="left").pack(side="left")

        ctk.CTkLabel(sidebar, text="MENÚ PRINCIPAL",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=16, pady=(24, 6))

        nav_items = [
            ("📊  Dashboard",         "dashboard"),
            ("👨‍🏫  Docentes",          "docentes"),
            ("🏫  Salones",            "salones"),
            ("👥  Grupos",             "grupos"),
            ("📅  Asignaciones",       "asignaciones"),
            ("⚠️  Conflictos",        "conflictos"),
            ("🗓️  Horario Docente",    "horario"),
            ("🤖  Chatbot RAG",        "chatbot"),
            ("📷  Escáner Físico",     "camara"),
            ("📄  Reportes PDF",       "reportes"),
        ]

        self.nav_btns = {}
        self.pages    = {}
        self.content  = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        for label, key in nav_items:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                font=ctk.CTkFont(size=13),
                fg_color="transparent", hover_color=C_CARD,
                text_color=C_TEXT, height=42, corner_radius=8,
                command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_btns[key] = btn

        # ── Separador + Botón Telegram ──
        ctk.CTkFrame(sidebar, fg_color=C_CARD, height=1).pack(fill="x", padx=10, pady=(16, 8))

        ctk.CTkButton(
            sidebar,
            text="✈️  Abrir Bot Telegram",
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_TELE,
            hover_color="#1a8cbf",
            text_color="white",
            height=44,
            corner_radius=8,
            command=self._abrir_telegram
        ).pack(fill="x", padx=10, pady=2)

        # ── Banner de bienvenida si entró con reconocimiento facial ──
        if usuario:
            hora = datetime.now().hour
            saludo = "Buenos días" if hora < 12 else ("Buenas tardes" if hora < 18 else "Buenas noches")
            bienvenida = ctk.CTkFrame(sidebar, fg_color="#1a3a1a", corner_radius=8)
            bienvenida.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(bienvenida,
                         text=f"👤 {saludo},",
                         font=ctk.CTkFont(size=10), text_color=C_MUTED).pack(anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(bienvenida,
                         text=usuario,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=C_SUCCESS).pack(anchor="w", padx=10, pady=(0, 6))

        # Status bar API
        self.status = ctk.CTkLabel(sidebar, text="● API: verificando...",
                                    font=ctk.CTkFont(size=11), text_color=C_MUTED)
        self.status.pack(side="bottom", pady=16, padx=12)

        self._page_classes = {
            "dashboard":   DashboardPage,
            "docentes":    DocentesPage,
            "salones":     SalonesPage,
            "grupos":      GruposPage,
            "asignaciones":AsignacionesPage,
            "conflictos":  ConflictosPage,
            "horario":     HorarioDocentePage,
            "chatbot":     ChatbotRAGPage,
            "camara":      CamaraPage,
            "reportes":    ReportesPage,
        }
        self.current_page = None
        self.show_page("dashboard")
        self.check_api_status()

        # Pre-cargar RAG en background al iniciar la app
        threading.Thread(target=_cargar_rag,    daemon=True).start()
        threading.Thread(target=_cargar_config, daemon=True).start()

    def _abrir_telegram(self):
        webbrowser.open(TELEGRAM_BOT_URL)

    def show_page(self, key):
        if self.current_page:
            self.current_page.pack_forget()
        for k, btn in self.nav_btns.items():
            btn.configure(fg_color=C_ACCENT if k == key else "transparent")
        if key not in self.pages:
            self.pages[key] = self._page_classes[key](self.content)
        self.pages[key].pack(fill="both", expand=True)
        self.current_page = self.pages[key]

    def check_api_status(self):
        def check():
            try:
                r = requests.get(f"{BASE_URL.replace('/api/v1','')}/", timeout=3)
                if r.status_code == 200:
                    self.status.configure(text="● API: conectada ✅", text_color=C_SUCCESS)
                else:
                    self.status.configure(text="● API: error ⚠️", text_color=C_WARN)
            except:
                self.status.configure(text="● API: desconectada ❌", text_color=C_DANGER)
            self.after(10000, self.check_api_status)
        threading.Thread(target=check, daemon=True).start()


if __name__ == "__main__":
    # Leer el nombre del usuario pasado por face_login.py (--usuario NOMBRE)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--usuario", default=None,
                        help="Nombre del usuario autenticado por reconocimiento facial")
    args, _ = parser.parse_known_args()

    app = App(usuario=args.usuario)
    app.mainloop()