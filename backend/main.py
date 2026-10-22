from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.formparsers import MultiPartParser
from jose import JWTError, jwt

MultiPartParser.max_part_size = 1024 * 1024 * 50  # 50 MB
_orig_mp_init = MultiPartParser.__init__
def _patched_mp_init(self, *args, **kwargs):
    kwargs.setdefault("max_files", 10000)
    kwargs.setdefault("max_fields", 10000)
    _orig_mp_init(self, *args, **kwargs)
MultiPartParser.__init__ = _patched_mp_init
from routers import centrales, enlaces, grupos, mantenimientos, reportes, dashboard, resultados, datos, carga_manual, comentarios, datasets, cortes_manuales, instaladores, ris, nodos
from routers import auth
from config import settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Rutas que no requieren autenticación
PUBLIC_PATHS = {"/auth/login", "/auth/sso", "/auth/sso-check", "/health", "/docs", "/openapi.json", "/redoc"}

scheduler = AsyncIOScheduler()


async def _job_check_nodos():
    """Tarea programada: verifica estado de nodos cada 5 min."""
    import httpx as _httpx
    from database import SessionLocal
    from routers.nodos import _check_single
    from sqlalchemy import text as _t
    from datetime import datetime as _dt
    import asyncio as _aio

    db = SessionLocal()
    try:
        rows = db.execute(_t("SELECT DISTINCT ip1, `ssl` FROM centrales WHERE ip1 IS NOT NULL")).fetchall()
        nodes = [(r[0], r[1]) for r in rows]
        now = _dt.now()
        async with _httpx.AsyncClient(timeout=10, verify=False) as client:
            results = await _aio.gather(*[_check_single(ip, ssl, client) for ip, ssl in nodes])
        for r in results:
            was = db.execute(_t("SELECT online FROM nodos_estado WHERE ip = :ip"), {"ip": r["ip"]}).scalar()
            if was is None:
                db.execute(_t("""
                    INSERT INTO nodos_estado (ip, online, ultimo_check, ultimo_online, ultimo_caida, error_msg)
                    VALUES (:ip, :on, :now, :uon, :uca, :err)
                """), {"ip": r["ip"], "on": int(r["online"]), "now": now,
                       "uon": now if r["online"] else None,
                       "uca": now if not r["online"] else None, "err": r["error"]})
            else:
                sets = ["online = :on", "ultimo_check = :now", "error_msg = :err"]
                params = {"ip": r["ip"], "on": int(r["online"]), "now": now, "err": r["error"]}
                if r["online"]:
                    sets.append("ultimo_online = :now")
                elif was:
                    sets.append("ultimo_caida = :now")
                db.execute(_t(f"UPDATE nodos_estado SET {', '.join(sets)} WHERE ip = :ip"), params)
        db.commit()
    finally:
        db.close()


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
        pass
    finally:
        _db.close()

    _db_dat = SessionLocal()
    try:
        _db_dat.execute(_text(
            "ALTER TABLE resultados_central ADD COLUMN dat_estado VARCHAR(50) DEFAULT NULL"
        ))
        _db_dat.commit()
    except Exception:
        pass
    finally:
        _db_dat.close()

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

    _db4 = SessionLocal()
    try:
        _db4.execute(_text("""
            CREATE TABLE IF NOT EXISTS instalaciones_log (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                planta_base     VARCHAR(50) NOT NULL,
                central_nombre  VARCHAR(100),
                protocolo       VARCHAR(10),
                usuario         VARCHAR(100),
                sotra_cn        VARCHAR(100),
                sotrb_cn        VARCHAR(100),
                created_at      DATETIME NOT NULL,
                UNIQUE KEY uq_planta (planta_base)
            )
        """))
        _db4.commit()
    except Exception:
        pass
    finally:
        _db4.close()

    scheduler.add_job(
        _job_guardar_resultados,
        CronTrigger(hour=0, minute=30),
        id="reporte_diario",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_check_nodos,
        CronTrigger(minute="*/5"),
        id="check_nodos",
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
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logging.error(f"[HTTP {exc.status_code}] {request.method} {request.url.path} — {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logging.exception(f"[500] {request.method} {request.url.path} — {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


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
app.include_router(datasets.router)
app.include_router(cortes_manuales.router)
app.include_router(instaladores.router)
app.include_router(ris.router)
app.include_router(nodos.router)


@app.get("/health")
def health():
    return {"status": "ok"}
