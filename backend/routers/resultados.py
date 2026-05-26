from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime, timedelta
from typing import Optional
import calendar
from database import get_db
import models
import schemas
from services.reporte_service import guardar_resultados_dia, guardar_resultados_mes, _detalle_central, _a_hora_local

router = APIRouter(prefix="/resultados", tags=["Resultados"])


@router.post("/guardar", summary="Calcular y guardar resultados del día indicado")
def guardar_resultados(
    fecha: Optional[date] = Query(
        default=None,
        description="Fecha a procesar (YYYY-MM-DD). Si se omite, se usa el día de ayer.",
    ),
    db: Session = Depends(get_db),
):
    fecha_proc = fecha if fecha else (date.today() - timedelta(days=1))
    detalle = guardar_resultados_dia(fecha_proc, db)
    ok = sum(1 for r in detalle if r.get("ok"))
    return {
        "fecha": str(fecha_proc),
        "procesados": len(detalle),
        "exitosos": ok,
        "fallidos": len(detalle) - ok,
        "detalle": detalle,
    }


@router.post("/guardar-mes", summary="Calcular y guardar resultados del mes en curso (sobreescribe existentes)")
def guardar_resultados_mes_endpoint(
    year: Optional[int] = Query(default=None, description="Año (por defecto: año actual)"),
    month: Optional[int] = Query(default=None, description="Mes (1-12, por defecto: mes actual)"),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    y = year if year else hoy.year
    m = month if month else hoy.month
    resultado = guardar_resultados_mes(y, m, db)
    return resultado


@router.get("/cortes", response_model=list[schemas.CorteReporteOut])
def get_cortes_reporte(
    ids_enlace: list[int] = Query(default=[]),
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    conditions: list[str] = []
    params: dict = {}

    if ids_enlace:
        placeholders = ", ".join(f":e{i}" for i in range(len(ids_enlace)))
        conditions.append(f"id_enlace IN ({placeholders})")
        params.update({f"e{i}": v for i, v in enumerate(ids_enlace)})
    if fecha_desde:
        conditions.append("fecha >= :fd")
        params["fd"] = fecha_desde
    if fecha_hasta:
        conditions.append("fecha <= :fh")
        params["fh"] = fecha_hasta

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(f"SELECT * FROM cortes_reporte {where} ORDER BY fecha, id_enlace, inicio"),
        params,
    ).fetchall()
    return [schemas.CorteReporteOut.model_validate(dict(r._mapping)) for r in rows]


@router.get("/centrales", response_model=list[schemas.ResultadoCentralOut])
def get_resultados_centrales(
    id_central: Optional[int] = Query(default=None),
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Devuelve resúmenes por central/día desde resultados_central."""
    conditions = ["UPPER(c.nemo) != 'BCOG'"]
    params: dict = {}

    if id_central is not None:
        conditions.append("rc.id_central = :id_central")
        params["id_central"] = id_central
    if fecha_desde:
        conditions.append("rc.fecha >= :fd")
        params["fd"] = fecha_desde
    if fecha_hasta:
        conditions.append("rc.fecha <= :fh")
        params["fh"] = fecha_hasta

    where = "WHERE " + " AND ".join(conditions)
    rows = db.execute(
        text(f"""SELECT rc.*, c.nemo AS central_nemo, c.tipo AS central_tipo
                 FROM resultados_central rc
                 JOIN centrales c ON c.id = rc.id_central
                 {where}
                 ORDER BY rc.fecha DESC, c.nemo ASC"""),
        params,
    ).fetchall()
    return [schemas.ResultadoCentralOut.model_validate(dict(r._mapping)) for r in rows]


@router.get("/detalle/{id_central}/{fecha}")
def get_detalle_central(
    id_central: int,
    fecha: date,
    db: Session = Depends(get_db),
):
    """Detalle on-the-fly de indisponibilidad de una central para un día dado."""
    ini = _a_hora_local(datetime(fecha.year, fecha.month, fecha.day))
    fin = ini + timedelta(days=1)
    resultado = _detalle_central(id_central, ini, fin, db)
    if not resultado:
        raise HTTPException(status_code=404, detail="Central no encontrada")
    return resultado


@router.get("/", response_model=list[schemas.ResultadoReporteOut])
def get_resultados(
    id_central: Optional[int] = Query(default=None),
    id_enlace: Optional[int] = Query(default=None),
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    params: dict = {}
    extra_parts = []

    if id_enlace is not None:
        extra_parts.append("rr.id_enlace = :id_enlace")
        params["id_enlace"] = id_enlace
    if fecha_desde:
        extra_parts.append("rr.fecha >= :fecha_desde")
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        extra_parts.append("rr.fecha <= :fecha_hasta")
        params["fecha_hasta"] = fecha_hasta

    extra = (" AND " + " AND ".join(extra_parts)) if extra_parts else ""

    if id_central is not None:
        central = db.query(models.Central).filter(models.Central.id == id_central).first()
        if not central:
            return []

        is_bcog = central.nemo.upper() == "BCOG"
        is_backup_red = central.tipo in (2, 3)

        if is_backup_red and not is_bcog:
            # Backup/Redundante: own links + BCOG links matching BCOG_{nemo} or {nemo}_CAMM
            params.update({"id_central": id_central, "c_nemo": central.nemo, "c_tipo": central.tipo})
            sql = text(f"""
                (
                    SELECT rr.*, c.nemo AS central_nemo, c.tipo AS central_tipo,
                           e.idcentral AS id_central_enlace
                    FROM resultados_reporte rr
                    LEFT JOIN enlaces e ON e.id = rr.id_enlace
                    LEFT JOIN centrales c ON c.id = e.idcentral
                    WHERE e.idcentral = :id_central {extra}
                )
                UNION ALL
                (
                    SELECT rr.*, :c_nemo AS central_nemo, :c_tipo AS central_tipo,
                           e.idcentral AS id_central_enlace
                    FROM resultados_reporte rr
                    JOIN enlaces e ON e.id = rr.id_enlace
                    JOIN centrales bcog ON bcog.id = e.idcentral AND UPPER(bcog.nemo) = 'BCOG'
                    WHERE (
                        UPPER(e.nombre) = UPPER(CONCAT('BCOG_', :c_nemo))
                        OR UPPER(e.nombre) = UPPER(CONCAT(:c_nemo, '_CAMM'))
                    ) {extra}
                )
                ORDER BY fecha DESC
            """)
        else:
            # Directa o BCOG seleccionado: query normal
            params["id_central"] = id_central
            sql = text(f"""
                SELECT rr.*, c.nemo AS central_nemo, c.tipo AS central_tipo,
                       e.idcentral AS id_central_enlace
                FROM resultados_reporte rr
                LEFT JOIN enlaces e ON e.id = rr.id_enlace
                LEFT JOIN centrales c ON c.id = e.idcentral
                WHERE e.idcentral = :id_central {extra}
                ORDER BY rr.fecha DESC
            """)
    else:
        # Todas las centrales: excluir BCOG como grupo propio;
        # reasignar enlaces BCOG al central al que pertenecen
        sql = text(f"""
            (
                SELECT rr.*, c.nemo AS central_nemo, c.tipo AS central_tipo,
                       e.idcentral AS id_central_enlace
                FROM resultados_reporte rr
                LEFT JOIN enlaces e ON e.id = rr.id_enlace
                LEFT JOIN centrales c ON c.id = e.idcentral
                WHERE (c.nemo IS NULL OR UPPER(c.nemo) != 'BCOG') {extra}
            )
            UNION ALL
            (
                SELECT rr.*, assoc.nemo AS central_nemo, assoc.tipo AS central_tipo,
                       e.idcentral AS id_central_enlace
                FROM resultados_reporte rr
                JOIN enlaces e ON e.id = rr.id_enlace
                JOIN centrales bcog ON bcog.id = e.idcentral AND UPPER(bcog.nemo) = 'BCOG'
                JOIN centrales assoc ON (
                    UPPER(e.nombre) = UPPER(CONCAT('BCOG_', assoc.nemo))
                    OR UPPER(e.nombre) = UPPER(CONCAT(assoc.nemo, '_CAMM'))
                ) AND assoc.tipo IN (2, 3)
                WHERE 1=1 {extra}
            )
            ORDER BY central_nemo ASC, fecha DESC
        """)

    rows = db.execute(sql, params).fetchall()
    return [schemas.ResultadoReporteOut.model_validate(dict(row._mapping)) for row in rows]
