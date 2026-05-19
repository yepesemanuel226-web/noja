from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base, DATABASE_URL
import backend.models
from backend.routers import router

app = FastAPI(
    title="Sistema de Gestión de Horarios",
    description="API para gestión de horarios académicos - Proyecto 9",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    print("=" * 55)
    print("  Iniciando API de Gestión de Horarios...")

    # Intentar crear tablas — no bloquea el arranque si falla
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("  ✅ Tablas verificadas/creadas en Supabase")
    except Exception as e:
        print(f"  ⚠️  No se pudieron crear tablas: {e}")
        print("  La API arrancará de todas formas.")

    # Mostrar host conectado (sin exponer contraseña)
    try:
        host_info = DATABASE_URL.split("@")[1].split("/")[0]
    except Exception:
        host_info = "desconocido"

    print(f"  Base de datos: {host_info}")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 55)


@app.get("/")
def root():
    return {
        "mensaje": "API de Gestión de Horarios funcionando",
        "docs": "/docs",
        "base_de_datos": "Supabase PostgreSQL",
    }