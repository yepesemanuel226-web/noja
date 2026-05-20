# NOJA — Sistema de Gestión de Horarios

## Estructura del proyecto

```
NOJA/
├── mainapi.py          ← API FastAPI (UN SOLO ARCHIVO)
├── app.py              ← App de escritorio CustomTkinter
├── config.py           ← Claves y rutas
├── requirements.txt
│
├── core/
│   ├── rag.py          ← Chatbot RAG (LangChain + ChromaDB)
│   ├── camara_yolo.py  ← Detección YOLO en tiempo real
│   ├── roboflow_api.py ← Análisis de fotos con Groq Vision
│   └── face_login.py   ← Login facial (corre independiente)
│
├── bot/
│   └── bot.py          ← Bot de Telegram
│
├── Docs_Dir/           ← PDFs para el RAG (reglamento, estatutos, etc.)
├── assets/fotos/       ← Fotos capturadas por cámara/Telegram
├── chroma_db/          ← Base vectorial (se crea automáticamente)
├── data/               ← horarios.db SQLite (se crea automáticamente)
└── reportes_pdf/       ← PDFs generados (se crea automáticamente)
```

## Instalación

```bash
pip install -r requirements.txt --break-system-packages
```

## Ejecución

### 1. Iniciar la API (terminal 1)
```bash
uvicorn mainapi:app --reload --port 8000
```
Documentación interactiva: http://localhost:8000/docs

### 2. Crear usuario admin (solo la primera vez)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/registro-inicial?nombre=Admin" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@noja.edu","password":"admin123"}'
```

### 3. Iniciar la App (terminal 2)
```bash
python app.py
```

### 4. Iniciar el Bot de Telegram (terminal 3)
```bash
python -m bot.bot
```

### 5. Login facial (opcional, independiente)
```bash
python core/face_login.py
```

## Migrar a Supabase
En `mainapi.py`, línea ~17, cambiar:
```python
DATABASE_URL = "postgresql://user:password@db.xxxx.supabase.co:5432/postgres"
```
Y eliminar el `connect_args` de SQLite.