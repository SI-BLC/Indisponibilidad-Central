"""
Servicio de cálculo de indisponibilidad para centrales ICCP.
Completamente separado de ELCOM — lee de con_iccp, dat_iccp, datasets.
Reutiliza funciones de pipeline comunes de reporte_service.py.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

# Reutilizar funciones comunes del servicio ELCOM
from services.reporte_service import (
    seg_to_hms, _completar, _peso_grupo, _make_corte,
    _update_excluidos_pd, _misc1_pd, _excluir_periodos_con_corte,
    _get_enlace_directo, _get_enlace_backup_bcog,
    _construir_timeline_tipo2 as _construir_timeline_tipo2_elcom,
    _fracciones_periodo,
)


# ─── Estado inicial ──────────────────────────────────────────────────────────

def _estado_inicial_iccp(id_enlace: int, col: str, ini: datetime, db: Session) -> bool:
    """True si el enlace ICCP estaba UP antes de ini.
    col: 'c_state' o 's_state'."""
    last = db.execute(
        text(f"SELECT {col} FROM con_iccp WHERE id_enlace=:e AND {col} IN ('i+','e+') AND fecha<:ini ORDER BY fecha DESC LIMIT 1"),
        {"e": id_enlace, "ini": ini}
    ).scalar()
    if last is None:
        fin = ini + timedelta(days=1)
        total_t = db.execute(
            text("SELECT COALESCE(SUM(t), 0) FROM dat_iccp WHERE id_enlace=:e AND fecha>=:ini AND fecha<:fin AND direction='tx'"),
            {"e": id_enlace, "ini": ini, "fin": fin}
        ).scalar() or 0
        return total_t > 0
    return last == "e+"


# ─── Procesamiento DAT ICCP ──────────────────────────────────────────────────

def _procesar_datos_dat_iccp(ini: datetime, fin: datetime,
                              id_enlace: int, db: Session) -> pd.DataFrame:
    """Lee dat_iccp (direction=tx) + datasets, retorna df_dat con misma estructura que ELCOM."""
    nombre_agente = db.execute(
        text("""SELECT CASE WHEN c.tipo != 4 THEN CONCAT(c.nemo,'_CAMM') ELSE e.nombre END
                FROM centrales c LEFT JOIN enlaces e ON c.id=e.idcentral
                WHERE e.id=:e LIMIT 1"""),
        {"e": id_enlace}
    ).scalar()

    tol_datos = float(db.execute(
        text("SELECT tol_datos FROM configuracion LIMIT 1")
    ).scalar() or 2)

    try:
        rows = db.execute(
            text("""SELECT fecha, ds, siz, t, g, h, c, e, m, i, exp
                    FROM dat_iccp WHERE id_enlace=:e AND direction='tx'
                    AND fecha>=:ini AND fecha<:fin"""),
            {"e": id_enlace, "ini": ini, "fin": fin}
        ).fetchall()
    except Exception:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    # Cargar datasets configurados
    try:
        ds_rows = db.execute(
            text("SELECT ds_nombre, tipo, calcular FROM datasets WHERE id_enlace=:e"),
            {"e": id_enlace}
        ).fetchall()
    except Exception:
        ds_rows = []
    ds_dict = {r[0]: {"tipo": r[1], "calcular": r[2]} for r in ds_rows}

    records = []
    for row in rows:
        fecha, ds_nombre, nobj, rec, bue, cong, calc, est, man, inv, exp_val = row

        ds_data = ds_dict.get(ds_nombre)
        if not ds_data:
            continue
        if ds_data["calcular"] != 1:
            continue
        tipo = int(ds_data["tipo"])

        ui = _peso_grupo(tipo)
        asoc = "C"  # ICCP: toda la data tx se asigna a asociación C
        esperados = float(exp_val or 0)

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
            "grupo": ds_nombre,  # en ICCP el "grupo" es el ds_nombre
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
            "nchequeos": 0,
            "analizar": 1,
            "ui": ui,
            "ui_esperadas": esperados * ui,
            "ui_recibidas": rec * ui,
            "ui_norecibidas": n_norec * ui,
            "ui_invalidas": n_inval * ui,
            "ui_tolerancia": tol * ui,
            "idenlace": id_enlace,
            "agente": nombre_agente,
            "subagente": nombre_agente,
            "ui_norec_netas": (n_norec - tol) * ui,
            "ui_inv_netas": (n_inval - tol) * ui,
            "ui_ind_mant_perm": 0.0,
        })

    return pd.DataFrame(records)


# ─── Detección de cortes ICCP ─────────────────────────────────────────────────

def _procesar_corte_iccp(col: str, ini: datetime, fin: datetime,
                          id_enlace: int, tol: int,
                          df_dat: pd.DataFrame, db: Session) -> list[dict]:
    """Detecta cortes ICCP desde con_iccp.
    col: 'c_state' o 's_state'. Retorna lista de dicts corte."""
    asoc = "C" if col == "c_state" else "S"
    EV_CAIDA, EV_ESTAB = 1, 2

    # Verificar si hay datos .dat para este enlace
    if not df_dat.empty:
        mask_asoc = (df_dat["asoc"] == asoc) & (df_dat["idenlace"] == id_enlace)
        hay = bool((mask_asoc & (df_dat["recibidos"] != 0)).any())
    else:
        hay = False

    # Leer eventos de con_iccp
    rows = db.execute(
        text(f"""SELECT fecha, {col} FROM con_iccp
                 WHERE id_enlace=:e AND fecha>=:ini AND fecha<:fin
                 AND {col} IN ('i+','e+')
                 ORDER BY fecha ASC"""),
        {"e": id_enlace, "ini": ini, "fin": fin}
    ).fetchall()

    data = []

    # Estado inicial
    was_up = _estado_inicial_iccp(id_enlace, col, ini, db)

    if rows:
        estado = 2 if was_up else 0  # 0=desconocido, 1=caido, 2=establecido
        for row in rows:
            fecha_ev = row[0]
            if isinstance(fecha_ev, str):
                fecha_ev = datetime.fromisoformat(fecha_ev)
            ev_str = row[1]
            ev = EV_CAIDA if ev_str == "i+" else EV_ESTAB

            if estado == 0:
                if ev == EV_CAIDA:
                    data.append((asoc, EV_CAIDA, fecha_ev, id_enlace, 0))
                    estado = 1
                elif ev == EV_ESTAB:
                    data.append((asoc, EV_CAIDA, ini, id_enlace, 1))
                    data.append((asoc, EV_ESTAB, fecha_ev, id_enlace, 1))
                    estado = 2
            elif estado == 1:
                if ev == EV_ESTAB:
                    data.append((asoc, EV_ESTAB, fecha_ev, id_enlace, 0))
                    estado = 2
            elif estado == 2:
                if ev == EV_CAIDA:
                    data.append((asoc, EV_CAIDA, fecha_ev, id_enlace, 0))
                    estado = 1

        fin_dia = fin - timedelta(seconds=1)
        if estado == 0:
            data.append((asoc, EV_CAIDA, ini, id_enlace, 0))
            data.append((asoc, EV_ESTAB, fin_dia, id_enlace, 0))
        elif estado == 1:
            data.append((asoc, EV_ESTAB, fin_dia, id_enlace, 0))
    else:
        fin_dia = fin - timedelta(seconds=1)
        if was_up:
            pass  # UP todo el día, sin cortes
        else:
            # DOWN todo el día
            data.append((asoc, EV_CAIDA, ini, id_enlace, 0))
            data.append((asoc, EV_ESTAB, fin_dia, id_enlace, 0))

    # Mantenimientos
    mantenimientos = db.execute(
        text("""SELECT inicio, fin FROM mantenimientos
                WHERE idenlace=:e AND inicio>:ini AND fin<:fin"""),
        {"e": id_enlace, "ini": ini, "fin": fin}
    ).fetchall()
    EV_MANT_INI, EV_MANT_FIN = 3, 4
    for mant in mantenimientos:
        mi = mant[0] if isinstance(mant[0], datetime) else datetime.fromisoformat(str(mant[0]))
        mf = mant[1] if isinstance(mant[1], datetime) else datetime.fromisoformat(str(mant[1]))
        data.append((asoc, EV_MANT_INI, mi, id_enlace, 0))
        data.append((asoc, EV_MANT_FIN, mf, id_enlace, 0))

    data.sort(key=lambda x: x[2])

    # Máquina de estados para generar cortes (misma lógica que ELCOM)
    cortes = []
    SM = 0
    SM_T1 = None
    for item in data:
        ev, fecha = item[1], item[2]
        if SM == 0:
            if ev == EV_MANT_INI:
                SM = 1
            elif ev == EV_CAIDA:
                SM_T1 = fecha; SM = 3
        elif SM == 1:
            if ev == EV_CAIDA:
                SM_T1 = fecha; SM = 2
            elif ev == EV_MANT_FIN:
                SM = 0
        elif SM == 2:
            if ev == EV_ESTAB:
                cortes.append(_make_corte(SM_T1, fecha, asoc, id_enlace, 1, tol))
                SM = 1
            elif ev == EV_MANT_FIN:
                cortes.append(_make_corte(SM_T1, fecha, asoc, id_enlace, 1, tol))
                SM_T1 = fecha; SM = 3
        elif SM == 3:
            if ev == EV_ESTAB:
                cortes.append(_make_corte(SM_T1, fecha, asoc, id_enlace, 0, tol))
                SM = 0
            elif ev == EV_MANT_INI:
                cortes.append(_make_corte(SM_T1, fecha, asoc, id_enlace, 0, tol))
                SM_T1 = fecha; SM = 2

    return cortes


# ─── Sumas parciales ICCP ────────────────────────────────────────────────────

def _sumas_parciales_iccp(df_dat: pd.DataFrame) -> pd.DataFrame:
    """Sumas parciales para ICCP — filtra por asoc C (no hay AB/BB/AC/BC)."""
    mask = (df_dat["analizar"] == 1) & df_dat["asoc"].isin(["C", "S"])
    df_f = df_dat[mask]
    if df_f.empty:
        return pd.DataFrame()

    df_sum = df_f.groupby(["fecha", "idenlace", "agente", "asoc"]).agg(
        sum_ui_esperadas=("ui_esperadas", "sum"),
        sum_ui_norec_netas=("ui_norec_netas", "sum"),
        sum_ui_inv_netas=("ui_inv_netas", "sum"),
        sum_ui_ind_mant_perm=("ui_ind_mant_perm", "sum"),
        sum_ui_norec_norm_ag=("ui_norec_norm", "sum"),
        sum_ui_inv_norm_ag=("ui_inv_norm", "sum"),
        sum_por_norec_esp=("por_norec_esp", "sum"),
        sum_por_inv_esp=("por_inv_esp", "sum"),
    ).reset_index()

    for c in ["sum_ui_ind_tot", "sum_ui_norec_norm", "sum_ui_inv_norm",
              "sum_ui_norec_mant", "sum_ui_inv_mant", "sum_ui_ind_norm",
              "sum_ui_ind_mant", "sum_seg_ind_norm", "sum_seg_ind_mant"]:
        df_sum[c] = 0.0

    df_sum = df_sum[df_sum["sum_ui_esperadas"] != 0].copy()
    df_sum.loc[df_sum["sum_ui_norec_netas"] < 0, "sum_ui_norec_netas"] = 0
    df_sum.loc[df_sum["sum_ui_inv_netas"] < 0, "sum_ui_inv_netas"] = 0
    df_sum["sum_ui_ind_tot"] = df_sum["sum_ui_norec_netas"] + df_sum["sum_ui_inv_netas"]

    m1 = df_sum["sum_ui_ind_mant_perm"] < df_sum["sum_ui_norec_netas"]
    m2 = (~m1) & (df_sum["sum_ui_ind_mant_perm"] <= df_sum["sum_ui_ind_tot"])
    m3 = df_sum["sum_ui_ind_mant_perm"] > df_sum["sum_ui_ind_tot"]

    df_sum.loc[m1, "sum_ui_norec_norm"] = df_sum.loc[m1, "sum_ui_norec_netas"] - df_sum.loc[m1, "sum_ui_ind_mant_perm"]
    df_sum.loc[m1, "sum_ui_norec_mant"] = df_sum.loc[m1, "sum_ui_ind_mant_perm"]
    df_sum.loc[m1, "sum_ui_inv_norm"] = df_sum.loc[m1, "sum_ui_inv_netas"]
    df_sum.loc[m1, "sum_ui_inv_mant"] = 0.0
    df_sum.loc[m2, "sum_ui_norec_norm"] = 0.0
    df_sum.loc[m2, "sum_ui_norec_mant"] = df_sum.loc[m2, "sum_ui_norec_netas"]
    df_sum.loc[m2, "sum_ui_inv_norm"] = df_sum.loc[m2, "sum_ui_ind_tot"] - df_sum.loc[m2, "sum_ui_ind_mant_perm"]
    df_sum.loc[m2, "sum_ui_inv_mant"] = df_sum.loc[m2, "sum_ui_ind_mant_perm"] - df_sum.loc[m2, "sum_ui_norec_netas"]
    df_sum.loc[m3, "sum_ui_norec_norm"] = 0.0
    df_sum.loc[m3, "sum_ui_norec_mant"] = df_sum.loc[m3, "sum_ui_norec_netas"]
    df_sum.loc[m3, "sum_ui_inv_norm"] = 0.0
    df_sum.loc[m3, "sum_ui_inv_mant"] = df_sum.loc[m3, "sum_ui_inv_netas"]

    df_sum["sum_ui_ind_norm"] = df_sum["sum_ui_norec_norm"] + df_sum["sum_ui_inv_norm"]
    df_sum["sum_ui_ind_mant"] = df_sum["sum_ui_norec_mant"] + df_sum["sum_ui_inv_mant"]
    mask_esp = df_sum["sum_ui_esperadas"] != 0
    df_sum.loc[mask_esp, "sum_seg_ind_norm"] = (
        df_sum.loc[mask_esp, "sum_ui_ind_norm"] * 1800 / df_sum.loc[mask_esp, "sum_ui_esperadas"]
    )
    df_sum.loc[mask_esp, "sum_seg_ind_mant"] = (
        df_sum.loc[mask_esp, "sum_ui_ind_mant"] * 1800 / df_sum.loc[mask_esp, "sum_ui_esperadas"]
    )
    return df_sum


def _misc2_iccp(df_dat: pd.DataFrame, df_sum: pd.DataFrame) -> pd.DataFrame:
    """misc2 para ICCP — usa asociación C."""
    if df_dat.empty or df_sum.empty:
        return df_dat
    from services.reporte_service import _misc2_pd
    return _misc2_pd(df_dat, df_sum, "C", "S")


# ─── Procesador de enlace ICCP ────────────────────────────────────────────────

def _procesar_enlace_iccp(id_enlace: int, ini: datetime, fin: datetime,
                           db: Session) -> tuple[str, dict, pd.DataFrame]:
    """Procesa un enlace ICCP. Retorna (txt, valores, df_cortes)."""
    tol = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)

    df_dat = _procesar_datos_dat_iccp(ini, fin, id_enlace, db)

    # Cortes para ambas asociaciones (C y S)
    all_cortes: list[dict] = []
    for col in ("c_state", "s_state"):
        all_cortes.extend(_procesar_corte_iccp(col, ini, fin, id_enlace, tol, df_dat, db))

    df_cortes = pd.DataFrame(all_cortes) if all_cortes else pd.DataFrame(
        columns=["inicio", "fin", "idenlace", "asoc", "ind_bruta", "ind_neta", "tipo"])

    # Excluir períodos .dat que se solapan con cortes
    if not df_dat.empty and not df_cortes.empty:
        df_dat = _excluir_periodos_con_corte(df_dat, df_cortes)

    if not df_dat.empty:
        df_dat = _update_excluidos_pd(df_dat, df_cortes)
        df_dat = _misc1_pd(df_dat)
        df_sum = _sumas_parciales_iccp(df_dat)
        df_dat = _misc2_iccp(df_dat, df_sum)
    else:
        df_sum = pd.DataFrame()

    txt, valores = _armar_informe_iccp(id_enlace, ini, fin, df_dat, df_sum, df_cortes, db)
    return txt, valores, df_cortes


# ─── Funciones de consulta ────────────────────────────────────────────────────

from services.reporte_service import (
    _calcular_vi_pd, _cant_cortes_pd, _ind_cortes_pd, _ind_bruta_pd,
    _num_periodos_pd, _contar_datos_pd, _norec_ui_pd, _norec_seg_pd,
    _noval_ui_pd, _noval_seg_pd, _mant_seg_pd, _obtener_cortes_pd,
)


# ─── Informe TXT ICCP ────────────────────────────────────────────────────────

def _armar_informe_iccp(id_enlace: int, ini: datetime, fin: datetime,
                         df_dat: pd.DataFrame, df_sum: pd.DataFrame,
                         df_cortes: pd.DataFrame, db: Session) -> tuple[str, dict]:
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    enlace_name = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:id LIMIT 1"), {"id": id_enlace}
    ).scalar() or str(id_enlace)

    tol_c = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)
    tol_d = int(db.execute(text("SELECT tol_datos FROM configuracion LIMIT 1")).scalar() or 2)

    ac = "C"  # ICCP: cliente
    ab = "S"  # ICCP: servidor

    vi_ct = _calcular_vi_pd(ac, True, df_dat)
    vi_st = _calcular_vi_pd(ab, True, df_dat)
    vi_total_t = vi_ct + vi_st

    isc_norm = _ind_cortes_pd(ac, 0, id_enlace, df_cortes)
    isc_mant = _ind_cortes_pd(ac, 1, id_enlace, df_cortes)
    iss_norm = _ind_cortes_pd(ab, 0, id_enlace, df_cortes)
    iss_mant = _ind_cortes_pd(ab, 1, id_enlace, df_cortes)

    is_cortes_norm = (isc_norm * vi_ct + iss_norm * vi_st) / vi_total_t if vi_total_t else 0.0
    is_cortes_mant = (isc_mant * vi_ct + iss_mant * vi_st) / vi_total_t if vi_total_t else 0.0

    bruta_c = int(_ind_bruta_pd(ac, id_enlace, df_cortes))
    bruta_s = int(_ind_bruta_pd(ab, id_enlace, df_cortes))

    vi_c = _calcular_vi_pd(ac, False, df_dat)
    vi_total = vi_c  # ICCP: solo datos tx (asociación C)

    is_datos_norm = 0.0
    is_datos_mant = 0.0

    if vi_total > 0:
        np_c = _num_periodos_pd(ac, id_enlace, df_dat)

        gl_esp, gl_rec, gl_bue, gl_man, _ = _contar_datos_pd(ac, id_enlace, df_dat)
        ui_c_norec = _norec_ui_pd(ac, id_enlace, df_sum)
        is_c_norec = _norec_seg_pd(ac, ui_c_norec, np_c, id_enlace, df_sum)
        ui_c_noval = _noval_ui_pd(ac, id_enlace, df_sum)
        is_c_noval = _noval_seg_pd(ac, ui_c_noval, np_c, id_enlace, df_sum)

        is_datos_norm = is_c_norec + is_c_noval
        is_c_mant = _mant_seg_pd(ac, np_c, id_enlace, df_sum)
        is_datos_mant = is_c_mant

        def pct(num, den): return f"   ( {num/den*100:.2f} % )" if den else ""
        prc = pct(gl_rec, gl_esp)
        pbc = pct(gl_bue, gl_esp)
        pmc = pct(gl_man, gl_esp)
        pnrc = pct(ui_c_norec, gl_esp)
        pnvc = pct(ui_c_noval, gl_esp)

    is_total_norm = is_cortes_norm + is_datos_norm
    is_total_mant = is_cortes_mant + is_datos_mant

    ultimo_dia = (fin - timedelta(seconds=1)).strftime('%d/%m/%Y')
    intervalo_str = f"{ini.strftime('%d/%m/%Y')} al {ultimo_dia}"

    t = ""
    t += f"Indisponibilidad del SOTR ICCP - ENLACE: {enlace_name}\n"
    t += f"Reporte generado en {fecha_hoy}\n"
    t += "(C) Copyright 2012 BLC S.A.\n\n"
    t += f"Intervalo considerado: {intervalo_str}\n\n"
    t += f"1) Cortes de las asociaciones en el enlace {enlace_name}\n\n"
    t += f"No se indican cortes de menos de {tol_c} segundos.\n\n"
    t += _obtener_cortes_pd(id_enlace, tol_c, ac, ab, df_cortes)
    t += "\n"
    t += f"Resultados del enlace {enlace_name}\n\n"
    t += "Cantidad de cortes\n"
    t += "Ordinarios\n"
    t += (f" * Asoc. Cliente (C)   :{_completar(str(_cant_cortes_pd(ac,0,tol_c,id_enlace,False,df_cortes)), 6)}"
          f"   ( {_cant_cortes_pd(ac,0,tol_c,id_enlace,True,df_cortes)} exceden {tol_c} seg )\n")
    t += (f" * Asoc. Servidor (S)  :{_completar(str(_cant_cortes_pd(ab,0,tol_c,id_enlace,False,df_cortes)), 6)}"
          f"   ( {_cant_cortes_pd(ab,0,tol_c,id_enlace,True,df_cortes)} exceden {tol_c} seg )\n")
    t += "Por Mantenimiento\n"
    t += f" * Asoc. Cliente (C)   :{_completar(str(_cant_cortes_pd(ac,1,tol_c,id_enlace,False,df_cortes)), 6)}\n"
    t += f" * Asoc. Servidor (S)  :{_completar(str(_cant_cortes_pd(ab,1,tol_c,id_enlace,False,df_cortes)), 6)}\n\n"
    t += "Tiempos de indisponibilidad\n"
    t += "Ordinaria Bruta\n"
    t += f" * Asoc. Cliente (C)   :{_completar(str(bruta_c), 11)} seg   ( {seg_to_hms(bruta_c)} )\n"
    t += f" * Asoc. Servidor (S)  :{_completar(str(bruta_s), 11)} seg   ( {seg_to_hms(bruta_s)} )\n"
    t += "Ordinaria Neta\n"
    t += f" * Asoc. Cliente (C)   :{_completar(str(int(isc_norm)), 11)} seg   ( {seg_to_hms(isc_norm)} )\n"
    t += f" * Asoc. Servidor (S)  :{_completar(str(int(iss_norm)), 11)} seg   ( {seg_to_hms(iss_norm)} )\n"
    t += f" * Promedio Neto       :{_completar(str(round(is_cortes_norm)), 11)} seg   ( {seg_to_hms(round(is_cortes_norm))} )\n\n"
    t += "Por Mantenimiento:\n"
    t += f" * Asoc. Cliente (C)   :{_completar(str(int(isc_mant)), 11)} seg   ( {seg_to_hms(isc_mant)} )\n"
    t += f" * Asoc. Servidor (S)  :{_completar(str(int(iss_mant)), 11)} seg   ( {seg_to_hms(iss_mant)} )\n"
    t += f" * Promedio Mant.      :{_completar(str(round(is_cortes_mant)), 11)} seg   ( {seg_to_hms(round(is_cortes_mant))} )\n\n"
    t += f"En la indisponibilidad neta y por mantenimiento, no se incluyen cortes de menos\n"
    t += f"de {tol_c} seg. En los cortes mayores, se deducen {tol_c} seg.\n\n"
    t += "En estos promedios se consideraron los siguientes volumenes de información:\n"
    t += f"{_completar(f'{vi_ct:.3f}', 10)} u.i - asociación cliente (C)\n"
    t += f"{_completar(f'{vi_st:.3f}', 10)} u.i - asociación servidor (S)\n"
    t += "\n*****************************************************************\n\n"
    t += f"2) Indisponibilidad por calidad de datos para el enlace {enlace_name}\n\n"
    if vi_total > 0:
        t += " Computada solamente en períodos normales\n"
        t += f" Tolerancia para datos no recibidos: {tol_d}%\n"
        t += f" Tolerancia para datos inválidos   : {tol_d}%\n\n"
        t += "Estadísticas\n\n"
        t += f"Datos transmitidos (Dir=tx) sobre {np_c} períodos.\n"
        t += f"  Esperados                  :{_completar(str(int(gl_esp)), 11)}\n"
        t += f"  Recibidos                  :{_completar(str(int(gl_rec)), 11)}{prc}\n"
        t += f"  Buenos                     :{_completar(str(int(gl_bue)), 11)}{pbc}\n"
        t += f"  Manuales                   :{_completar(str(int(gl_man)), 11)}{pmc}\n\n"
        t += f"  Vol. Info no recibidos     :{_completar(f'{ui_c_norec:.2f}', 11)} ui{pnrc}\n"
        t += f"  Vol. Info Inválidos        :{_completar(f'{ui_c_noval:.2f}', 11)} ui{pnvc}\n\n"
        t += "Indisponibilidades por calidad de datos\n"
        t += "  * Indisponibilidad por datos no recibidos:\n"
        t += f"{_completar(str(round(is_c_norec)), 21)} seg   ( {seg_to_hms(round(is_c_norec))} )\n"
        t += "  * Indisponibilidad por datos inválidos:\n"
        t += f"{_completar(str(round(is_c_noval)), 21)} seg   ( {seg_to_hms(round(is_c_noval))} )\n\n"
        t += "* Indisponibilidad promedio datos no recibidos e inválidos\n"
        t += f"{_completar(str(round(is_datos_norm)), 21)} seg   ( {seg_to_hms(round(is_datos_norm))} )\n\n"
        t += "Indisponibilidades por mantenimientos programados\n"
        t += f"  * Datos tx       :{_completar(str(round(is_c_mant)), 12)} seg   ( {seg_to_hms(round(is_c_mant))} )\n\n"
        t += "En estos promedios se consideraron los siguientes volumenes de información:\n"
        t += f"{_completar(f'{vi_c:.3f}', 10)} u.i - datos transmitidos (Dir=tx)\n\n"
    else:
        t += "Sin datos .dat disponibles para este período.\n\n"
    t += "=================================================================\n\n"
    t += "Resumen de resultados\n\n"
    t += f"* Indisponibilidad en el período (total por cortes de enlace y calidad de datos) de {enlace_name}\n"
    t += f"{_completar(str(round(is_total_norm)), 21)} seg   ( {seg_to_hms(round(is_total_norm))} )\n\n"
    t += f"* Mantenimientos en el período (total por cortes de enlace y calidad de datos) de {enlace_name}\n"
    t += f"{_completar(str(round(is_total_mant)), 21)} seg   ( {seg_to_hms(round(is_total_mant))} )\n\n"
    t += "=================================================================\n"

    valores = {
        "enlace_nombre": enlace_name,
        "bruta_c": bruta_c, "bruta_s": bruta_s,
        "neta_c": isc_norm, "neta_s": iss_norm,
        "promedio_neto": is_cortes_norm,
        "ind_datos_norm": is_datos_norm,
        "ind_datos_mant": is_datos_mant,
        "ind_total_norm": is_total_norm,
        "ind_total_mant": is_total_mant,
    }
    return t, valores


# ─── Cálculo por central ICCP ─────────────────────────────────────────────────

def _get_link_events_iccp(id_enlace: int, col: str, ini: datetime, fin: datetime,
                           db: Session) -> list[tuple[datetime, str]]:
    """Eventos i+/e+ de con_iccp para el enlace. col: 'c_state' o 's_state'."""
    rows = db.execute(
        text(f"""SELECT fecha, {col} FROM con_iccp
                 WHERE id_enlace=:e AND fecha>=:ini AND fecha<=:fin AND {col} IN ('i+','e+')
                 ORDER BY fecha"""),
        {"e": id_enlace, "ini": ini, "fin": fin}
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _construir_timeline_tipo2_iccp(id_prim: int, id_bck: int,
                                    ini: datetime, fin: datetime,
                                    db: Session):
    """Timeline tipo 2 ICCP — usa c_state para determinar UP/DOWN."""
    col = "c_state"

    prim_up = _estado_inicial_iccp(id_prim, col, ini, db)
    bck_up = _estado_inicial_iccp(id_bck, col, ini, db)

    events = []
    for ev_time, ev_state in _get_link_events_iccp(id_prim, col, ini, fin, db):
        events.append((ev_time, "prim", ev_state == "e+"))
    for ev_time, ev_state in _get_link_events_iccp(id_bck, col, ini, fin, db):
        events.append((ev_time, "bck", ev_state == "e+"))
    events.sort(key=lambda x: x[0])

    def _estado(p, b):
        if p and b: return "ambos"
        if p: return "prim"
        if b: return "bck"
        return "ninguno"

    segments = []
    inconsistencias = []
    current_t = ini
    current_estado = _estado(prim_up, bck_up)

    for t, link, is_up in events:
        if t > current_t:
            segments.append({
                "inicio": current_t, "fin": t,
                "estado": current_estado,
                "dur_seg": (t - current_t).total_seconds(),
            })
        if link == "prim":
            prim_up = is_up
        else:
            bck_up = is_up
        new_estado = _estado(prim_up, bck_up)
        current_t = t
        current_estado = new_estado

    if current_t < fin:
        segments.append({
            "inicio": current_t, "fin": fin,
            "estado": current_estado,
            "dur_seg": (fin - current_t).total_seconds(),
        })

    cortes_ef = [
        {"inicio": s["inicio"], "fin": s["fin"], "dur_seg": s["dur_seg"]}
        for s in segments if s["estado"] == "ninguno"
    ]
    corte_ef_seg = sum(c["dur_seg"] for c in cortes_ef)

    return segments, cortes_ef, inconsistencias, corte_ef_seg


def _calcular_tipo2_iccp(id_prim: int, id_bck: int, ini: datetime, fin: datetime,
                          db: Session) -> tuple[float, bool]:
    """Calcula indisponibilidad total para central ICCP tipo 2."""
    tol_c = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)
    segments, cortes_ef, inconsistencias, corte_ef_seg = \
        _construir_timeline_tipo2_iccp(id_prim, id_bck, ini, fin, db)

    corte_ef_seg_neto = sum(max(0.0, c["dur_seg"] - tol_c) for c in cortes_ef)

    prim_active = sum(s["dur_seg"] for s in segments if s["estado"] == "prim")
    bck_active = sum(s["dur_seg"] for s in segments if s["estado"] == "bck")
    total_active = prim_active + bck_active
    prim_frac = prim_active / total_active if total_active > 0 else 0.0
    bck_frac = bck_active / total_active if total_active > 0 else 0.0

    _, valores_prim, _ = _procesar_enlace_iccp(id_prim, ini, fin, db)
    _, valores_bck, _ = _procesar_enlace_iccp(id_bck, ini, fin, db)
    ind_datos_prim = float(valores_prim.get("ind_datos_norm", 0.0)) if valores_prim else 0.0
    ind_datos_bck = float(valores_bck.get("ind_datos_norm", 0.0)) if valores_bck else 0.0
    ind_datos_seg = ind_datos_prim * prim_frac + ind_datos_bck * bck_frac
    ind_total_seg = corte_ef_seg_neto + ind_datos_seg

    return ind_total_seg, len(inconsistencias) > 0


def calcular_ind_central_iccp(id_central: int, ini: datetime, fin: datetime,
                               db: Session) -> tuple[float | None, bool]:
    """Dispatcher ICCP por tipo de central."""
    row = db.execute(
        text("SELECT nemo, tipo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central}
    ).fetchone()
    if not row:
        return None, False
    nemo, tipo = row

    if tipo == 1:
        id_e = _get_enlace_directo(id_central, db)
        if not id_e:
            return None, False
        _, valores, _ = _procesar_enlace_iccp(id_e, ini, fin, db)
        if not valores:
            return 0.0, False
        return float(valores.get("ind_total_norm", 0.0)), False

    if tipo == 3:
        id_e = _get_enlace_backup_bcog(id_central, db)
        if not id_e:
            return None, False
        _, valores, _ = _procesar_enlace_iccp(id_e, ini, fin, db)
        if not valores:
            return 0.0, False
        return float(valores.get("ind_total_norm", 0.0)), False

    if tipo == 2:
        id_prim = _get_enlace_directo(id_central, db)
        id_bck = _get_enlace_backup_bcog(id_central, db)
        if not id_prim or not id_bck:
            return None, False
        return _calcular_tipo2_iccp(id_prim, id_bck, ini, fin, db)

    return None, False


# ─── Detalle on-the-fly ICCP ──────────────────────────────────────────────────

def detalle_central_iccp(id_central: int, ini: datetime, fin: datetime,
                          db: Session) -> dict:
    """Detalle completo de un día para una central ICCP."""
    row = db.execute(
        text("SELECT id, nemo, tipo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central}
    ).fetchone()
    if not row:
        return {}
    c_id, nemo, tipo = row
    tol_c = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)

    def _eventos_enlace(id_e: int) -> list[dict]:
        rows_c = _get_link_events_iccp(id_e, "c_state", ini, fin, db)
        rows_s = _get_link_events_iccp(id_e, "s_state", ini, fin, db)
        eventos = [{"t": r[0].isoformat(), "tipo": r[1], "asoc": "C"} for r in rows_c]
        eventos += [{"t": r[0].isoformat(), "tipo": r[1], "asoc": "S"} for r in rows_s]
        eventos.sort(key=lambda x: x["t"])
        return eventos

    def _periodos_dat(id_e: int) -> dict[str, dict]:
        df = _procesar_datos_dat_iccp(ini, fin, id_e, db)
        if df.empty:
            return {}
        result: dict[str, dict] = {}
        for _, r in df.iterrows():
            key = pd.Timestamp(r["fecha"]).isoformat()
            result.setdefault(key, {
                "esperados": 0.0, "recibidos": 0.0, "buenos": 0.0,
                "norecibidos": 0.0, "invalidos": 0.0,
                "ui_norec": 0.0, "ui_noval": 0.0,
            })
            result[key]["esperados"] += float(r.get("esperados", 0) or 0)
            result[key]["recibidos"] += float(r.get("recibidos", 0) or 0)
            result[key]["buenos"] += float(r.get("buenos", 0) or 0)
            result[key]["norecibidos"] += float(r.get("norecibidos", 0) or 0)
            result[key]["invalidos"] += float(r.get("invalidos", 0) or 0)
            result[key]["ui_norec"] += float(r.get("ui_norecibidas", 0) or 0)
            result[key]["ui_noval"] += float(r.get("ui_invalidas", 0) or 0)
        return result

    # ─── Tipo 1 / Tipo 3 ─────────────────────────────────────────────
    if tipo in (1, 3):
        id_e = _get_enlace_directo(id_central, db) if tipo == 1 else _get_enlace_backup_bcog(id_central, db)
        if not id_e:
            return {"central": nemo, "tipo": tipo, "error": "Enlace no encontrado"}

        _, valores, df_cortes = _procesar_enlace_iccp(id_e, ini, fin, db)
        eventos = _eventos_enlace(id_e)

        # Timeline usando c_state
        col = "c_state"
        up_ini = _estado_inicial_iccp(id_e, col, ini, db)
        raw_ev = _get_link_events_iccp(id_e, col, ini, fin, db)
        segs: list[dict] = []
        cur_t, cur_up = ini, up_ini
        for t, ev in raw_ev:
            segs.append({"inicio": cur_t.isoformat(), "fin": t.isoformat(),
                         "estado": "up" if cur_up else "down",
                         "dur_seg": (t - cur_t).total_seconds()})
            cur_up = (ev == "e+")
            cur_t = t
        segs.append({"inicio": cur_t.isoformat(), "fin": fin.isoformat(),
                     "estado": "up" if cur_up else "down",
                     "dur_seg": (fin - cur_t).total_seconds()})

        nombre_e = db.execute(
            text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_e}
        ).scalar() or str(id_e)
        cortes = [
            {"enlace": nombre_e, "inicio": s["inicio"], "fin": s["fin"],
             "dur_seg": s["dur_seg"], "bajo_tolerancia": s["dur_seg"] < tol_c}
            for s in segs if s["estado"] == "down"
        ]

        periodos = [{"intervalo_fin": k, "enlace": "unico", **v}
                    for k, v in sorted(_periodos_dat(id_e).items())]

        return {
            "central": nemo, "tipo": tipo,
            "ind_total_seg": float(valores.get("ind_total_norm", 0.0)) if valores else 0.0,
            "inconsistencias": [],
            "segments": segs,
            "cortes_efectivos": cortes,
            "periodos_dat": periodos,
        }

    # ─── Tipo 2 ───────────────────────────────────────────────────────
    id_prim = _get_enlace_directo(id_central, db)
    id_bck = _get_enlace_backup_bcog(id_central, db)
    if not id_prim or not id_bck:
        return {"central": nemo, "tipo": tipo, "error": "Faltan enlaces"}

    segments, cortes_ef, inconsistencias, corte_ef_seg = \
        _construir_timeline_tipo2_iccp(id_prim, id_bck, ini, fin, db)

    segments_out = [{**s, "inicio": s["inicio"].isoformat(), "fin": s["fin"].isoformat()} for s in segments]

    nombre_prim = db.execute(text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_prim}).scalar() or "Directo"
    nombre_bck = db.execute(text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_bck}).scalar() or "Backup"

    def _merge_link_cortes(nombre, estados_down):
        result, cur = [], None
        for seg in segments_out:
            if seg["estado"] in estados_down:
                if cur is None:
                    cur = {"enlace": nombre, "inicio": seg["inicio"], "fin": seg["fin"], "dur_seg": seg["dur_seg"]}
                else:
                    cur["fin"] = seg["fin"]; cur["dur_seg"] += seg["dur_seg"]
            else:
                if cur is not None:
                    result.append(cur); cur = None
        if cur is not None:
            result.append(cur)
        return result

    def _con_tol(c): return {**c, "bajo_tolerancia": c["dur_seg"] < tol_c}

    cortes_individuales = sorted(
        [_con_tol(c) for c in _merge_link_cortes(nombre_prim, {"bck", "ninguno"})] +
        [_con_tol(c) for c in _merge_link_cortes(nombre_bck, {"prim", "ninguno"})],
        key=lambda x: x["inicio"]
    )
    cortes_efectivos_merged = [
        {"enlace": "Sin cobertura", "inicio": c["inicio"].isoformat(), "fin": c["fin"].isoformat(),
         "dur_seg": c["dur_seg"], "bajo_tolerancia": c["dur_seg"] < tol_c}
        for c in cortes_ef
    ]
    cortes_out = cortes_individuales + cortes_efectivos_merged

    corte_ef_seg_neto = sum(max(0.0, c["dur_seg"] - tol_c) for c in cortes_ef)

    prim_active = sum(s["dur_seg"] for s in segments if s["estado"] == "prim")
    bck_active = sum(s["dur_seg"] for s in segments if s["estado"] == "bck")
    total_active = prim_active + bck_active
    prim_frac = prim_active / total_active if total_active > 0 else 0.0
    bck_frac = bck_active / total_active if total_active > 0 else 0.0

    _, valores_prim, _ = _procesar_enlace_iccp(id_prim, ini, fin, db)
    _, valores_bck, _ = _procesar_enlace_iccp(id_bck, ini, fin, db)
    ind_datos_prim = float(valores_prim.get("ind_datos_norm", 0.0)) if valores_prim else 0.0
    ind_datos_bck = float(valores_bck.get("ind_datos_norm", 0.0)) if valores_bck else 0.0
    ind_datos_seg = ind_datos_prim * prim_frac + ind_datos_bck * bck_frac
    ind_total_seg = corte_ef_seg_neto + ind_datos_seg

    dat_prim = _periodos_dat(id_prim)
    dat_bck = _periodos_dat(id_bck)
    all_fechas = sorted(set(dat_prim.keys()) | set(dat_bck.keys()))

    periodos_lista = []
    for k in all_fechas:
        p_end = datetime.fromisoformat(k)
        p_start = p_end - timedelta(minutes=30)
        frac_p, frac_b = _fracciones_periodo(p_start, p_end, segments)
        frac_gap = max(0.0, 1.0 - frac_p - frac_b)

        def _w(d, f): return {key: val * f for key, val in d.items()} if d else {}
        prim_w = _w(dat_prim.get(k, {}), frac_p)
        bck_w = _w(dat_bck.get(k, {}), frac_b)
        combined = {}
        for campo in ("esperados", "recibidos", "buenos", "norecibidos", "invalidos", "ui_norec", "ui_noval"):
            combined[campo] = prim_w.get(campo, 0.0) + bck_w.get(campo, 0.0)

        tipo_periodo = "excluido" if frac_gap > 0 else "normal"
        periodos_lista.append({
            "intervalo_fin": k, "prim_pct": round(frac_p * 100, 1),
            "bck_pct": round(frac_b * 100, 1), "gap_pct": round(frac_gap * 100, 1),
            "tipo_periodo": tipo_periodo, **combined,
        })

    return {
        "central": nemo, "tipo": tipo,
        "ind_total_seg": ind_total_seg,
        "corte_efectivo_seg": corte_ef_seg_neto,
        "ind_datos_seg": ind_datos_seg,
        "inconsistencias": [
            {**inc, "t1": inc["t1"].isoformat(), "t2": inc["t2"].isoformat()}
            for inc in inconsistencias
        ] if inconsistencias else [],
        "segments": segments_out,
        "cortes_efectivos": cortes_out,
        "eventos_prim": _eventos_enlace(id_prim),
        "eventos_bck": _eventos_enlace(id_bck),
        "periodos_dat": periodos_lista,
    }
