"""
ml_horarios.py
==============
Módulo de Machine Learning para el Sistema de Gestión de Horarios.

Algoritmo 1 — Random Forest Classifier
  Predice si una nueva asignación generará conflicto ANTES de crearla.
  Dataset: generado automáticamente desde la base de datos SQLite.

Algoritmo 2 — K-Means Clustering
  Agrupa docentes según su carga académica en 3 categorías:
  Subcargado / Normal / Sobrecargado.
  Dataset: generado automáticamente desde la base de datos SQLite.
"""

import os
import sqlite3
import random
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# ── Ruta a la base de datos (ajusta si cambia) ──────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "horarios.db")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
DIA_NUM = {d: i for i, d in enumerate(DIAS)}

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE DATASET
# ═══════════════════════════════════════════════════════════════════════════════

def _hora_a_minutos(hora: str) -> int:
    """Convierte 'HH:MM' a minutos desde medianoche."""
    try:
        h, m = hora.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _hay_solapamiento(hi1, hf1, hi2, hf2) -> bool:
    return _hora_a_minutos(hi1) < _hora_a_minutos(hf2) and \
           _hora_a_minutos(hi2) < _hora_a_minutos(hf1)


def _cargar_asignaciones_db() -> list[dict]:
    """Lee las asignaciones reales de la BD SQLite."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("""
            SELECT docente_id, grupo_id, salon_id, dia, hora_inicio, hora_fin, periodo
            FROM asignaciones
        """)
        rows = cur.fetchall()
        con.close()
        cols = ["docente_id", "grupo_id", "salon_id", "dia", "hora_inicio", "hora_fin", "periodo"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        print(f"[ML] Error leyendo BD: {e}")
        return []


def _generar_dataset_sintetico(n: int = 500) -> pd.DataFrame:
    """
    Genera un dataset sintético realista de asignaciones de horarios
    para entrenar los modelos cuando la BD tiene pocos datos reales.
    """
    docentes  = [f"doc_{i:03d}" for i in range(1, 16)]
    grupos    = [f"grp_{i:03d}" for i in range(1, 12)]
    salones   = [f"sal_{i:03d}" for i in range(1, 8)]
    horas     = [("06:00","08:00"),("08:00","10:00"),("10:00","12:00"),
                 ("12:00","14:00"),("14:00","16:00"),("16:00","18:00"),
                 ("18:00","20:00"),("20:00","22:00")]
    periodos  = ["2025-1", "2025-2", "2026-1"]

    registros = []
    for _ in range(n):
        doc = random.choice(docentes)
        grp = random.choice(grupos)
        sal = random.choice(salones)
        dia = random.choice(DIAS)
        hi, hf = random.choice(horas)
        per = random.choice(periodos)
        registros.append({
            "docente_id": doc, "grupo_id": grp, "salon_id": sal,
            "dia": dia, "hora_inicio": hi, "hora_fin": hf, "periodo": per
        })
    return pd.DataFrame(registros)


def _etiquetar_conflictos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega columna 'conflicto' (1=sí, 0=no) revisando solapamientos
    de docente, salón o grupo en el mismo día.
    """
    df = df.copy().reset_index(drop=True)
    conflicto = [0] * len(df)

    for i in range(len(df)):
        for j in range(len(df)):
            if i == j:
                continue
            if df.at[i, "dia"] != df.at[j, "dia"]:
                continue
            if df.at[i, "periodo"] != df.at[j, "periodo"]:
                continue
            if not _hay_solapamiento(df.at[i, "hora_inicio"], df.at[i, "hora_fin"],
                                     df.at[j, "hora_inicio"], df.at[j, "hora_fin"]):
                continue
            # Hay solapamiento + (mismo docente, salón o grupo)
            if (df.at[i, "docente_id"] == df.at[j, "docente_id"] or
                    df.at[i, "salon_id"]   == df.at[j, "salon_id"]   or
                    df.at[i, "grupo_id"]   == df.at[j, "grupo_id"]):
                conflicto[i] = 1
                break

    df["conflicto"] = conflicto
    return df


def _construir_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Convierte el DataFrame en features numéricas para sklearn.
    Retorna X, y y los encoders usados.
    """
    le_doc  = LabelEncoder().fit(df["docente_id"])
    le_grp  = LabelEncoder().fit(df["grupo_id"])
    le_sal  = LabelEncoder().fit(df["salon_id"])

    X = np.column_stack([
        le_doc.transform(df["docente_id"]),
        le_grp.transform(df["grupo_id"]),
        le_sal.transform(df["salon_id"]),
        df["dia"].map(lambda d: DIA_NUM.get(d, -1)),
        df["hora_inicio"].map(_hora_a_minutos),
        df["hora_fin"].map(_hora_a_minutos),
        df["hora_fin"].map(_hora_a_minutos) - df["hora_inicio"].map(_hora_a_minutos),  # duración
    ])
    y = df["conflicto"].values

    encoders = {"doc": le_doc, "grp": le_grp, "sal": le_sal}
    return X, y, encoders


# ═══════════════════════════════════════════════════════════════════════════════
# ALGORITMO 1 — RANDOM FOREST: Predicción de Conflictos
# ═══════════════════════════════════════════════════════════════════════════════

class PredictorConflictos:
    """
    Predice si una nueva asignación generará conflicto.

    Uso:
        modelo = PredictorConflictos()
        modelo.entrenar()
        resultado = modelo.predecir(docente_id, grupo_id, salon_id,
                                    dia, hora_inicio, hora_fin)
    """

    def __init__(self):
        self.modelo: RandomForestClassifier | None = None
        self.encoders: dict = {}
        self.entrenado = False
        self.accuracy = 0.0
        self.n_muestras = 0
        self.n_conflictos = 0

    # ── Entrenamiento ──────────────────────────────────────────────────────────
    def entrenar(self) -> dict:
        """
        Carga datos reales de la BD + datos sintéticos,
        etiqueta conflictos y entrena el Random Forest.
        Retorna métricas del entrenamiento.
        """
        print("[RF] Cargando datos reales de la BD...")
        reales = _cargar_asignaciones_db()
        df_real = pd.DataFrame(reales) if reales else pd.DataFrame()

        print(f"[RF] {len(df_real)} asignaciones reales encontradas")

        # Completar con sintéticos para garantizar suficiente variedad
        n_sintetico = max(400, 600 - len(df_real))
        df_sint = _generar_dataset_sintetico(n_sintetico)

        if not df_real.empty:
            df = pd.concat([df_real, df_sint], ignore_index=True)
        else:
            df = df_sint

        print(f"[RF] Dataset total: {len(df)} registros")

        # Etiquetar
        df = _etiquetar_conflictos(df)
        self.n_muestras   = len(df)
        self.n_conflictos = int(df["conflicto"].sum())

        print(f"[RF] Conflictos en dataset: {self.n_conflictos} ({self.n_conflictos/self.n_muestras*100:.1f}%)")

        X, y, self.encoders = _construir_features(df)

        # Split entrenamiento / prueba
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y if self.n_conflictos > 10 else None
        )

        # Entrenar
        self.modelo = RandomForestClassifier(
            n_estimators=150,
            max_depth=10,
            min_samples_split=4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        self.modelo.fit(X_train, y_train)

        # Evaluar
        y_pred = self.modelo.predict(X_test)
        self.accuracy = accuracy_score(y_test, y_pred)
        reporte = classification_report(y_test, y_pred,
                                        target_names=["Sin conflicto", "Con conflicto"],
                                        zero_division=0)
        self.entrenado = True

        print(f"[RF] Accuracy: {self.accuracy:.2%}")
        print(f"[RF] Reporte:\n{reporte}")

        # Importancia de características
        nombres = ["docente_enc", "grupo_enc", "salon_enc", "dia_num",
                   "hora_inicio_min", "hora_fin_min", "duracion_min"]
        importancias = dict(zip(nombres, self.modelo.feature_importances_))

        return {
            "accuracy": round(self.accuracy, 4),
            "n_muestras": self.n_muestras,
            "n_conflictos": self.n_conflictos,
            "importancias": {k: round(float(v), 4) for k, v in
                             sorted(importancias.items(), key=lambda x: -x[1])},
            "reporte": reporte,
        }

    # ── Predicción ─────────────────────────────────────────────────────────────
    def predecir(self, docente_id: str, grupo_id: str, salon_id: str,
                 dia: str, hora_inicio: str, hora_fin: str) -> dict:
        """
        Predice si la asignación dada generará conflicto.
        Retorna: { 'conflicto': bool, 'probabilidad': float, 'riesgo': str }
        """
        if not self.entrenado or self.modelo is None:
            return {"error": "Modelo no entrenado. Llama a entrenar() primero."}

        # Encode (manejo de categorías nuevas)
        def _enc(le: LabelEncoder, val: str) -> int:
            if val in le.classes_:
                return int(le.transform([val])[0])
            return len(le.classes_)   # categoría desconocida → fuera del rango

        doc_enc = _enc(self.encoders["doc"], docente_id)
        grp_enc = _enc(self.encoders["grp"], grupo_id)
        sal_enc = _enc(self.encoders["sal"], salon_id)
        dia_num = DIA_NUM.get(dia, -1)
        hi_min  = _hora_a_minutos(hora_inicio)
        hf_min  = _hora_a_minutos(hora_fin)
        dur     = hf_min - hi_min

        X = np.array([[doc_enc, grp_enc, sal_enc, dia_num, hi_min, hf_min, dur]])
        pred  = int(self.modelo.predict(X)[0])
        proba = float(self.modelo.predict_proba(X)[0][1])

        if proba < 0.30:
            riesgo = "🟢 Bajo"
        elif proba < 0.65:
            riesgo = "🟡 Medio"
        else:
            riesgo = "🔴 Alto"

        return {
            "conflicto":    bool(pred),
            "probabilidad": round(proba, 4),
            "porcentaje":   f"{proba*100:.1f}%",
            "riesgo":       riesgo,
            "mensaje": (
                f"⚠️ PROBABLE CONFLICTO ({proba*100:.1f}% de probabilidad)"
                if pred else
                f"✅ Sin conflicto previsto ({proba*100:.1f}% de riesgo)"
            )
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ALGORITMO 2 — K-MEANS: Clasificación de Carga Docente
# ═══════════════════════════════════════════════════════════════════════════════

class ClasificadorCargaDocente:
    """
    Agrupa docentes en 3 clusters según su carga horaria:
      • Cluster 0 → Subcargado
      • Cluster 1 → Normal
      • Cluster 2 → Sobrecargado

    Uso:
        clf = ClasificadorCargaDocente()
        resultado = clf.analizar()   # devuelve DataFrame con cluster por docente
        clf.predecir_docente(docente_id)
    """

    def __init__(self):
        self.modelo: KMeans | None = None
        self.scaler = StandardScaler()
        self.df_resultado: pd.DataFrame | None = None
        self.entrenado = False
        self.etiquetas_cluster: dict[int, str] = {}

    # ── Construcción del dataset de carga ─────────────────────────────────────
    def _construir_dataset_carga(self) -> pd.DataFrame:
        """
        Calcula métricas de carga por docente desde la BD.
        Si hay pocos docentes reales, agrega sintéticos.
        """
        reales = _cargar_asignaciones_db()

        if reales:
            df = pd.DataFrame(reales)
            df["duracion"] = df.apply(
                lambda r: _hora_a_minutos(r["hora_fin"]) - _hora_a_minutos(r["hora_inicio"]),
                axis=1
            )
            resumen = df.groupby("docente_id").agg(
                total_clases=("docente_id", "count"),
                horas_semana=("duracion", lambda x: x.sum() / 60),
                dias_distintos=("dia", "nunique"),
            ).reset_index()
        else:
            resumen = pd.DataFrame(columns=["docente_id","total_clases","horas_semana","dias_distintos"])

        # Completar con sintéticos si hay menos de 9 docentes
        if len(resumen) < 9:
            sint_rows = []
            for i in range(1, 20):
                did = f"doc_sint_{i:03d}"
                clases     = random.randint(1, 14)
                horas      = round(clases * random.uniform(1.5, 2.5), 1)
                dias       = min(clases, random.randint(1, 5))
                sint_rows.append({
                    "docente_id": did,
                    "total_clases": clases,
                    "horas_semana": horas,
                    "dias_distintos": dias,
                })
            resumen = pd.concat([resumen, pd.DataFrame(sint_rows)], ignore_index=True)

        return resumen

    # ── Entrenamiento / Análisis ───────────────────────────────────────────────
    def analizar(self) -> dict:
        """
        Carga datos, aplica K-Means con k=3 y retorna el análisis completo.
        """
        print("[KM] Construyendo dataset de carga docente...")
        df = self._construir_dataset_carga()

        features = ["total_clases", "horas_semana", "dias_distintos"]
        X = df[features].values.astype(float)
        X_scaled = self.scaler.fit_transform(X)

        print(f"[KM] Entrenando K-Means con {len(df)} docentes...")
        self.modelo = KMeans(n_clusters=3, random_state=42, n_init=20)
        clusters = self.modelo.fit_predict(X_scaled)
        df["cluster"] = clusters

        # Determinar etiquetas por centroide (horas_semana)
        centros = self.modelo.cluster_centers_
        # Desescalar para interpretar
        centros_orig = self.scaler.inverse_transform(centros)
        horas_por_cluster = {i: centros_orig[i][1] for i in range(3)}

        orden = sorted(horas_por_cluster, key=lambda k: horas_por_cluster[k])
        etiqueta_map = {
            orden[0]: "🔵 Subcargado",
            orden[1]: "🟢 Normal",
            orden[2]: "🔴 Sobrecargado",
        }
        self.etiquetas_cluster = etiqueta_map
        df["categoria"] = df["cluster"].map(etiqueta_map)

        self.df_resultado = df
        self.entrenado = True

        # Resumen por grupo
        resumen_grupos = {}
        for c, lbl in etiqueta_map.items():
            grupo_df = df[df["cluster"] == c]
            resumen_grupos[lbl] = {
                "n_docentes":      int(len(grupo_df)),
                "horas_promedio":  round(float(grupo_df["horas_semana"].mean()), 1),
                "clases_promedio": round(float(grupo_df["total_clases"].mean()), 1),
                "docentes":        grupo_df["docente_id"].tolist(),
            }

        print(f"[KM] Análisis completo: {resumen_grupos}")
        return {
            "total_docentes": len(df),
            "grupos": resumen_grupos,
            "inercia": round(float(self.modelo.inertia_), 2),
            "tabla": df[["docente_id","total_clases","horas_semana",
                         "dias_distintos","categoria"]].to_dict(orient="records"),
        }

    # ── Predicción individual ──────────────────────────────────────────────────
    def predecir_docente(self, docente_id: str) -> dict:
        """Devuelve la categoría de carga de un docente específico."""
        if not self.entrenado or self.df_resultado is None:
            return {"error": "Modelo no entrenado. Llama a analizar() primero."}

        fila = self.df_resultado[self.df_resultado["docente_id"] == docente_id]
        if fila.empty:
            return {"error": f"Docente '{docente_id}' no encontrado en el dataset."}

        row = fila.iloc[0]
        return {
            "docente_id":    docente_id,
            "total_clases":  int(row["total_clases"]),
            "horas_semana":  round(float(row["horas_semana"]), 1),
            "dias_distintos":int(row["dias_distintos"]),
            "categoria":     row["categoria"],
            "cluster":       int(row["cluster"]),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCIAS GLOBALES (singleton por sesión)
# ═══════════════════════════════════════════════════════════════════════════════
_predictor_conflictos: PredictorConflictos | None = None
_clasificador_carga: ClasificadorCargaDocente | None = None


def obtener_predictor() -> PredictorConflictos:
    global _predictor_conflictos
    if _predictor_conflictos is None:
        _predictor_conflictos = PredictorConflictos()
    return _predictor_conflictos


def obtener_clasificador() -> ClasificadorCargaDocente:
    global _clasificador_carga
    if _clasificador_carga is None:
        _clasificador_carga = ClasificadorCargaDocente()
    return _clasificador_carga


# ═══════════════════════════════════════════════════════════════════════════════
# TEST RÁPIDO (ejecutar directo: python ml_horarios.py)
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST — Algoritmo 1: Random Forest (Predicción de conflictos)")
    print("=" * 60)
    rf = PredictorConflictos()
    metricas = rf.entrenar()
    print(f"\n  Accuracy: {metricas['accuracy']*100:.2f}%")
    print(f"  Muestras: {metricas['n_muestras']}  |  Conflictos: {metricas['n_conflictos']}")
    print("\n  Importancia de características:")
    for feat, imp in metricas["importancias"].items():
        print(f"    {feat}: {imp:.4f}")

    print("\n  Predicción de ejemplo:")
    res = rf.predecir("doc_001","grp_001","sal_001","lunes","08:00","10:00")
    print(f"    {res['mensaje']}  |  Riesgo: {res['riesgo']}")

    print("\n" + "=" * 60)
    print("  TEST — Algoritmo 2: K-Means (Clasificación de carga docente)")
    print("=" * 60)
    km = ClasificadorCargaDocente()
    resultado = km.analizar()
    print(f"\n  Total docentes analizados: {resultado['total_docentes']}")
    print(f"  Inercia del modelo: {resultado['inercia']}")
    for cat, datos in resultado["grupos"].items():
        print(f"\n  {cat}:")
        print(f"    Docentes: {datos['n_docentes']}")
        print(f"    Horas promedio/semana: {datos['horas_promedio']}")
        print(f"    Clases promedio: {datos['clases_promedio']}")
    print("\n✅ Tests completados correctamente")