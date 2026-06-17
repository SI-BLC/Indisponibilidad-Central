from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from jose import JWTError, jwt
from routers import centrales, enlaces, grupos, mantenimientos, reportes, dashboard, resultados, datos, carga_manual, comentarios
from routers import auth
from config import settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Rutas que no requieren autenticación
PUBLIC_PATHS = {"/auth/login", "/health", "/docs", "/openapi.json", "/redoc"}

scheduler = AsyncIOScheduler()


async def _job_guardar_resultados():
    """Tarea programada: guarda resultados del día anterior a las 00:30."""
    from datetime import date, timedelta
    from database import SessionLocal
    from services.reporte_service import guardar_resultados_dia
    db = SessionLocal()
    try:
        fecha_ayer = date.today() - timedelta(days=1)
        guardar_resultados_dia(fecha_ayer, db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar que la columna corte_efectivo existe en resultados_reporte
    from database import SessionLocal
    from sqlalchemy import text as _text
    _db = SessionLocal()
    try:
        _db.execute(_text(
            "ALTER TABLE resultados_reporte ADD COLUMN corte_efectivo FLOAT DEFAULT NULL"
        ))
        _db.commit()
    except Exception:
        pass  # La columna ya existe
    finally:
        _db.close()

    _db2 = SessionLocal()
    try:
        _db2.execute(_text("""
            CREATE TABLE IF NOT EXISTS comentarios (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                id_central INT NOT NULL,
                fecha      DATE NOT NULL,
                texto      TEXT NOT NULL,
                usuario    VARCHAR(100) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE KEY uq_central_fecha (id_central, fecha)
            )
        """))
        _db2.commit()
    except Exception:
        pass
    finally:
        _db2.close()

    _db3 = SessionLocal()
    try:
        _db3.execute(_text("""
            CREATE TABLE IF NOT EXISTS cortes_reporte (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                id_enlace  INT NOT NULL,
                fecha      DATE NOT NULL,
                asoc       VARCHAR(4),
                inicio     DATETIME NOT NULL,
                fin        DATETIME NOT NULL,
                ind_bruta  INT DEFAULT 0,
                ind_neta   INT DEFAULT 0,
                tipo       INT DEFAULT 0,
                INDEX idx_enlace_fecha (id_enlace, fecha)
            )
        """))
        _db3.commit()
    except Exception:
        pass
    finally:
        _db3.close()

    scheduler.add_job(
        _job_guardar_resultados,
        CronTrigger(hour=0, minute=30),
        id="reporte_diario",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Indisponibilidad API",
    description="API REST para el sistema de monitoreo de disponibilidad de centrales",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        request.state.user = payload
    except JWTError:
        return JSONResponse(status_code=401, content={"detail": "Token inválido o expirado"})

    return await call_next(request)


app.include_router(auth.router)
app.include_router(centrales.router)
app.include_router(enlaces.router)
app.include_router(grupos.router)
app.include_router(mantenimientos.router)
app.include_router(reportes.router)
app.include_router(dashboard.router)
app.include_router(resultados.router)
app.include_router(datos.router)
app.include_router(carga_manual.router)
app.include_router(comentarios.router)


@app.get("/health")
def health():
    return {"status": "ok"}
