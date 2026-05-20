# -*- coding: utf-8 -*-
"""
face_login.py
Ubicacion: NOJA_BOT/core/face_login.py
Al reconocer exitosamente lanza app.py (raiz del proyecto).
"""
import sys
import io
import os

# Fix encoding en Windows ANTES de cualquier otro import
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

import cv2
import numpy as np
import pickle
import subprocess
from datetime import datetime
from ultralytics import YOLO
from deepface import DeepFace

# ── Rutas ─────────────────────────────────────────────────────────────────────
# face_login.py vive en NOJA_BOT/core/  ->  ROOT = NOJA_BOT/
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_PATH = os.path.join(ROOT_DIR, "app.py")

ROSTROS_DIR     = os.path.join(ROOT_DIR, "assets", "rostros_guardados")
ROSTROS_DB      = os.path.join(ROOT_DIR, "data",   "rostros_db.pkl")
YOLO_PT         = os.path.join(ROOT_DIR, "yolov8n.pt")
MODELO_DEEPFACE = "Facenet"
UMBRAL          = 0.6

os.makedirs(ROSTROS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(ROSTROS_DB), exist_ok=True)

# ── Colores BGR ───────────────────────────────────────────────────────────────
VERDE       = (0, 200, 100)
VERDE_CLARO = (0, 255, 150)
BLANCO      = (255, 255, 255)
GRIS        = (180, 180, 180)
ROJO        = (60,  60,  220)
AMARILLO    = (0,  210,  255)
FONDO       = (25,  25,   25)
ACENTO      = (0,  180,   90)
ACENTO2     = (30, 140,  220)

# ── Base de datos ─────────────────────────────────────────────────────────────
def cargar_db():
    if os.path.exists(ROSTROS_DB):
        with open(ROSTROS_DB, "rb") as f:
            return pickle.load(f)
    return {}

def guardar_db(db):
    with open(ROSTROS_DB, "wb") as f:
        pickle.dump(db, f)

def rostros_registrados():
    return list(cargar_db().keys())

# ── YOLO ──────────────────────────────────────────────────────────────────────
def cargar_yolo():
    pt = YOLO_PT if os.path.exists(YOLO_PT) else "yolov8n.pt"
    return YOLO(pt)

def detectar_rostro(model, frame):
    resultados = model(frame, verbose=False)
    mejor_box  = None
    mejor_area = 0
    for r in resultados:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            area = (x2-x1)*(y2-y1)
            if area > mejor_area:
                mejor_area = area
                mejor_box  = (x1, y1, x2, y2)
    if mejor_box:
        x1, y1, x2, y2 = mejor_box
        m  = 30
        fh, fw = frame.shape[:2]
        recorte = frame[max(0,y1-m):min(fh,y2+m), max(0,x1-m):min(fw,x2+m)]
        return recorte, mejor_box
    return None, None

# ── Helpers dibujo ────────────────────────────────────────────────────────────
def t(img, msg, x, y, sc=0.6, col=BLANCO, gr=1):
    cv2.putText(img, msg, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, col, gr, cv2.LINE_AA)

def barra_top(img, titulo):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (w, 62), (15,15,15), -1)
    cv2.rectangle(img, (0, 60),(w, 62), ACENTO, -1)
    t(img, "Sistema NOJA", 20, 22, 0.48, ACENTO)
    t(img, titulo,         20, 48, 0.60, BLANCO)

def barra_bot(img, msg, color=GRIS):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, h-34),(w, h), (15,15,15), -1)
    t(img, msg, 14, h-11, 0.43, color)

def dibujar_btn(img, x, y, w, h, label, sub="", hover=False, col=ACENTO):
    bg    = (35,55,35) if hover else (35,35,35)
    borde = col        if hover else (75,75,75)
    cv2.rectangle(img, (x,y),   (x+w, y+h), bg,    -1)
    cv2.rectangle(img, (x,y),   (x+w, y+h), borde,  1)
    cy = y + h//2
    if sub:
        t(img, label, x+14, cy-7,  0.58, VERDE_CLARO if hover else BLANCO)
        t(img, sub,   x+14, cy+13, 0.42, GRIS)
    else:
        t(img, label, x+14, cy+6,  0.58, VERDE_CLARO if hover else BLANCO)

# ── Crear ventana sin ventana fantasma en Windows ─────────────────────────────
def crear_ventana(nombre, w, h):
    """
    Usa WINDOW_AUTOSIZE para evitar la ventana fantasma blanca que
    aparece con WINDOW_NORMAL en ciertos entornos Windows.
    """
    cv2.namedWindow(nombre, cv2.WINDOW_AUTOSIZE)
    blank = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.imshow(nombre, blank)
    cv2.waitKey(1)

# ── MENU PRINCIPAL ────────────────────────────────────────────────────────────
def menu_principal():
    W, H = 520, 430
    # Titulos sin caracteres especiales para evitar mojibake en Windows
    WIN  = "Sistema NOJA - Acceso"
    crear_ventana(WIN, W, H)

    img   = np.zeros((H, W, 3), dtype=np.uint8)
    hover = -1

    BOTONES = [
        (60, 140, 400, 68, "Acceder",     "Reconocer rostro y entrar"),
        (60, 228, 400, 68, "Registrar",   "Registrar nuevo rostro"),
        (60, 316, 400, 68, "Registrados", "Ver usuarios registrados"),
        (60, 404, 180, 38, "Salir",       ""),
    ]

    state = {"click": -1}

    def mouse(event, x, y, flags, param):
        nonlocal hover
        hover = -1
        for i, (bx, by, bw, bh, *_) in enumerate(BOTONES):
            if bx <= x <= bx+bw and by <= y <= by+bh:
                hover = i
        if event == cv2.EVENT_LBUTTONDOWN:
            for i, (bx, by, bw, bh, *_) in enumerate(BOTONES):
                if bx <= x <= bx+bw and by <= y <= by+bh:
                    param["click"] = i

    cv2.setMouseCallback(WIN, mouse, state)

    while True:
        img[:] = FONDO
        barra_top(img, "Inicio de sesion - Reconocimiento Facial")

        cx = W // 2
        cv2.circle(img, (cx, 100), 30, (40,40,40), -1)
        cv2.circle(img, (cx, 100), 30, ACENTO, 1)
        cv2.circle(img, (cx,  93), 10, ACENTO, -1)
        cv2.ellipse(img, (cx, 118), (18,10), 0, 180, 360, ACENTO, -1)

        regs = rostros_registrados()
        est  = ("Usuarios: " + ", ".join(regs)) if regs else "Sin usuarios registrados"
        t(img, est, 20, 136, 0.37, (90,175,90) if regs else (110,110,110))

        for i, (bx, by, bw, bh, label, sub) in enumerate(BOTONES):
            col = ACENTO if i < 3 else ROJO
            dibujar_btn(img, bx, by, bw, bh, label, sub, hover==i, col)

        barra_bot(img, "Clic en una opcion  |  ESC para salir")
        cv2.imshow(WIN, img)

        key = cv2.waitKey(30) & 0xFF
        if key == 27 or state["click"] == 3:
            cv2.destroyWindow(WIN)
            return None

        if state["click"] != -1:
            click = state["click"]
            state["click"] = -1
            cv2.destroyWindow(WIN)
            if click == 0: return "acceder"
            if click == 1: return "escanear"
            if click == 2: return "registrados"

# ── PANTALLA REGISTRADOS ──────────────────────────────────────────────────────
def pantalla_registrados():
    W, H = 520, 400
    WIN  = "NOJA - Usuarios registrados"
    crear_ventana(WIN, W, H)
    img  = np.zeros((H, W, 3), dtype=np.uint8)

    while True:
        img[:] = FONDO
        barra_top(img, "Usuarios Registrados")
        regs = rostros_registrados()
        if regs:
            for i, nombre in enumerate(regs):
                y = 100 + i * 48
                if y > H - 50:
                    break
                cv2.circle(img, (48, y-5), 15, (40,40,40), -1)
                cv2.circle(img, (48, y-5), 15, ACENTO, 1)
                t(img, nombre[0].upper(), 43, y,    0.52, ACENTO)
                t(img, nombre,            76, y,    0.58, BLANCO)
                cv2.line(img, (68, y+14), (W-28, y+14), (45,45,45), 1)
        else:
            t(img, "No hay usuarios registrados.", 60, 200, 0.55, GRIS)

        barra_bot(img, "Presiona cualquier tecla para volver")
        cv2.imshow(WIN, img)
        if cv2.waitKey(100) != -1:
            break

    cv2.destroyWindow(WIN)

# ── ESCANEAR ─────────────────────────────────────────────────────────────────
def modo_escanear():
    # Input nombre
    WIN_INP   = "NOJA - Nombre"
    W_I, H_I  = 500, 82
    crear_ventana(WIN_INP, W_I, H_I)
    inp    = np.zeros((H_I, W_I, 3), dtype=np.uint8)
    nombre = ""

    while True:
        inp[:] = (20,20,20)
        t(inp, "Nombre del usuario:", 14, 24, 0.53, GRIS)
        cv2.rectangle(inp, (14,34), (W_I-14, 66), (40,40,40), -1)
        cv2.rectangle(inp, (14,34), (W_I-14, 66), ACENTO,      1)
        t(inp, nombre + "|", 20, 57, 0.58, BLANCO)
        cv2.imshow(WIN_INP, inp)
        key = cv2.waitKey(50) & 0xFF
        if   key == 13 and nombre.strip():
            break
        elif key == 27:
            cv2.destroyWindow(WIN_INP)
            return
        elif key == 8 and nombre:
            nombre = nombre[:-1]
        elif 32 <= key <= 126:
            nombre += chr(key)

    cv2.destroyWindow(WIN_INP)
    nombre = nombre.strip()

    model = cargar_yolo()
    cap   = cv2.VideoCapture(0)
    if not cap.isOpened():
        ventana_error("No se pudo abrir la camara.")
        return

    WIN_CAM = "NOJA - Escaneando"
    crear_ventana(WIN_CAM, 640, 480)

    db              = cargar_db()
    fotos_guardadas = []
    num_prev        = len(db.get(nombre, []))

    while len(fotos_guardadas) < 3:
        ret, frame = cap.read()
        if not ret:
            break
        fm = frame.copy()
        _, box = detectar_rostro(model, frame)
        if box:
            x1, y1, x2, y2 = box
            cv2.rectangle(fm, (x1,y1),(x2,y2), VERDE, 2)
        fh, fw = fm.shape[:2]
        cv2.rectangle(fm, (0,0),     (fw,52),  (0,0,0), -1)
        cv2.rectangle(fm, (0,fh-38), (fw,fh),  (0,0,0), -1)
        t(fm, f"Registrando: {nombre}",           10, 22, 0.58, VERDE_CLARO)
        t(fm, f"Fotos: {len(fotos_guardadas)}/3", 10, 44, 0.46, GRIS)
        t(fm, "ESPACIO=capturar  ESC=cancelar",   10, fh-13, 0.45, GRIS)
        pw = int((fw-20)*len(fotos_guardadas)/3)
        cv2.rectangle(fm, (10,fh-7),(fw-10,fh-3), (50,50,50), -1)
        if pw > 0:
            cv2.rectangle(fm, (10,fh-7),(10+pw,fh-3), ACENTO, -1)
        cv2.imshow(WIN_CAM, fm)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            cap.release()
            cv2.destroyWindow(WIN_CAM)
            return
        elif key == 32:
            rostro, _ = detectar_rostro(model, frame)
            if rostro is None or rostro.size == 0:
                continue
            slug = nombre.replace(" ","_").lower()
            ruta = os.path.join(ROSTROS_DIR, f"{slug}_{num_prev+len(fotos_guardadas)}.jpg")
            cv2.imwrite(ruta, rostro)
            fotos_guardadas.append(ruta)
            flash = fm.copy()
            cv2.rectangle(flash, (0,0),(fw,fh),(0,200,80),4)
            cv2.imshow(WIN_CAM, flash)
            cv2.waitKey(300)

    cap.release()
    cv2.destroyWindow(WIN_CAM)

    if len(fotos_guardadas) == 3:
        db[nombre] = db.get(nombre, []) + fotos_guardadas
        guardar_db(db)
        ventana_exito(f"'{nombre}' registrado correctamente")

# ── ACCEDER ───────────────────────────────────────────────────────────────────
def modo_acceder():
    db = cargar_db()
    if not db:
        ventana_error("No hay usuarios registrados.\nVe a Registrar primero.")
        return

    model = cargar_yolo()
    cap   = cv2.VideoCapture(0)
    if not cap.isOpened():
        ventana_error("No se pudo abrir la camara.")
        return

    hora   = datetime.now().hour
    saludo = ("Buenos dias"   if hora < 12 else
              "Buenas tardes" if hora < 18 else
              "Buenas noches")

    temp_path = os.path.join(ROOT_DIR, "data", "temp_rostro.jpg")
    WIN_CAM   = "NOJA - Reconocimiento"
    crear_ventana(WIN_CAM, 640, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        fm = frame.copy()
        fh, fw = fm.shape[:2]
        _, box = detectar_rostro(model, frame)
        if box:
            x1,y1,x2,y2 = box
            cv2.rectangle(fm,(x1,y1),(x2,y2),VERDE,2)
        cv2.rectangle(fm,(0,0),     (fw,44),  (0,0,0),-1)
        cv2.rectangle(fm,(0,fh-38), (fw,fh),  (0,0,0),-1)
        t(fm, "Posiciona tu rostro en la camara", 10, 28, 0.58, BLANCO)
        t(fm, "ESPACIO=reconocer  ESC=volver",    10, fh-13, 0.45, GRIS)
        cv2.imshow(WIN_CAM, fm)
        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break

        elif key == 32:
            rostro, _ = detectar_rostro(model, frame)
            if rostro is None or rostro.size == 0:
                continue

            wait = np.zeros_like(fm)
            t(wait, "Analizando rostro...", fw//2-130, fh//2, 0.7, AMARILLO, 2)
            cv2.imshow(WIN_CAM, wait)
            cv2.waitKey(1)

            cv2.imwrite(temp_path, rostro)
            mejor_match = None
            mejor_dist  = float("inf")

            for nombre_db, rutas in db.items():
                for ruta in rutas:
                    if not os.path.exists(ruta):
                        continue
                    try:
                        res = DeepFace.verify(
                            img1_path=temp_path,
                            img2_path=ruta,
                            model_name=MODELO_DEEPFACE,
                            enforce_detection=False,
                            silent=True,
                        )
                        if res["distance"] < mejor_dist:
                            mejor_dist  = res["distance"]
                            mejor_match = nombre_db
                    except Exception:
                        continue

            if os.path.exists(temp_path):
                os.remove(temp_path)

            if mejor_match and mejor_dist < UMBRAL:
                cap.release()
                cv2.destroyAllWindows()
                cv2.waitKey(1)
                ventana_bienvenida(saludo, mejor_match)
                lanzar_app(mejor_match)
                return
            else:
                no = np.zeros_like(fm)
                x0, y0 = fw//2-95, fh//2-42
                cv2.rectangle(no,(x0,y0),(x0+190,y0+84),(40,0,0),-1)
                cv2.rectangle(no,(x0,y0),(x0+190,y0+84),ROJO,1)
                t(no,"No reconocido",  x0+8, y0+44, 0.62,(80,80,255),2)
                t(no,"Intenta de nuevo",x0+8,y0+70, 0.42, GRIS)
                cv2.imshow(WIN_CAM, no)
                cv2.waitKey(1800)

    cap.release()
    cv2.destroyWindow(WIN_CAM)

# ── Ventanas auxiliares ───────────────────────────────────────────────────────
def ventana_error(msg):
    WIN = "NOJA - Error"
    W, H = 460, 160
    crear_ventana(WIN, W, H)
    img = np.full((H,W,3), (20,20,20), dtype=np.uint8)
    for i, linea in enumerate(msg.split("\n")):
        t(img, linea, 30, 60+i*34, 0.56, ROJO)
    t(img, "Presiona cualquier tecla", 80, H-18, 0.42, GRIS)
    cv2.imshow(WIN, img)
    cv2.waitKey(0)
    cv2.destroyWindow(WIN)

def ventana_exito(msg):
    WIN = "NOJA - Exito"
    W, H = 460, 200
    crear_ventana(WIN, W, H)
    img = np.full((H,W,3),(20,20,20),dtype=np.uint8)
    cv2.circle(img,(W//2,66),30,(30,70,30),-1)
    cv2.circle(img,(W//2,66),30,VERDE,2)
    t(img,"OK",W//2-14,74,0.72,VERDE_CLARO,2)
    t(img, msg, 28,130,0.50,BLANCO)
    t(img,"Presiona cualquier tecla",80,168,0.42,GRIS)
    cv2.imshow(WIN, img)
    cv2.waitKey(0)
    cv2.destroyWindow(WIN)

def ventana_bienvenida(saludo, nombre):
    WIN = "NOJA - Bienvenido"
    W, H = 520, 310
    crear_ventana(WIN, W, H)
    img = np.full((H,W,3),(18,18,18),dtype=np.uint8)
    cx  = W//2
    cv2.circle(img,(cx,80),40,(25,60,25),-1)
    cv2.circle(img,(cx,80),40,VERDE,2)
    cv2.line(img,(cx-18,80),(cx-3,98),(0,255,100),3)
    cv2.line(img,(cx-3,98),(cx+22,60),(0,255,100),3)
    t(img, saludo + ",",        78,158,0.70,GRIS)
    t(img, nombre,              78,198,0.90,VERDE_CLARO,2)
    t(img,"Acceso concedido",  144,238,0.52,(100,200,100))
    t(img,"Abriendo sistema...",136,272,0.44,GRIS)
    cv2.imshow(WIN, img)
    cv2.waitKey(2400)
    cv2.destroyWindow(WIN)

# ── Lanzar app.py ─────────────────────────────────────────────────────────────
def lanzar_app(nombre_usuario):
    cv2.destroyAllWindows()
    cv2.waitKey(1)   # flush de eventos pendientes de OpenCV
    import time
    time.sleep(0.3)  # pequeña pausa para que OpenCV libere las ventanas
    kwargs = {"cwd": ROOT_DIR}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            [sys.executable, APP_PATH, "--usuario", nombre_usuario],
            **kwargs,
        )
    except Exception as e:
        print(f"[face_login] No se pudo lanzar app.py: {e}")
    # Salir del proceso de face_login completamente
    sys.exit(0)

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        accion = menu_principal()
        if accion is None:
            break
        elif accion == "acceder":
            modo_acceder()
        elif accion == "escanear":
            modo_escanear()
        elif accion == "registrados":
            pantalla_registrados()