import cv2
import base64
import threading
import os
import sys
import httpx
from PIL import Image, ImageTk

# ── Path para encontrar config.py en la raíz ──────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROBOFLOW_API_KEY  = "oceK61twCXIqNSqyLB8q"
ROBOFLOW_MODEL_ID = "horarios-deteccion/2"
ROBOFLOW_URL      = f"https://detect.roboflow.com/{ROBOFLOW_MODEL_ID}"

COLORES = [
    (0, 255, 0),
    (255, 100, 0),
    (0, 100, 255),
    (255, 0, 200),
    (0, 220, 220),
]


class CamaraYOLO:
    def __init__(
        self,
        label_widget,
        camara_idx: int = 0,
        confianza: float = 0.30,
        ancho: int = 640,
        alto: int = 480,
        intervalo_api: int = 5,
        callback_deteccion=None,
    ):
        self.label              = label_widget
        self.camara_idx         = camara_idx
        self.confianza          = confianza
        self.ancho              = ancho
        self.alto               = alto
        self.intervalo_api      = intervalo_api
        self.callback_deteccion = callback_deteccion

        self._activo              = False
        self._hilo                = None
        self._cap                 = None
        self._ultimas_detecciones = []
        self._frame_count         = 0

    def iniciar(self):
        if self._activo:
            return
        self._cap = cv2.VideoCapture(self.camara_idx)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.ancho)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto)

        if not self._cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la cámara (índice {self.camara_idx}). "
                "Verifica que esté conectada y no esté en uso."
            )

        self._activo = True
        self._hilo   = threading.Thread(target=self._loop, daemon=True)
        self._hilo.start()
        print("Camara YOLO iniciada (modo API Roboflow).")

    def detener(self):
        self._activo = False
        if self._hilo:
            self._hilo.join(timeout=2)
        if self._cap:
            self._cap.release()
        print("Camara YOLO detenida.")

    @property
    def esta_activa(self):
        return self._activo

    def _loop(self):
        while self._activo:
            ok, frame = self._cap.read()
            if not ok:
                break

            self._frame_count += 1

            if self._frame_count % self.intervalo_api == 0:
                detecciones = self._llamar_api(frame)
                if detecciones is not None:
                    self._ultimas_detecciones = detecciones
                    if self.callback_deteccion:
                        self.callback_deteccion(self._ultimas_detecciones)

            frame_anotado = self._dibujar(frame, self._ultimas_detecciones)
            self._actualizar_label(frame_anotado)

        self._activo = False

    def _llamar_api(self, frame):
        try:
            _, buf  = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            img_b64 = base64.b64encode(buf).decode("utf-8")

            with httpx.Client(timeout=5) as client:
                resp = client.post(
                    ROBOFLOW_URL,
                    params={
                        "api_key":    ROBOFLOW_API_KEY,
                        "confidence": int(self.confianza * 100),
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    content=img_b64,
                )

            if resp.status_code != 200:
                return None

            predicciones = resp.json().get("predictions", [])
            return [
                {
                    "clase":     p["class"],
                    "confianza": round(p["confidence"], 3),
                    "bbox": (
                        int(p["x"] - p["width"]  / 2),
                        int(p["y"] - p["height"] / 2),
                        int(p["x"] + p["width"]  / 2),
                        int(p["y"] + p["height"] / 2),
                    ),
                }
                for p in predicciones
            ]
        except Exception as e:
            print(f"Error API Roboflow: {e}")
            return None

    def _dibujar(self, frame, detecciones):
        frame        = frame.copy()
        clases_vistas = {}

        for d in detecciones:
            clase     = d["clase"]
            confianza = d["confianza"]
            x1, y1, x2, y2 = d["bbox"]

            if clase not in clases_vistas:
                clases_vistas[clase] = COLORES[len(clases_vistas) % len(COLORES)]
            color = clases_vistas[clase]

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            etiqueta = f"{clase} {confianza*100:.0f}%"
            (tw, th), _ = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(frame, etiqueta, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.putText(frame, f"Detecciones: {len(detecciones)}", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return frame

    def _actualizar_label(self, frame):
        try:
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.label.after(0, self._set_image, imgtk)
        except Exception:
            pass

    def _set_image(self, imgtk):
        try:
            self.label.configure(image=imgtk)
            self.label.image = imgtk
        except Exception:
            pass