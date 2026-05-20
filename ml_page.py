"""
ml_page.py
==========
Pantalla de Machine Learning para integrar en app.py del proyecto NOJA.

CÓMO INTEGRAR EN app.py:
  1. Copia ml_horarios.py y ml_page.py a la raíz del proyecto (junto a app.py)
  2. Al inicio de app.py agrega:
       from ml_page import MLPage
  3. En el diccionario _page_classes del App añade:
       "ml": MLPage,
  4. En nav_items añade:
       ("🧠  Machine Learning", "ml"),
"""

import threading
import customtkinter as ctk
from tkinter import messagebox, StringVar

# ── Colores (deben coincidir con los de app.py) ──────────────────────────────
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
C_ML1     = "#0ea5e9"   # azul cielo para Random Forest
C_ML2     = "#8b5cf6"   # violeta para K-Means


# ── Widgets reutilizables ─────────────────────────────────────────────────────
class _Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C_CARD, corner_radius=12, **kw)

class _PBtn(ctk.CTkButton):
    def __init__(self, master, color=C_ACCENT, **kw):
        super().__init__(master, fg_color=color, hover_color="#3b71d4",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         corner_radius=8, height=36, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
class MLPage(ctk.CTkFrame):
    """
    Página principal de Machine Learning.
    Contiene dos pestañas:
      • Random Forest → predicción de conflictos
      • K-Means       → clasificación de carga docente
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        # Título
        ctk.CTkLabel(self, text="🧠 Machine Learning — Análisis de Horarios",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(self, text="Algoritmo 1: Random Forest  |  Algoritmo 2: K-Means Clustering",
                     font=ctk.CTkFont(size=12), text_color=C_MUTED).pack(anchor="w", padx=20, pady=(0, 12))

        # TabView
        self.tabs = ctk.CTkTabview(self, fg_color=C_PANEL, corner_radius=12,
                                   segmented_button_fg_color=C_CARD,
                                   segmented_button_selected_color=C_ML1,
                                   segmented_button_selected_hover_color="#0284c7",
                                   text_color=C_TEXT)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.tabs.add("🌲 Random Forest — Predicción de Conflictos")
        self.tabs.add("🔵 K-Means — Clasificación de Carga Docente")

        self._build_rf_tab(self.tabs.tab("🌲 Random Forest — Predicción de Conflictos"))
        self._build_km_tab(self.tabs.tab("🔵 K-Means — Clasificación de Carga Docente"))

        # Estado global ML
        self.rf_modelo  = None
        self.km_modelo  = None
        self.rf_listo   = False
        self.km_listo   = False

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 — RANDOM FOREST
    # ══════════════════════════════════════════════════════════════════════════
    def _build_rf_tab(self, tab):
        tab.columnconfigure((0, 1), weight=1)
        tab.rowconfigure(1, weight=1)

        # ── Descripción ──
        desc = _Card(tab)
        desc.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 6))
        ctk.CTkLabel(desc,
                     text="🌲 Random Forest Classifier",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=C_ML1).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(desc,
                     text="Aprende de las asignaciones históricas y predice si una NUEVA asignación "
                          "generará conflicto antes de crearla. Usa 150 árboles de decisión.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED,
                     wraplength=900, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        # ── Panel izquierdo: Entrenar ──
        left = _Card(tab)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=4)

        ctk.CTkLabel(left, text="① Entrenar el modelo",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_ML1).pack(anchor="w", padx=14, pady=(14, 6))

        ctk.CTkLabel(left,
                     text="El modelo se entrena con datos reales de tu BD\n"
                          "más datos sintéticos para mayor variedad.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED,
                     justify="left").pack(anchor="w", padx=14)

        self.rf_btn_train = _PBtn(left, text="🚀 Entrenar Random Forest",
                                   color=C_ML1, command=self._rf_entrenar)
        self.rf_btn_train.pack(padx=14, pady=(12, 6), fill="x")

        self.rf_status = ctk.CTkLabel(left, text="Estado: sin entrenar",
                                       font=ctk.CTkFont(size=11), text_color=C_MUTED)
        self.rf_status.pack(anchor="w", padx=14)

        # Métricas
        ctk.CTkLabel(left, text="📊 Métricas del modelo:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=14, pady=(16, 4))

        self.rf_metricas = ctk.CTkTextbox(left, fg_color=C_BG, text_color=C_TEXT,
                                           font=ctk.CTkFont(size=11, family="Courier"),
                                           height=200, wrap="word")
        self.rf_metricas.pack(fill="x", padx=14, pady=(0, 14))
        self.rf_metricas.insert("1.0", "Entrena el modelo para ver las métricas aquí.")
        self.rf_metricas.configure(state="disabled")

        # ── Panel derecho: Predecir ──
        right = _Card(tab)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=4)

        ctk.CTkLabel(right, text="② Predecir conflicto en nueva asignación",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_ML1).pack(anchor="w", padx=14, pady=(14, 6))

        # Campos de entrada
        self.rf_docente = StringVar()
        self.rf_grupo   = StringVar()
        self.rf_salon   = StringVar()
        self.rf_dia     = StringVar(value="lunes")
        self.rf_hi      = StringVar(value="08:00")
        self.rf_hf      = StringVar(value="10:00")

        campos = [
            ("ID / Nombre Docente", self.rf_docente),
            ("ID / Nombre Grupo",   self.rf_grupo),
            ("ID / Nombre Salón",   self.rf_salon),
            ("Hora inicio",         self.rf_hi),
            ("Hora fin",            self.rf_hf),
        ]
        for lbl, var in campos:
            ctk.CTkLabel(right, text=lbl, font=ctk.CTkFont(size=11),
                         text_color=C_MUTED).pack(anchor="w", padx=14, pady=(6, 0))
            ctk.CTkEntry(right, textvariable=var, height=32,
                         fg_color=C_PANEL).pack(fill="x", padx=14, pady=(2, 0))

        ctk.CTkLabel(right, text="Día", font=ctk.CTkFont(size=11),
                     text_color=C_MUTED).pack(anchor="w", padx=14, pady=(6, 0))
        ctk.CTkOptionMenu(right,
                          values=["lunes","martes","miércoles","jueves","viernes","sábado"],
                          variable=self.rf_dia,
                          fg_color=C_PANEL).pack(fill="x", padx=14, pady=(2, 8))

        _PBtn(right, text="🔮 Predecir", color=C_ML1,
              command=self._rf_predecir).pack(padx=14, pady=(4, 8), fill="x")

        # Resultado — textbox con scroll para que nunca quede cortado
        ctk.CTkLabel(right, text="Resultado:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=14)
        self.rf_resultado_box = ctk.CTkTextbox(
            right, fg_color=C_BG, text_color=C_TEXT,
            font=ctk.CTkFont(size=13), wrap="word",
            height=110)
        self.rf_resultado_box.pack(fill="both", expand=True, padx=14, pady=(2, 14))
        self.rf_resultado_box.insert("1.0", "Completa los campos y presiona Predecir.")
        self.rf_resultado_box.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 — K-MEANS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_km_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        # ── Descripción ──
        desc = _Card(tab)
        desc.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 6))
        ctk.CTkLabel(desc, text="🔵 K-Means Clustering — Carga Académica Docente",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=C_ML2).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(desc,
                     text="Agrupa automáticamente a los docentes en 3 categorías según su carga horaria: "
                          "Subcargado / Normal / Sobrecargado. Usa K=3 centroides.",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED,
                     wraplength=900, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        # ── Controles ──
        ctrl = _Card(tab)
        ctrl.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        ctrl_inner = ctk.CTkFrame(ctrl, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=14, pady=12)

        _PBtn(ctrl_inner, text="🚀 Ejecutar K-Means", color=C_ML2,
              command=self._km_analizar, width=200).pack(side="left", padx=(0, 12))

        self.km_status = ctk.CTkLabel(ctrl_inner, text="Estado: sin ejecutar",
                                       font=ctk.CTkFont(size=11), text_color=C_MUTED)
        self.km_status.pack(side="left")

        # Buscar docente individual
        ctk.CTkLabel(ctrl_inner, text="  |  Buscar docente:",
                     font=ctk.CTkFont(size=11), text_color=C_MUTED).pack(side="left", padx=(20, 4))
        self.km_buscar_var = StringVar()
        ctk.CTkEntry(ctrl_inner, textvariable=self.km_buscar_var,
                     placeholder_text="Nombre del docente",
                     width=200, height=32, fg_color=C_PANEL).pack(side="left", padx=4)
        _PBtn(ctrl_inner, text="Buscar", color=C_ACCENT2, width=80,
              command=self._km_buscar_docente).pack(side="left", padx=4)

        # ── Tabla de resultados ──
        tabla_frame = _Card(tab)
        tabla_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Encabezado tabla
        hdr = ctk.CTkFrame(tabla_frame, fg_color="#1e2235", corner_radius=6)
        hdr.pack(fill="x", padx=8, pady=(8, 2))
        for i, col in enumerate(["Docente", "Clases/semana", "Horas/semana", "Días activos", "Categoría"]):
            ctk.CTkLabel(hdr, text=col,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=C_ML2).grid(row=0, column=i, padx=12, pady=6, sticky="w")
            hdr.columnconfigure(i, weight=1)

        self.km_scroll = ctk.CTkScrollableFrame(tabla_frame, fg_color="transparent", height=340)
        self.km_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.km_info = ctk.CTkLabel(tabla_frame,
                                     text="Ejecuta K-Means para ver la clasificación de docentes.",
                                     font=ctk.CTkFont(size=12), text_color=C_MUTED)
        self.km_info.pack(pady=8)

    # ══════════════════════════════════════════════════════════════════════════
    # HANDLERS — Random Forest
    # ══════════════════════════════════════════════════════════════════════════
    def _rf_entrenar(self):
        self.rf_btn_train.configure(state="disabled", text="⏳ Entrenando...")
        self.rf_status.configure(text="Entrenando modelo...", text_color=C_WARN)

        def run():
            try:
                from ml_horarios import obtener_predictor
                self.rf_modelo = obtener_predictor()
                metricas = self.rf_modelo.entrenar()
                self.rf_listo = True

                texto = (
                    f"✅ Entrenamiento exitoso\n"
                    f"{'─'*38}\n"
                    f"Accuracy:    {metricas['accuracy']*100:.2f}%\n"
                    f"Muestras:    {metricas['n_muestras']}\n"
                    f"Conflictos:  {metricas['n_conflictos']}\n\n"
                    f"Importancia de características:\n"
                )
                for feat, imp in metricas["importancias"].items():
                    barra = "█" * int(imp * 30)
                    texto += f"  {feat[:18]:<18} {barra} {imp:.3f}\n"

                self._set_textbox(self.rf_metricas, texto)
                self.rf_status.configure(text=f"✅ Modelo listo — Accuracy: {metricas['accuracy']*100:.1f}%",
                                          text_color=C_SUCCESS)
            except Exception as e:
                self.rf_status.configure(text=f"❌ Error: {str(e)[:60]}", text_color=C_DANGER)
                self._set_textbox(self.rf_metricas, f"Error durante el entrenamiento:\n{e}")
            finally:
                self.rf_btn_train.configure(state="normal", text="🚀 Entrenar Random Forest")

        threading.Thread(target=run, daemon=True).start()

    def _rf_predecir(self):
        if not self.rf_listo or self.rf_modelo is None:
            messagebox.showwarning("Modelo no entrenado",
                                   "Primero entrena el modelo presionando '🚀 Entrenar Random Forest'")
            return

        doc = self.rf_docente.get().strip() or "docente_nuevo"
        grp = self.rf_grupo.get().strip()   or "grupo_nuevo"
        sal = self.rf_salon.get().strip()   or "salon_nuevo"
        dia = self.rf_dia.get()
        hi  = self.rf_hi.get().strip()
        hf  = self.rf_hf.get().strip()

        try:
            res = self.rf_modelo.predecir(doc, grp, sal, dia, hi, hf)
            if "error" in res:
                self._set_textbox(self.rf_resultado_box, f"❌ {res['error']}")
                return

            texto = (
                f"{res['mensaje']}\n\n"
                f"Nivel de riesgo:  {res['riesgo']}\n"
                f"Probabilidad:     {res['porcentaje']}"
            )
            self.rf_resultado_box.configure(state="normal")
            self.rf_resultado_box.delete("1.0", "end")
            color = C_DANGER if res["conflicto"] else C_SUCCESS
            self.rf_resultado_box.configure(text_color=color)
            self.rf_resultado_box.insert("1.0", texto)
            self.rf_resultado_box.configure(state="disabled")

        except Exception as e:
            self._set_textbox(self.rf_resultado_box, f"❌ Error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # HANDLERS — K-Means
    # ══════════════════════════════════════════════════════════════════════════
    def _km_analizar(self):
        self.km_status.configure(text="⏳ Ejecutando K-Means...", text_color=C_WARN)
        for w in self.km_scroll.winfo_children():
            w.destroy()

        def run():
            try:
                from ml_horarios import obtener_clasificador
                import requests

                self.km_modelo = obtener_clasificador()
                resultado = self.km_modelo.analizar()
                self.km_listo = True

                # Resolver nombres desde la API
                try:
                    resp = requests.get("http://localhost:8000/api/v1/docentes", timeout=3)
                    docentes_api = {d["id"]: d["nombre"] for d in resp.json()} if resp.ok else {}
                except Exception:
                    docentes_api = {}

                # Guardar tabla con nombres para el buscador
                self._km_tabla_datos = resultado["tabla"]
                self._km_docentes_nombres = docentes_api

                self._km_pintar_tabla(resultado["tabla"], docentes_api)

                # Resumen
                resumen_txt = "  ".join(
                    f"{cat}: {datos['n_docentes']} docentes ({datos['horas_promedio']} h/sem)"
                    for cat, datos in resultado["grupos"].items()
                )
                self.km_info.configure(
                    text=f"Total: {resultado['total_docentes']} docentes  |  {resumen_txt}",
                    text_color=C_SUCCESS
                )
                self.km_status.configure(text="✅ K-Means ejecutado correctamente",
                                          text_color=C_SUCCESS)

            except Exception as e:
                self.km_status.configure(text=f"❌ Error: {str(e)[:60]}", text_color=C_DANGER)

        threading.Thread(target=run, daemon=True).start()

    def _km_pintar_tabla(self, tabla, docentes_api):
        """Pinta las filas de la tabla K-Means resolviendo nombres."""
        for w in self.km_scroll.winfo_children():
            w.destroy()

        COLOR_CAT = {
            "🔵 Subcargado":   "#0ea5e9",
            "🟢 Normal":       "#10b981",
            "🔴 Sobrecargado": "#ef4444",
        }
        for reg in tabla:
            cat   = reg["categoria"]
            color = COLOR_CAT.get(cat, C_TEXT)
            nombre = docentes_api.get(reg["docente_id"], reg["docente_id"][:22])
            row   = ctk.CTkFrame(self.km_scroll, fg_color=C_PANEL, corner_radius=6)
            row.pack(fill="x", padx=4, pady=2)
            valores = [
                nombre,
                str(reg["total_clases"]),
                f"{reg['horas_semana']:.1f} h",
                str(reg["dias_distintos"]),
                cat,
            ]
            for i, v in enumerate(valores):
                ctk.CTkLabel(row, text=v,
                             font=ctk.CTkFont(size=11,
                                              weight="bold" if i == 4 else "normal"),
                             text_color=color if i == 4 else C_TEXT,
                             anchor="w").grid(row=0, column=i, padx=12, pady=6, sticky="w")
                row.columnconfigure(i, weight=1)

    def _km_buscar_docente(self):
        if not self.km_listo or self.km_modelo is None:
            messagebox.showwarning("Sin datos", "Ejecuta K-Means primero.")
            return
        query = self.km_buscar_var.get().strip().lower()
        if not query:
            # Si está vacío, mostrar todos
            self._km_pintar_tabla(self._km_tabla_datos, self._km_docentes_nombres)
            return

        # Filtrar por nombre (o por ID si no hay nombres)
        nombres = getattr(self, "_km_docentes_nombres", {})
        tabla   = getattr(self, "_km_tabla_datos", [])

        filtrados = [
            reg for reg in tabla
            if query in nombres.get(reg["docente_id"], reg["docente_id"]).lower()
        ]

        if not filtrados:
            messagebox.showinfo("Sin resultados",
                                f"No se encontró ningún docente con '{self.km_buscar_var.get()}'.\n"
                                "Prueba con parte del nombre, ej: 'Carlos', 'Ramírez', 'Dr.'")
            return

        self._km_pintar_tabla(filtrados, nombres)

    # ── Utilidad ──────────────────────────────────────────────────────────────
    @staticmethod
    def _set_textbox(tb: ctk.CTkTextbox, texto: str):
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.insert("1.0", texto)
        tb.configure(state="disabled")