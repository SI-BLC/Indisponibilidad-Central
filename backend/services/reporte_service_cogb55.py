"""
Cálculo de indisponibilidad para centrales vinculadas al concentrador COGB55.

COGB55 es un concentrador especial: todas sus centrales transmiten por un único
enlace COGB_CAMM, diferenciándose solo por número de grupo.  La tabla
`cogb55_grupos` asigna qué grupos corresponden a cada central.

- Cortes: se toman del enlace COGB_CAMM completo (aplican a todas las centrales).
- Datos: se filtran los registros .dat de COGB_CAMM por los grupos de la central.

La tabla `grupos` no tiene entradas para COGB_CAMM, así que el tipo de cada
grupo se infiere del número: 1xx→1(medidas), 3xx→3(estados), 5xx→5(alarmas).
"""

from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.reporte_service import (
    _es_directo,
    _nombre_asoc,
    _procesar_corte_asoc_pd,
    _excluir_periodos_con_corte,
    _update_excluidos_pd,
    _misc1_pd,
    _sumas_parciales_pd,
    _misc2_pd,
    _armar_informe_pd,
    _detectar_eventos_huerfanos,
    _estado_inicial_enlace,
    _PESO_POR_TIPO,
)

ID_CONCENTRADOR = 110
ID_ENLACE_CAMM = 476

# COGB_CAMM groups: 1xx=medidas(1), 3xx=estados(3), 5xx=alarmas(5)
_TIPO_POR_CENTENA = {1: 1, 3: 3, 5: 5}


def _tipo_grupo_cogb55(grupo: int) -> int:
    return _TIPO_POR_CENTENA.get(grupo // 100, 1)


def _peso_grupo(tipo: int) -> float:
    return _PESO_POR_TIPO.get(int(tipo), 0.0)


def _get_grupos_central(id_central: int, db: Session) -> list[int]:
    rows = db.execute(
        text("SELECT grupo FROM cogb55_grupos WHERE id_central=:c"),
        {"c": id_central},
    ).fetchall()
    return [r[0] for r in rows]


def _procesar_datos_dat_cogb55(
    ini: datetime, fin: datetime, grupos_central: list[int], db: Session
) -> pd.DataFrame:
    """Versión de _procesar_datos_dat_pd para COGB55.

    No depende de la tabla `grupos` — infiere el tipo del número de grupo.
    Solo carga registros para los grupos indicados.
    """
    ini_adj = ini + timedelta(minutes=1)
    fin_adj = fin + timedelta(minutes=1)

    nombre_agente = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:e LIMIT 1"),
        {"e": ID_ENLACE_CAMM},
    ).scalar() or "COGB_CAMM"

    tol_datos = float(
        db.execute(text("SELECT tol_datos FROM configuracion LIMIT 1")).scalar() or 2
    )

    prefix = "A" if _es_directo(ID_ENLACE_CAMM, db) else "B"
    asoc_b = prefix + "B"
    asoc_c = prefix + "C"

    ph = ", ".join(f":g{i}" for i in range(len(grupos_central)))
    params = {f"g{i}": g for i, g in enumerate(grupos_central)}
    params.update({"e": ID_ENLACE_CAMM, "ini": ini_adj, "fin": fin_adj})

    try:
        rows = db.execute(
            text(f"""SELECT id, fecha, id_gr, gr_grupo, siz, t, g, h, c, e, m, i, exp, freq, st
                     FROM dat WHERE id_enlace=:e AND gr_grupo IN ({ph})
                     AND fecha>:ini AND fecha<=:fin"""),
            params,
        ).fetchall()
    except Exception:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        _, fecha, id_gr, grupo, nobj, rec, bue, cong, calc, est, man, inv, exp, freq, st = row

        if id_gr != "R":
            continue

        tipo = _tipo_grupo_cogb55(grupo)
        ui = _peso_grupo(tipo)

        if freq is not None:
            asoc = asoc_c
            n_chq = 0
            esperados = float(exp or 0)
        else:
            asoc = asoc_b
            n_chq = int(st or 0)
            esperados = float(n_chq * nobj)

        tol = esperados * tol_datos / 100
        rec, bue, cong, man, inv = (float(x or 0) for x in (rec, bue, cong, man, inv))

        if tipo == 1:
            n_inv = cong + inv + man
            if rec > 0 and rec >= esperados:
                n_norec = 0.0
                n_inval = n_inv * esperados / rec if rec else 0.0
            else:
                n_norec = esperados - rec
                n_inval = n_inv
        else:
            if rec > 0 and rec >= esperados:
                exceso = rec - esperados
                n_inv2 = max(0.0, cong + inv - exceso / 2)
                n_norec = 0.0
                n_inval = (n_inv2 + man / 2) * esperados / rec if rec else 0.0
            else:
                n_inv2 = cong + inv
                n_norec = esperados - rec
                n_inval = n_inv2 + man / 2

        records.append({
            "fecha": fecha,
            "intervalo": 0,
            "asoc": asoc,
            "grupo": grupo,
            "tipo": tipo,
            "nobjetos": nobj,
            "esperados": esperados,
            "recibidos": rec,
            "norecibidos": n_norec,
            "buenos": bue,
            "congelados": cong,
            "calculados": calc,
            "estimados": est,
            "manuales": man,
            "invalidos": inv,
            "nchequeos": n_chq,
            "analizar": 1,
            "ui": ui,
            "ui_esperadas": esperados * ui,
            "ui_recibidas": rec * ui,
            "ui_norecibidas": n_norec * ui,
            "ui_invalidas": n_inval * ui,
            "ui_tolerancia": tol * ui,
            "idenlace": ID_ENLACE_CAMM,
            "agente": nombre_agente,
            "subagente": nombre_agente,
            "ui_norec_netas": (n_norec - tol) * ui,
            "ui_inv_netas": (n_inval - tol) * ui,
            "ui_ind_mant_perm": 0.0,
        })

    return pd.DataFrame(records)


def _run_pipeline(grupos_central: list[int], ini: datetime, fin: datetime, db: Session):
    """Ejecuta el pipeline completo: cortes (enlace full) + datos (grupos filtrados).

    Retorna (df_dat, df_sum, df_cortes, valores).
    """
    tol = int(
        db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120
    )

    # Dat para corte detection: usa procesador estándar con TODOS los grupos de COGB_CAMM
    # (necesita los dat para el check hay/fecha_max en _procesar_corte_asoc_pd)
    df_dat_for_cortes = _procesar_datos_dat_cogb55(
        ini, fin, _all_cogb55_grupos(db), db
    )

    asocs = ["ab", "ac"] if _es_directo(ID_ENLACE_CAMM, db) else ["bb", "bc"]
    all_cortes: list[dict] = []
    for asoc in asocs:
        all_cortes.extend(
            _procesar_corte_asoc_pd(asoc, ini, fin, ID_ENLACE_CAMM, tol, df_dat_for_cortes, db)
        )
    df_cortes = (
        pd.DataFrame(all_cortes)
        if all_cortes
        else pd.DataFrame(
            columns=["inicio", "fin", "idenlace", "asoc", "ind_bruta", "ind_neta", "tipo"]
        )
    )

    # Dat filtrado solo por los grupos de esta central
    df_dat = _procesar_datos_dat_cogb55(ini, fin, grupos_central, db)

    if not df_dat.empty and not df_cortes.empty:
        df_dat = _excluir_periodos_con_corte(df_dat, df_cortes)

    ac = _nombre_asoc("C", ID_ENLACE_CAMM, db)
    ab = _nombre_asoc("B", ID_ENLACE_CAMM, db)

    if not df_dat.empty:
        df_dat = _update_excluidos_pd(df_dat, df_cortes)
        df_dat = _misc1_pd(df_dat)
        df_sum = _sumas_parciales_pd(df_dat)
        df_dat = _misc2_pd(df_dat, df_sum, ac, ab)
    else:
        df_sum = pd.DataFrame()

    _, valores = _armar_informe_pd(ID_ENLACE_CAMM, ini, fin, df_dat, df_sum, df_cortes, db)
    return df_dat, df_sum, df_cortes, valores


def _all_cogb55_grupos(db: Session) -> list[int]:
    """Todos los grupos asignados en cogb55_grupos (para detectar cortes con dat completo)."""
    rows = db.execute(text("SELECT DISTINCT grupo FROM cogb55_grupos")).fetchall()
    if rows:
        return [r[0] for r in rows]
    # Fallback: todos los grupos que existen en dat para COGB_CAMM
    rows = db.execute(
        text("SELECT DISTINCT gr_grupo FROM dat WHERE id_enlace=:e"),
        {"e": ID_ENLACE_CAMM},
    ).fetchall()
    return [r[0] for r in rows]


# ─── API pública ────────────────────────────────────────────────────────────


def calcular_ind_cogb55(
    id_central: int, ini: datetime, fin: datetime, db: Session
) -> tuple[float | None, float | None, float | None, bool]:
    """
    Calcula indisponibilidad para una central vinculada a COGB55.
    Retorna (ind_cortes_seg, ind_datos_seg, ind_total_seg, inconsistencia).
    """
    grupos = _get_grupos_central(id_central, db)
    if not grupos:
        return None, None, None, False

    _, _, _, valores = _run_pipeline(grupos, ini, fin, db)

    if not valores:
        return 0.0, 0.0, 0.0, False

    cortes = float(valores.get("promedio_neto", 0.0))
    datos = float(valores.get("ind_datos_norm", 0.0))
    total = float(valores.get("ind_total_norm", 0.0))

    huerfanos = _detectar_eventos_huerfanos(ID_ENLACE_CAMM, ini, fin, db)
    return cortes, datos, total, len(huerfanos) > 0


def generar_reporte_txt_cogb55(
    id_central: int, ini: datetime, fin: datetime, db: Session
) -> str:
    """Genera el reporte TXT para una central COGB55."""
    row = db.execute(
        text("SELECT nemo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central},
    ).fetchone()
    nemo = row[0] if row else str(id_central)

    grupos = _get_grupos_central(id_central, db)
    if not grupos:
        return f"Central {nemo}: sin grupos COGB55 asignados.\n"

    df_dat, df_sum, df_cortes, _ = _run_pipeline(grupos, ini, fin, db)

    txt, _ = _armar_informe_pd(ID_ENLACE_CAMM, ini, fin, df_dat, df_sum, df_cortes, db)
    header = (
        f"=== COGB55 — Central {nemo} — Grupos: {grupos} ===\n"
        f"Enlace utilizado: COGB_CAMM (filtrado por grupos asignados)\n\n"
    )
    return header + (txt or f"Sin datos para {nemo}.\n")


def es_central_cogb55(id_central: int, db: Session) -> bool:
    """True si la central tiene grupos asignados en cogb55_grupos."""
    count = db.execute(
        text("SELECT COUNT(*) FROM cogb55_grupos WHERE id_central=:c"),
        {"c": id_central},
    ).scalar()
    return (count or 0) > 0


def evaluar_dat_estado_cogb55(id_central: int, ini: datetime, fin: datetime,
                               db: Session) -> str | None:
    """Evalúa si COGB_CAMM tiene datos .dat para los grupos de esta central."""
    grupos = _get_grupos_central(id_central, db)
    if not grupos:
        return "incompleto"

    ini_adj = ini + timedelta(minutes=1)
    fin_adj = fin + timedelta(minutes=1)
    ph = ", ".join(f":g{i}" for i in range(len(grupos)))
    params = {f"g{i}": g for i, g in enumerate(grupos)}
    params.update({"e": ID_ENLACE_CAMM, "ini": ini_adj, "fin": fin_adj})

    count = db.execute(
        text(f"""SELECT COUNT(DISTINCT fecha) FROM dat
                 WHERE id_enlace=:e AND gr_grupo IN ({ph})
                 AND fecha>:ini AND fecha<=:fin"""),
        params,
    ).scalar() or 0
    return None if count >= 44 else "incompleto"


def detalle_central_cogb55(
    id_central: int, ini: datetime, fin: datetime, db: Session
) -> dict:
    """Detalle on-the-fly para una central COGB55."""
    row = db.execute(
        text("SELECT nemo, tipo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central},
    ).fetchone()
    if not row:
        return {}
    nemo, tipo = row

    grupos = _get_grupos_central(id_central, db)
    if not grupos:
        return {"central": nemo, "tipo": tipo, "error": "Sin grupos COGB55 asignados"}

    tol_c = int(
        db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120
    )

    # Calcular valores
    ind_cortes, ind_datos, ind_total, _ = calcular_ind_cogb55(id_central, ini, fin, db)

    # ── Timeline del enlace ─────────────────────────────────────────────────
    prefix = "a" if _es_directo(ID_ENLACE_CAMM, db) else "b"
    col_b = f"asoc_{prefix}b"
    col_c = f"asoc_{prefix}c"

    def _query_events(col):
        rows = db.execute(
            text(f"SELECT fecha, {col} FROM con"
                 f" WHERE id_enlace=:e AND fecha>=:ini AND fecha<=:fin"
                 f" AND {col} IN ('i+','e+') ORDER BY fecha"),
            {"e": ID_ENLACE_CAMM, "ini": ini, "fin": fin},
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    ev_b = _query_events(col_b)
    ev_c = _query_events(col_c)
    up_ini_b = _estado_inicial_enlace(ID_ENLACE_CAMM, col_b, ini, db)
    up_ini_c = _estado_inicial_enlace(ID_ENLACE_CAMM, col_c, ini, db)

    merged = sorted(
        [(t, tp, "b") for t, tp in ev_b] + [(t, tp, "c") for t, tp in ev_c],
        key=lambda x: x[0],
    )

    segs: list[dict] = []
    cur_t = ini
    cur_up_b, cur_up_c = up_ini_b, up_ini_c
    for t_ev, ev_tipo, assoc in merged:
        combined = cur_up_b and cur_up_c
        segs.append({
            "inicio": cur_t.isoformat(), "fin": t_ev.isoformat(),
            "estado": "up" if combined else "down",
            "dur_seg": (t_ev - cur_t).total_seconds(),
        })
        if assoc == "b":
            cur_up_b = ev_tipo == "e+"
        else:
            cur_up_c = ev_tipo == "e+"
        cur_t = t_ev
    combined = cur_up_b and cur_up_c
    segs.append({
        "inicio": cur_t.isoformat(), "fin": fin.isoformat(),
        "estado": "up" if combined else "down",
        "dur_seg": (fin - cur_t).total_seconds(),
    })

    nombre_e = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": ID_ENLACE_CAMM}
    ).scalar() or "COGB_CAMM"

    cortes_out = [
        {"enlace": nombre_e, "inicio": s["inicio"], "fin": s["fin"],
         "dur_seg": s["dur_seg"], "bajo_tolerancia": s["dur_seg"] < tol_c}
        for s in segs if s["estado"] == "down"
    ]

    # ── Periodos dat filtrados por grupos ───────────────────────────────────
    df_dat_filtered = _procesar_datos_dat_cogb55(ini, fin, grupos, db)
    periodos_dat: dict[str, dict] = {}
    if not df_dat_filtered.empty:
        for _, r in df_dat_filtered.iterrows():
            key = pd.Timestamp(r["fecha"]).isoformat()
            periodos_dat.setdefault(key, {
                "esperados": 0.0, "recibidos": 0.0, "buenos": 0.0,
                "norecibidos": 0.0, "invalidos": 0.0,
                "ui_norec": 0.0, "ui_noval": 0.0,
            })
            periodos_dat[key]["esperados"]   += float(r.get("esperados",   0) or 0)
            periodos_dat[key]["recibidos"]   += float(r.get("recibidos",   0) or 0)
            periodos_dat[key]["buenos"]      += float(r.get("buenos",      0) or 0)
            periodos_dat[key]["norecibidos"] += float(r.get("norecibidos", 0) or 0)
            periodos_dat[key]["invalidos"]   += float(r.get("invalidos",   0) or 0)
            periodos_dat[key]["ui_norec"]    += float(r.get("ui_norecibidas", 0) or 0)
            periodos_dat[key]["ui_noval"]    += float(r.get("ui_invalidas",   0) or 0)

    periodos_lista = [
        {"intervalo_fin": k, "enlace": "COGB_CAMM", **v}
        for k, v in sorted(periodos_dat.items())
    ]

    huerfanos = _detectar_eventos_huerfanos(ID_ENLACE_CAMM, ini, fin, db)
    huerfanos_out = [
        {**inc, "t1": inc["t1"].isoformat(), "t2": inc["t2"].isoformat()}
        for inc in huerfanos
    ]

    return {
        "central": nemo, "tipo": tipo,
        "ind_total_seg": float(ind_total or 0.0),
        "inconsistencias": huerfanos_out,
        "segments": segs,
        "cortes_efectivos": cortes_out,
        "periodos_dat": periodos_lista,
        "cogb55_grupos": grupos,
    }
