from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from calendar import monthrange
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/ris", tags=["RIS"])


def _seg_mes(anio: int, mes: int) -> int:
    _, dias = monthrange(anio, mes)
    return dias * 86400


@router.get("/{id_central}")
def get_ris(
    id_central: int,
    mes: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    anio, mes_num = int(mes[:4]), int(mes[5:7])

    central = db.execute(
        text("SELECT id, nemo, nemo_cammesa, cliente, tipo, protocolo, pem FROM centrales WHERE id = :id"),
        {"id": id_central},
    ).mappings().first()
    if not central:
        raise HTTPException(404, "Central no encontrada")

    if central["tipo"] not in (1, 2, 3):
        raise HTTPException(400, "Solo centrales tipo 1/2/3 tienen RIS")

    pem = central["pem"] or date(2025, 1, 1)
    inicio_penalidad = date(pem.year + 1, pem.month, 1)

    # --- DIARIO ---
    primer_dia = date(anio, mes_num, 1)
    _, ultimo = monthrange(anio, mes_num)
    ultimo_dia = date(anio, mes_num, ultimo)

    rows_diario = db.execute(
        text("""
            SELECT fecha, ind_cortes_seg, ind_datos_seg, ind_total_seg, inconsistencia, dat_estado
            FROM resultados_central
            WHERE id_central = :c AND fecha BETWEEN :ini AND :fin
            ORDER BY fecha
        """),
        {"c": id_central, "ini": primer_dia, "fin": ultimo_dia},
    ).mappings().all()

    diario = []
    for r in rows_diario:
        diario.append({
            "fecha": r["fecha"].isoformat(),
            "ind_cortes_seg": r["ind_cortes_seg"],
            "ind_datos_seg": r["ind_datos_seg"],
            "ind_total_seg": r["ind_total_seg"],
            "inconsistencia": r["inconsistencia"],
            "dat_estado": r["dat_estado"],
        })

    seg_mes_actual = _seg_mes(anio, mes_num)
    sum_cortes = sum((d["ind_cortes_seg"] or 0) for d in diario)
    sum_datos = sum((d["ind_datos_seg"] or 0) for d in diario)
    sum_total = sum((d["ind_total_seg"] or 0) for d in diario)

    # --- HISTORICO (desde PEM hasta mes solicitado) ---
    historico_rows = db.execute(
        text("""
            SELECT
                YEAR(fecha) as anio, MONTH(fecha) as mes_n,
                SUM(COALESCE(ind_cortes_seg, 0)) as sum_cortes,
                SUM(COALESCE(ind_datos_seg, 0)) as sum_datos,
                SUM(COALESCE(ind_total_seg, 0)) as sum_total
            FROM resultados_central
            WHERE id_central = :c AND fecha >= :pem AND fecha <= :fin
            GROUP BY YEAR(fecha), MONTH(fecha)
            ORDER BY anio, mes_n
        """),
        {"c": id_central, "pem": pem, "fin": ultimo_dia},
    ).mappings().all()

    hist_data = []
    for h in historico_rows:
        h_anio, h_mes = int(h["anio"]), int(h["mes_n"])
        seg_m = _seg_mes(h_anio, h_mes)
        s_cortes = float(h["sum_cortes"] or 0)
        s_datos = float(h["sum_datos"] or 0)
        s_total = float(h["sum_total"] or 0)
        pct = (s_total / seg_m * 100) if seg_m else 0
        pct_cortes = (s_cortes / seg_m * 100) if seg_m else 0
        pct_datos = (s_datos / seg_m * 100) if seg_m else 0
        hist_data.append({
            "mes": f"{h_anio:04d}-{h_mes:02d}",
            "seg_totales": seg_m,
            "ind_cortes_seg": s_cortes,
            "ind_datos_seg": s_datos,
            "ind_total_seg": s_total,
            "ind_pct": round(pct, 6),
            "ind_cortes_pct": round(pct_cortes, 6),
            "ind_datos_pct": round(pct_datos, 6),
        })

    # Rolling 12-month window for ind_acum_pct (like Excel SUMPRODUCT)
    historico = []
    for idx, h in enumerate(hist_data):
        start_idx = max(0, idx - 11)
        rolling_total = sum(hist_data[i]["ind_total_seg"] for i in range(start_idx, idx + 1))
        rolling_seg = sum(hist_data[i]["seg_totales"] for i in range(start_idx, idx + 1))
        pct_acum = (rolling_total / rolling_seg * 100) if rolling_seg else 0
        historico.append({**h, "ind_acum_pct": round(pct_acum, 6)})

    # --- AÑO MOVIL (últimos 12 meses hasta mes solicitado) ---
    anio_movil_meses = []
    for i in range(11, -1, -1):
        m = mes_num - i
        a = anio
        while m <= 0:
            m += 12
            a -= 1
        anio_movil_meses.append(f"{a:04d}-{m:02d}")

    am_lookup = {h["mes"]: h for h in historico}
    am_total_seg = 0.0
    am_cortes_seg = 0.0
    am_datos_seg = 0.0
    am_seg_totales = 0
    meses_sobre_umbral = 0
    meses_con_datos = 0
    anio_movil_detalle = []

    for mk in anio_movil_meses:
        a_m, m_m = int(mk[:4]), int(mk[5:7])
        mes_pem = f"{pem.year:04d}-{pem.month:02d}"
        if mk < mes_pem:
            continue
        seg_m = _seg_mes(a_m, m_m)
        am_seg_totales += seg_m
        if mk in am_lookup:
            entry = am_lookup[mk]
            am_total_seg += entry["ind_total_seg"]
            am_cortes_seg += entry["ind_cortes_seg"]
            am_datos_seg += entry["ind_datos_seg"]
            if entry["ind_pct"] > 0.5:
                meses_sobre_umbral += 1
            meses_con_datos += 1
            anio_movil_detalle.append({
                "mes": mk,
                "seg_totales": entry["seg_totales"],
                "ind_cortes_seg": entry["ind_cortes_seg"],
                "ind_datos_seg": entry["ind_datos_seg"],
                "ind_total_seg": entry["ind_total_seg"],
                "ind_cortes_pct": entry["ind_cortes_pct"],
                "ind_datos_pct": entry["ind_datos_pct"],
                "ind_pct": entry["ind_pct"],
                "ind_acum_pct": entry["ind_acum_pct"],
            })
        else:
            anio_movil_detalle.append({
                "mes": mk,
                "seg_totales": seg_m,
                "ind_cortes_seg": 0,
                "ind_datos_seg": 0,
                "ind_total_seg": 0,
                "ind_cortes_pct": 0,
                "ind_datos_pct": 0,
                "ind_pct": 0,
                "ind_acum_pct": 0,
            })

    am_pct = (am_total_seg / am_seg_totales * 100) if am_seg_totales else 0

    # --- TABLAS: cortes relevantes del mes (ind_neta > 1000 seg) ---
    enlace_ids = db.execute(
        text("SELECT id FROM enlaces WHERE idcentral = :c"),
        {"c": id_central},
    ).scalars().all()

    tablas_cortes = []
    if enlace_ids:
        placeholders = ",".join(str(eid) for eid in enlace_ids)
        cortes_rows = db.execute(
            text(f"""
                SELECT cr.id_enlace, e.nombre as enlace, cr.fecha, cr.asoc, cr.inicio, cr.fin,
                       cr.ind_bruta, cr.ind_neta, cr.tipo
                FROM cortes_reporte cr
                JOIN enlaces e ON e.id = cr.id_enlace
                WHERE cr.id_enlace IN ({placeholders})
                  AND cr.fecha BETWEEN :ini AND :fin
                  AND cr.ind_neta > 1000
                ORDER BY cr.ind_neta DESC
            """),
            {"ini": primer_dia, "fin": ultimo_dia},
        ).mappings().all()

        for cr in cortes_rows:
            tablas_cortes.append({
                "enlace": cr["enlace"],
                "fecha": cr["fecha"].isoformat(),
                "asoc": cr["asoc"],
                "inicio": cr["inicio"].isoformat(),
                "fin": cr["fin"].isoformat(),
                "ind_bruta_seg": cr["ind_bruta"],
                "ind_neta_seg": cr["ind_neta"],
                "tipo": cr["tipo"],
            })

    # --- TABLAS: datos inválidos relevantes del mes (ind_datos_norm > 1000 seg por día) ---
    tablas_datos = []
    if enlace_ids:
        datos_rows = db.execute(
            text(f"""
                SELECT rr.id_enlace, e.nombre as enlace, rr.fecha, rr.ind_datos_norm
                FROM resultados_reporte rr
                JOIN enlaces e ON e.id = rr.id_enlace
                WHERE rr.id_enlace IN ({placeholders})
                  AND rr.fecha BETWEEN :ini AND :fin
                  AND rr.ind_datos_norm > 1000
                ORDER BY rr.ind_datos_norm DESC
            """),
            {"ini": primer_dia, "fin": ultimo_dia},
        ).mappings().all()

        for dr in datos_rows:
            tablas_datos.append({
                "enlace": dr["enlace"],
                "fecha": dr["fecha"].isoformat(),
                "ind_datos_seg": float(dr["ind_datos_norm"] or 0),
            })

    # --- OBSERVACIONES (comentarios del mes) ---
    comentarios_rows = db.execute(
        text("""
            SELECT tipo, fecha_dia, fecha_inicio, fecha_fin, texto, usuario, duracion_seg
            FROM comentarios
            WHERE id_central = :c AND fecha_dia BETWEEN :ini AND :fin
            ORDER BY fecha_dia, fecha_inicio
        """),
        {"c": id_central, "ini": primer_dia, "fin": ultimo_dia},
    ).mappings().all()

    diario_lookup = {d["fecha"]: d for d in diario}

    obs_cortes = []
    obs_datos = []
    for cm in comentarios_rows:
        fecha_iso = cm["fecha_dia"].isoformat()
        dia_data = diario_lookup.get(fecha_iso, {})

        if cm["tipo"] == "corte":
            if cm["duracion_seg"] is not None:
                duracion = float(cm["duracion_seg"])
            else:
                duracion = dia_data.get("ind_cortes_seg") or 0
            obs_cortes.append({
                "fecha": fecha_iso,
                "fecha_inicio": cm["fecha_inicio"],
                "fecha_fin": cm["fecha_fin"],
                "duracion_seg": round(duracion, 2),
                "texto": cm["texto"],
                "usuario": cm["usuario"],
            })
        elif cm["tipo"] == "dat":
            duracion = dia_data.get("ind_datos_seg") or 0
            seg_dia = 86400
            pct = round(duracion / seg_dia * 100, 4) if seg_dia else 0
            obs_datos.append({
                "fecha": fecha_iso,
                "duracion_seg": round(duracion, 2),
                "pct": pct,
                "texto": cm["texto"],
                "usuario": cm["usuario"],
            })

    return {
        "central": {
            "id": central["id"],
            "nemo": central["nemo"],
            "nemo_cammesa": central["nemo_cammesa"],
            "cliente": central["cliente"],
            "tipo": central["tipo"],
            "protocolo": central["protocolo"],
            "pem": pem.isoformat(),
            "inicio_penalidad": inicio_penalidad.isoformat(),
        },
        "mes": mes,
        "diario": diario,
        "resumen_mes": {
            "seg_totales": seg_mes_actual,
            "ind_cortes_seg": round(sum_cortes, 2),
            "ind_datos_seg": round(sum_datos, 2),
            "ind_total_seg": round(sum_total, 2),
            "ind_pct": round(sum_total / seg_mes_actual * 100, 6) if seg_mes_actual else 0,
            "ind_cortes_pct": round(sum_cortes / seg_mes_actual * 100, 6) if seg_mes_actual else 0,
            "ind_datos_pct": round(sum_datos / seg_mes_actual * 100, 6) if seg_mes_actual else 0,
        },
        "historico": historico,
        "anio_movil": {
            "meses": anio_movil_meses,
            "detalle": anio_movil_detalle,
            "ind_total_seg": round(am_total_seg, 2),
            "ind_cortes_seg": round(am_cortes_seg, 2),
            "ind_datos_seg": round(am_datos_seg, 2),
            "seg_totales": am_seg_totales,
            "ind_pct": round(am_pct, 6),
            "meses_sobre_umbral": meses_sobre_umbral,
            "meses_con_datos": meses_con_datos,
        },
        "tablas": {
            "cortes": tablas_cortes,
            "datos": tablas_datos,
        },
        "observaciones": {
            "cortes": obs_cortes,
            "datos": obs_datos,
        },
    }


# ─── Validación RIS ──────────────────────────────────────────────────────────

class ValidacionBody(BaseModel):
    validado: bool
    comentario: Optional[str] = None


@router.get("/validacion/{id_central}/{mes}")
def get_validacion(
    id_central: int,
    mes: str,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("""SELECT id, id_central, mes, validado, comentario, usuario, fecha_validacion
                FROM validaciones_ris WHERE id_central = :c AND mes = :m"""),
        {"c": id_central, "m": mes},
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "id_central": row[1],
        "mes": row[2],
        "validado": bool(row[3]),
        "comentario": row[4],
        "usuario": row[5],
        "fecha_validacion": row[6].isoformat() if row[6] else None,
    }


@router.post("/validacion/{id_central}/{mes}")
def set_validacion(
    id_central: int,
    mes: str,
    body: ValidacionBody,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    now = datetime.now()

    existing = db.execute(
        text("SELECT id FROM validaciones_ris WHERE id_central = :c AND mes = :m"),
        {"c": id_central, "m": mes},
    ).fetchone()

    if existing:
        db.execute(
            text("""UPDATE validaciones_ris
                    SET validado = :v, comentario = :com, usuario = :u, fecha_validacion = :f
                    WHERE id = :id"""),
            {"v": int(body.validado), "com": body.comentario, "u": usuario, "f": now, "id": existing[0]},
        )
    else:
        db.execute(
            text("""INSERT INTO validaciones_ris (id_central, mes, validado, comentario, usuario, fecha_validacion)
                    VALUES (:c, :m, :v, :com, :u, :f)"""),
            {"c": id_central, "m": mes, "v": int(body.validado), "com": body.comentario, "u": usuario, "f": now},
        )
    db.commit()

    row = db.execute(
        text("""SELECT id, id_central, mes, validado, comentario, usuario, fecha_validacion
                FROM validaciones_ris WHERE id_central = :c AND mes = :m"""),
        {"c": id_central, "m": mes},
    ).fetchone()
    return {
        "id": row[0],
        "id_central": row[1],
        "mes": row[2],
        "validado": bool(row[3]),
        "comentario": row[4],
        "usuario": row[5],
        "fecha_validacion": row[6].isoformat() if row[6] else None,
    }
