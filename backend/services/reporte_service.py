"""
Servicio de cálculo de indisponibilidad.
Migrado desde Ignition (Reporte/Funciones). Genera el TXT en formato SOTR ENARSA.
Pipeline de cálculo usa pandas en memoria (sin tablas temporales MySQL).
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import models
import schemas

_AR_TZ = timezone(timedelta(hours=-3))


def _a_hora_local(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(_AR_TZ).replace(tzinfo=None)
    return dt


# ─── Helpers ─────────────────────────────────────────────────────────────────

def seg_to_hms(seg) -> str:
    seg = int(seg)
    h = seg // 3600
    m = (seg % 3600) // 60
    s = seg % 60
    return f"{h}H {m}M {s}S"


def _completar(val: str, largo: int) -> str:
    return str(val).rjust(largo)


def _es_directo(id_enlace: int, db: Session) -> bool:
    """Retorna True si el enlace es directo (prefijo A), False si es concentrador (prefijo B).

    Lógica de detección:
    - idtipo=2 → siempre prefijo A (directo)
    - idtipo=3 → siempre prefijo B (concentrador)
    - idtipo=NULL → auto-detecta contando eventos reales en la tabla con:
        si BC tiene más eventos que AC → prefijo B
        si AC tiene más eventos → prefijo A
        si empate → usa campo rol como fallback
    """
    row = db.execute(
        text("SELECT idtipo, rol FROM enlaces WHERE id=:id LIMIT 1"),
        {"id": id_enlace}
    ).fetchone()
    if not row:
        return False
    idtipo, rol = row
    if idtipo == 2:
        return True
    if idtipo == 3:
        return False
    # idtipo=NULL: auto-detectar por eventos reales en la tabla con
    has_ac = db.execute(
        text("SELECT COUNT(*) FROM con WHERE id_enlace=:e AND asoc_ac IN ('i+','e+')"),
        {"e": id_enlace}
    ).scalar() or 0
    has_bc = db.execute(
        text("SELECT COUNT(*) FROM con WHERE id_enlace=:e AND asoc_bc IN ('i+','e+')"),
        {"e": id_enlace}
    ).scalar() or 0
    if has_bc > has_ac:
        return False
    if has_ac > has_bc:
        return True
    # Sin datos en con: usar campo rol como fallback
    return rol == "directo"


def _nombre_asoc(caracter: str, id_enlace: int, db: Session) -> str:
    prefix = "A" if _es_directo(id_enlace, db) else "B"
    return prefix + caracter.upper()


def _asoc_col(asoc: str) -> str:
    return asoc.lower()


# Pesos por tipo de grupo — extraídos del VB6 original.
_PESO_POR_TIPO: dict[int, float] = {
    1: 1.0,
    2: 0.0,
    3: 0.25,
    4: 0.125,
    5: 0.125,
    7: 0.0,
}

# Tipo por defecto según número de grupo (VB6 hardcoded defaults).
# Si la tabla `grupos` tiene tipo=0 para alguno de estos grupos, se usa este default.
_TIPO_DEFAULT_POR_GRUPO: dict[int, int] = {
    1: 1,
    3: 3,
    5: 5,
    71: 7,
    81: 7,
    710: 7,
    810: 7,
}


def _peso_grupo(tipo: int) -> float:
    return _PESO_POR_TIPO.get(int(tipo), 0.0)


# ─── Pipeline pandas ─────────────────────────────────────────────────────────

def _procesar_datos_dat_pd(ini: datetime, fin: datetime,
                            id_enlace: int, db: Session) -> pd.DataFrame:
    """Lee dat + grupos en bulk (sin N+1), retorna df_dat."""
    ini_adj = ini + timedelta(minutes=1)
    fin_adj = fin + timedelta(minutes=1)

    nombre_agente = db.execute(
        text("""SELECT CASE WHEN UPPER(c.nemo) != 'BCOG' THEN CONCAT(c.nemo,'_CAMM') ELSE e.nombre END
                FROM centrales c LEFT JOIN enlaces e ON c.id=e.idcentral
                WHERE e.id=:e LIMIT 1"""),
        {"e": id_enlace}
    ).scalar()

    tol_datos = float(db.execute(
        text("SELECT tol_datos FROM configuracion LIMIT 1")
    ).scalar() or 2)

    prefix = "A" if _es_directo(id_enlace, db) else "B"
    asoc_b = prefix + "B"
    asoc_c = prefix + "C"

    try:
        rows = db.execute(
            text("""SELECT id, fecha, id_gr, gr_grupo, siz, t, g, h, c, e, m, i, exp, freq, st
                    FROM dat WHERE id_enlace=:e AND fecha>:ini AND fecha<=:fin"""),
            {"e": id_enlace, "ini": ini_adj, "fin": fin_adj}
        ).fetchall()
    except Exception:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    # Cargar todos los grupos en una sola query (elimina N+1)
    try:
        grupos_rows = db.execute(
            text("SELECT grupo, tipo, calcular FROM grupos WHERE idenlace=:e"),
            {"e": id_enlace}
        ).fetchall()
    except Exception:
        grupos_rows = []
    grupos_dict = {r[0]: {"tipo": r[1], "calcular": r[2]} for r in grupos_rows}

    records = []
    for row in rows:
        _, fecha, id_gr, grupo, nobj, rec, bue, cong, calc, est, man, inv, exp, freq, st = row

        gr_data = grupos_dict.get(grupo)
        if not gr_data:
            continue
        if gr_data["calcular"] != 1 or id_gr != 'R':
            continue
        tipo = int(gr_data["tipo"])
        if tipo == 0:
            tipo = _TIPO_DEFAULT_POR_GRUPO.get(grupo, 0)

        ui = _peso_grupo(tipo)

        if freq is None:
            asoc = asoc_b
            n_chq = int(st or 0)
            esperados = float(n_chq * nobj)
        else:
            asoc = asoc_c
            n_chq = 0
            esperados = float(exp or 0)

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
            "idenlace": id_enlace,
            "agente": nombre_agente,
            "subagente": nombre_agente,
            "ui_norec_netas": (n_norec - tol) * ui,
            "ui_inv_netas": (n_inval - tol) * ui,
            "ui_ind_mant_perm": 0.0,
        })

    return pd.DataFrame(records)


def _procesar_corte_asoc_pd(asoc: str, ini: datetime, fin: datetime,
                              id_enlace: int, tol: int,
                              df_dat: pd.DataFrame, db: Session) -> list[dict]:
    """Detecta cortes y retorna lista de dicts (sin escribir en cortes_aux)."""
    asoc_up = asoc.upper()
    col = _asoc_col(asoc)
    EV_CAIDA, EV_ESTAB, EV_MANT_INI, EV_MANT_FIN = 1, 2, 3, 4

    # Reemplaza las queries a dat_aux (tabla temporal ya no usada) con df_dat
    if not df_dat.empty:
        mask_asoc = (df_dat["asoc"] == asoc_up) & (df_dat["idenlace"] == id_enlace)
        hay = bool((mask_asoc & (df_dat["recibidos"] != 0)).any())
        fechas_asoc = df_dat.loc[mask_asoc, "fecha"]
        fecha_max = fechas_asoc.max() if not fechas_asoc.empty else None
        if fecha_max is not None and hasattr(fecha_max, "to_pydatetime"):
            fecha_max = fecha_max.to_pydatetime()
    else:
        hay = False
        fecha_max = None

    try:
        rows = db.execute(
            text(f"""SELECT fecha, id_enlace, id_sotr, CAST({col} AS SIGNED)
                     FROM vista_asoc_con1
                     WHERE fecha>=:ini AND fecha<:fin AND id_enlace=:e AND {col} IS NOT NULL
                     ORDER BY fecha ASC"""),
            {"ini": ini, "fin": fin, "e": id_enlace}
        ).fetchall()
    except Exception:
        rows = []

    data = []

    if rows:
        estado = 0
        for row in rows:
            fecha_ev = row[0]
            if isinstance(fecha_ev, str):
                fecha_ev = datetime.fromisoformat(fecha_ev)
            ev = int(row[3]) if row[3] is not None else -1

            if estado == 0:
                if ev == EV_CAIDA:
                    data.append((asoc_up, EV_CAIDA, fecha_ev, id_enlace, 0))
                    estado = 1
                elif ev == EV_ESTAB:
                    data.append((asoc_up, EV_CAIDA, ini, id_enlace, 1))
                    data.append((asoc_up, EV_ESTAB, fecha_ev, id_enlace, 1))
                    estado = 2
            elif estado == 1:
                if ev == EV_ESTAB:
                    data.append((asoc_up, EV_ESTAB, fecha_ev, id_enlace, 0))
                    estado = 2
            elif estado == 2:
                if ev == EV_CAIDA:
                    data.append((asoc_up, EV_CAIDA, fecha_ev, id_enlace, 0))
                    estado = 1

        fin_dia = fin - timedelta(seconds=1)
        if estado == 0:
            data.append((asoc_up, EV_CAIDA, ini, id_enlace, 0))
            data.append((asoc_up, EV_ESTAB, fin_dia, id_enlace, 0))
        elif estado == 1:
            data.append((asoc_up, EV_ESTAB, fin_dia, id_enlace, 0))
    else:
        fin_dia = fin - timedelta(seconds=1)
        if hay and fecha_max:
            if isinstance(fecha_max, str):
                fecha_max = datetime.fromisoformat(fecha_max)
            if fecha_max >= fin:
                t_caida = fin_dia
            else:
                t_caida = fecha_max
            data.append((asoc_up, EV_CAIDA, t_caida, id_enlace, 1))
            data.append((asoc_up, EV_ESTAB, fin_dia, id_enlace, 1))
        else:
            data.append((asoc_up, EV_CAIDA, fin_dia, id_enlace, 1))
            data.append((asoc_up, EV_ESTAB, fin_dia, id_enlace, 1))

    # Mantenimientos
    mantenimientos = db.execute(
        text("""SELECT inicio, fin, idenlace FROM mantenimientos
                WHERE idenlace=:e AND inicio>:ini AND fin<:fin"""),
        {"e": id_enlace, "ini": ini, "fin": fin}
    ).fetchall()
    for mant in mantenimientos:
        mi = mant[0] if isinstance(mant[0], datetime) else datetime.fromisoformat(str(mant[0]))
        mf = mant[1] if isinstance(mant[1], datetime) else datetime.fromisoformat(str(mant[1]))
        data.append((asoc_up, EV_MANT_INI, mi, id_enlace, 0))
        data.append((asoc_up, EV_MANT_FIN, mf, id_enlace, 0))

    data.sort(key=lambda x: x[2])

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
                cortes.append(_make_corte(SM_T1, fecha, asoc_up, id_enlace, 1, tol))
                SM = 1
            elif ev == EV_MANT_FIN:
                cortes.append(_make_corte(SM_T1, fecha, asoc_up, id_enlace, 1, tol))
                SM_T1 = fecha; SM = 3
        elif SM == 3:
            if ev == EV_ESTAB:
                cortes.append(_make_corte(SM_T1, fecha, asoc_up, id_enlace, 0, tol))
                SM = 0
            elif ev == EV_MANT_INI:
                cortes.append(_make_corte(SM_T1, fecha, asoc_up, id_enlace, 0, tol))
                SM_T1 = fecha; SM = 2

    return cortes


def _make_corte(t1: datetime, t2: datetime, asoc: str, id_enlace: int,
                es_mant: int, tol: int) -> dict:
    bruta = int((t2 - t1).total_seconds())
    neta = max(0, bruta - tol)
    return {"inicio": t1, "fin": t2, "idenlace": id_enlace,
            "asoc": asoc, "ind_bruta": bruta, "ind_neta": neta, "tipo": es_mant}


def _update_excluidos_pd(df_dat: pd.DataFrame,
                          df_cortes: pd.DataFrame) -> pd.DataFrame:
    if df_cortes.empty or df_dat.empty:
        return df_dat
    df_dat = df_dat.copy()
    df_dat["fecha"] = pd.to_datetime(df_dat["fecha"])
    for _, row in df_cortes.iterrows():
        ini = pd.Timestamp(row["inicio"])
        fin = pd.Timestamp(row["fin"])
        e = row["idenlace"]
        if fin.minute % 30 == 0 and fin.second == 0:
            mask = (df_dat["idenlace"] == e) & (df_dat["fecha"] > ini) & (df_dat["fecha"] < fin)
        else:
            mask = (df_dat["idenlace"] == e) & (df_dat["fecha"] > ini) & (df_dat["fecha"] <= fin)
        df_dat.loc[mask, "analizar"] = 0
    return df_dat


def _misc1_pd(df_dat: pd.DataFrame) -> pd.DataFrame:
    df = df_dat.copy()
    diff = df["ui_norecibidas"] - df["ui_ind_mant_perm"]
    df["ui_norec_norm"] = 0.0
    df.loc[diff >= 0, "ui_norec_norm"] = diff[diff >= 0]

    cond_gt = df["ui_ind_mant_perm"] > df["ui_norecibidas"]
    expr = df["ui_invalidas"] - (df["ui_ind_mant_perm"] - df["ui_norecibidas"])
    df["ui_inv_norm"] = 0.0
    df.loc[cond_gt & (expr > 0), "ui_inv_norm"] = expr[cond_gt & (expr > 0)]
    df.loc[cond_gt & (expr <= 0), "ui_inv_norm"] = 0.0
    df.loc[~cond_gt, "ui_inv_norm"] = df.loc[~cond_gt, "ui_invalidas"]

    mask_esp = df["ui_esperadas"] != 0
    df["por_inv_esp"] = 0.0
    df["por_norec_esp"] = 0.0
    df.loc[mask_esp, "por_inv_esp"] = df.loc[mask_esp, "ui_inv_norm"] / df.loc[mask_esp, "ui_esperadas"]
    df.loc[mask_esp, "por_norec_esp"] = df.loc[mask_esp, "ui_norec_norm"] / df.loc[mask_esp, "ui_esperadas"]
    return df


def _sumas_parciales_pd(df_dat: pd.DataFrame) -> pd.DataFrame:
    mask = (df_dat["analizar"] == 1) & df_dat["asoc"].isin(["BC", "BB", "AC", "AB"])
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

    for col in ["sum_ui_ind_tot", "sum_ui_norec_norm", "sum_ui_inv_norm",
                "sum_ui_norec_mant", "sum_ui_inv_mant", "sum_ui_ind_norm",
                "sum_ui_ind_mant", "sum_seg_ind_norm", "sum_seg_ind_mant"]:
        df_sum[col] = 0.0

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


def _misc2_pd(df_dat: pd.DataFrame, df_sum: pd.DataFrame,
              ac: str, ab: str) -> pd.DataFrame:
    if df_dat.empty or df_sum.empty:
        return df_dat

    df = df_dat.copy()
    join_cols = ["fecha", "agente", "asoc"]
    sum_map_cols = ["sum_por_norec_esp", "sum_por_inv_esp", "sum_ui_norec_netas",
                    "sum_ui_inv_netas", "sum_ui_ind_tot", "sum_ui_ind_mant_perm",
                    "sum_seg_ind_norm", "sum_seg_ind_mant",
                    "sum_ui_norec_norm_ag", "sum_ui_inv_norm_ag"]

    for col in sum_map_cols:
        df[col] = 0.0

    mask = df["analizar"] == 1
    if mask.any():
        merged = df.loc[mask, join_cols].merge(
            df_sum[join_cols + sum_map_cols], on=join_cols, how="left"
        )
        for col in sum_map_cols:
            vals = merged[col].values if col in merged.columns else 0.0
            df.loc[mask, col] = vals

    df["por_norec"] = 0.0
    m = df["sum_por_norec_esp"] > 0
    df.loc[m, "por_norec"] = df.loc[m, "por_norec_esp"] / df.loc[m, "sum_por_norec_esp"]

    df["por_inv"] = 0.0
    m = df["sum_por_inv_esp"] > 0
    df.loc[m, "por_inv"] = df.loc[m, "por_inv_esp"] / df.loc[m, "sum_por_inv_esp"]

    df["ind_norec_norm"] = 0.0
    m = df["sum_ui_norec_norm_ag"] != 0
    df.loc[m, "ind_norec_norm"] = df.loc[m, "por_norec"] * df.loc[m, "sum_ui_norec_norm_ag"]

    df["ind_inv_norm"] = 0.0
    m = df["sum_ui_inv_norm_ag"] != 0
    df.loc[m, "ind_inv_norm"] = df.loc[m, "por_inv"] * df.loc[m, "sum_ui_inv_norm_ag"]

    df["ind_norm"] = df["ind_norec_norm"] + df["ind_inv_norm"]

    # sum_ind_norm por grupo (equivale a dat_aux_sum_aux)
    df_sum_aux = df.groupby(["fecha", "idenlace", "agente", "asoc"])["ind_norm"].sum().reset_index()
    df_sum_aux.rename(columns={"ind_norm": "sum_ind_norm_"}, inplace=True)

    df["sum_ind_norm"] = 0.0
    mask = df["analizar"] == 1
    if mask.any():
        merged2 = df.loc[mask, ["fecha", "idenlace", "agente", "asoc"]].merge(
            df_sum_aux, on=["fecha", "idenlace", "agente", "asoc"], how="left"
        )
        df.loc[mask, "sum_ind_norm"] = merged2["sum_ind_norm_"].values

    df["por_ind_norm"] = 0.0
    m = df["sum_ind_norm"] > 0
    df.loc[m, "por_ind_norm"] = df.loc[m, "ind_norm"] / df.loc[m, "sum_ind_norm"]

    df["seg_ind_norm"] = 0.0
    m = df["sum_seg_ind_norm"] != 0
    df.loc[m, "seg_ind_norm"] = df.loc[m, "por_ind_norm"] * df.loc[m, "sum_seg_ind_norm"]

    return df


# ─── Funciones de consulta sobre DataFrames ──────────────────────────────────

def _calcular_vi_pd(asoc: str, total: bool, df_dat: pd.DataFrame) -> float:
    if df_dat.empty:
        return 0.0
    mask = df_dat["asoc"] == asoc
    if not total:
        mask = mask & df_dat["tipo"].isin([1, 3, 4, 6])
    df_sub = df_dat[mask][["grupo", "nobjetos", "ui"]].copy()
    if df_sub.empty:
        return 0.0
    df_sub["expr"] = df_sub["nobjetos"] * df_sub["ui"]
    return float(df_sub[["grupo", "expr"]].drop_duplicates()["expr"].sum())


def _cant_cortes_pd(asoc: str, tipo: int, tol: int, id_enlace: int,
                    exceden: bool, df_cortes: pd.DataFrame) -> int:
    if df_cortes.empty:
        return 0
    mask = (df_cortes["tipo"] == tipo) & (df_cortes["asoc"] == asoc) & (df_cortes["idenlace"] == id_enlace)
    if exceden:
        mask = mask & (df_cortes["ind_bruta"] > tol)
    return int(mask.sum())


def _ind_cortes_pd(asoc: str, tipo: int, id_enlace: int,
                   df_cortes: pd.DataFrame) -> float:
    if df_cortes.empty:
        return 0.0
    mask = (df_cortes["tipo"] == tipo) & (df_cortes["idenlace"] == id_enlace) & (df_cortes["asoc"] == asoc)
    return float(df_cortes.loc[mask, "ind_neta"].sum())


def _ind_bruta_pd(asoc: str, id_enlace: int, df_cortes: pd.DataFrame) -> float:
    if df_cortes.empty:
        return 0.0
    mask = (df_cortes["asoc"] == asoc) & (df_cortes["idenlace"] == id_enlace) & (df_cortes["tipo"] == 0)
    return float(df_cortes.loc[mask, "ind_bruta"].sum())


def _num_periodos_pd(asoc: str, id_enlace: int, df_dat: pd.DataFrame) -> int:
    if df_dat.empty:
        return 0
    mask = (df_dat["asoc"] == asoc) & (df_dat["analizar"] == 1) & (df_dat["idenlace"] == id_enlace)
    return int(df_dat.loc[mask, "fecha"].nunique())


def _contar_datos_pd(asoc: str, id_enlace: int, df_dat: pd.DataFrame,
                     tipo=None) -> tuple:
    if df_dat.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    mask = (df_dat["asoc"] == asoc) & (df_dat["analizar"] == 1) & (df_dat["idenlace"] == id_enlace)
    if tipo is not None:
        mask = mask & (df_dat["tipo"] == tipo)
    df_sub = df_dat[mask].copy()
    if df_sub.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    if asoc in ("AC", "BC"):
        df_grp = df_sub.groupby(["fecha", "idenlace"]).agg(
            esp=("esperados", "sum"), rec=("recibidos", "sum"),
            bue=("buenos", "sum"), man=("manuales", "sum"), inv=("invalidos", "sum")
        )
    else:
        df_sub["man_half"] = df_sub["manuales"] / 2
        df_grp = df_sub.groupby(["fecha", "idenlace"]).agg(
            esp=("esperados", "sum"), rec=("recibidos", "sum"),
            bue=("buenos", "sum"), man=("man_half", "sum"), inv=("invalidos", "sum")
        )
    return (float(df_grp["esp"].sum()), float(df_grp["rec"].sum()),
            float(df_grp["bue"].sum()), float(df_grp["man"].sum()),
            float(df_grp["inv"].sum()))


def _norec_ui_pd(asoc: str, id_enlace: int, df_sum: pd.DataFrame) -> float:
    if df_sum.empty:
        return 0.0
    mask = (df_sum["asoc"] == asoc) & (df_sum["idenlace"] == id_enlace)
    return float(df_sum.loc[mask, "sum_ui_norec_norm"].sum())


def _norec_seg_pd(asoc: str, v_ui: float, n_p: int,
                  id_enlace: int, df_sum: pd.DataFrame) -> float:
    if df_sum.empty:
        return 0.0
    mask = (df_sum["asoc"] == asoc) & (df_sum["idenlace"] == id_enlace)
    r = float(df_sum.loc[mask, "sum_ui_esperadas"].sum())
    return v_ui * n_p * 1800 / r if r != 0 else 0.0


def _noval_ui_pd(asoc: str, id_enlace: int, df_sum: pd.DataFrame) -> float:
    if df_sum.empty:
        return 0.0
    mask = (df_sum["asoc"] == asoc) & (df_sum["idenlace"] == id_enlace)
    return float(df_sum.loc[mask, "sum_ui_inv_norm"].sum())


def _noval_seg_pd(asoc: str, v_ui: float, n_p: int,
                  id_enlace: int, df_sum: pd.DataFrame) -> float:
    if df_sum.empty:
        return 0.0
    mask = (df_sum["asoc"] == asoc) & (df_sum["idenlace"] == id_enlace)
    r = float(df_sum.loc[mask, "sum_ui_esperadas"].sum())
    return v_ui * n_p * 1800 / r if r != 0 else 0.0


def _mant_seg_pd(asoc: str, n_p: int, id_enlace: int,
                 df_sum: pd.DataFrame) -> float:
    if df_sum.empty:
        return 0.0
    mask = (df_sum["asoc"] == asoc) & (df_sum["idenlace"] == id_enlace)
    df_sub = df_sum[mask]
    if df_sub.empty:
        return 0.0
    norec_mant = float(df_sub["sum_ui_norec_mant"].sum())
    inv_mant = float(df_sub["sum_ui_inv_mant"].sum())
    esp = float(df_sub["sum_ui_esperadas"].sum())
    return (norec_mant + inv_mant) * n_p * 1800 / esp if esp != 0 else 0.0


def _obtener_cortes_pd(id_enlace: int, tol: int, ac: str, ab: str,
                       df_cortes: pd.DataFrame) -> str:
    if df_cortes.empty:
        return ""
    m_ab = (df_cortes["idenlace"] == id_enlace) & (df_cortes["asoc"] == ab)
    m_ac = (df_cortes["idenlace"] == id_enlace) & (df_cortes["asoc"] == ac)
    df_ab = df_cortes[m_ab].copy(); df_ab["suceso"] = "Est Ind"
    df_ac = df_cortes[m_ac].copy(); df_ac["suceso"] = "Med Ind"
    rows = pd.concat([df_ab, df_ac]).sort_values("inicio")
    if rows.empty:
        return ""

    ret = "FECHA INICIO            FECHA FIN               SUCESO      DURACION      OBSERVACIONES\n\n"
    for _, r in rows.iterrows():
        fi = pd.Timestamp(r["inicio"])
        ff = pd.Timestamp(r["fin"])
        fi = fi.strftime("%d/%m/%Y %H:%M:%S")
        ff = ff.strftime("%d/%m/%Y %H:%M:%S")
        bruta = float(r["ind_bruta"])
        neta = int(r["ind_neta"])
        tipo = int(r["tipo"])
        suceso = str(r["suceso"])
        ret += _completar(fi, 19)
        ret += _completar(ff, 24)
        ret += _completar(suceso, 12)
        ret += _completar(f"{neta} seg", 14)
        if tipo == 1:
            ret += _completar("MANTENIMIENTO", 18)
        elif bruta <= tol:
            ret += _completar(f"< {tol} seg (no computa)", 18)
        ret += "\n"
    return ret


# ─── Armar informe con DataFrames ────────────────────────────────────────────

def _armar_informe_pd(id_enlace: int, ini: datetime, fin: datetime,
                      df_dat: pd.DataFrame, df_sum: pd.DataFrame,
                      df_cortes: pd.DataFrame, db: Session) -> tuple[str, dict]:
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    enlace_row = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:id LIMIT 1"), {"id": id_enlace}
    ).fetchone()
    enlace_name = enlace_row[0] if enlace_row else str(id_enlace)

    tol_c = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)
    tol_d = int(db.execute(text("SELECT tol_datos FROM configuracion LIMIT 1")).scalar() or 2)

    ac = _nombre_asoc("C", id_enlace, db)
    ab = _nombre_asoc("B", id_enlace, db)

    vi_ct = _calcular_vi_pd(ac, True, df_dat)
    vi_bt = _calcular_vi_pd(ab, True, df_dat)
    vi_total_t = vi_ct + vi_bt

    isc_norm = _ind_cortes_pd(ac, 0, id_enlace, df_cortes)
    isc_mant = _ind_cortes_pd(ac, 1, id_enlace, df_cortes)
    isb_norm = _ind_cortes_pd(ab, 0, id_enlace, df_cortes)
    isb_mant = _ind_cortes_pd(ab, 1, id_enlace, df_cortes)

    is_cortes_norm = (isc_norm * vi_ct + isb_norm * vi_bt) / vi_total_t if vi_total_t else 0.0
    is_cortes_mant = (isc_mant * vi_ct + isb_mant * vi_bt) / vi_total_t if vi_total_t else 0.0

    bruta_c = int(_ind_bruta_pd(ac, id_enlace, df_cortes))
    bruta_b = int(_ind_bruta_pd(ab, id_enlace, df_cortes))

    vi_c = _calcular_vi_pd(ac, False, df_dat)
    vi_b = _calcular_vi_pd(ab, False, df_dat)
    vi_total = vi_c + vi_b

    if vi_total > 0:
        np_c = _num_periodos_pd(ac, id_enlace, df_dat)
        np_b = _num_periodos_pd(ab, id_enlace, df_dat)

        gl_esp, gl_rec, gl_bue, gl_man, _ = _contar_datos_pd(ac, id_enlace, df_dat)
        ui_c_norec = _norec_ui_pd(ac, id_enlace, df_sum)
        is_c_norec = _norec_seg_pd(ac, ui_c_norec, np_c, id_enlace, df_sum)
        ui_c_noval = _noval_ui_pd(ac, id_enlace, df_sum)
        is_c_noval = _noval_seg_pd(ac, ui_c_noval, np_c, id_enlace, df_sum)

        ui_b_norec = _norec_ui_pd(ab, id_enlace, df_sum)
        is_b_norec = _norec_seg_pd(ab, ui_b_norec, np_b, id_enlace, df_sum)
        ui_b_noval = _noval_ui_pd(ab, id_enlace, df_sum)
        is_b_noval = _noval_seg_pd(ab, ui_b_noval, np_b, id_enlace, df_sum)

        is_datos_norec = (is_c_norec * vi_c + is_b_norec * vi_b) / vi_total
        is_datos_noval = (is_c_noval * vi_c + is_b_noval * vi_b) / vi_total
        is_datos_norm = is_datos_norec + is_datos_noval

        is_c_mant = _mant_seg_pd(ac, np_c, id_enlace, df_sum)
        is_b_mant = _mant_seg_pd(ab, np_b, id_enlace, df_sum)
        is_datos_mant = (is_c_mant * vi_c + is_b_mant * vi_b) / vi_total

        med = _contar_datos_pd(ab, id_enlace, df_dat, 1)
        est = _contar_datos_pd(ab, id_enlace, df_dat, 3)
        ala = _contar_datos_pd(ab, id_enlace, df_dat, 4)
        rbc = _contar_datos_pd(ab, id_enlace, df_dat, 6)
        med_esp, med_rec, med_bue, med_man = med[0], med[1], med[2], med[3]
        est_esp, est_rec, est_bue, est_man = est[0], est[1], est[2], est[3]
        ala_esp, ala_rec, ala_bue, ala_man = ala[0], ala[1], ala[2], ala[3]
        rbc_esp, rbc_rec, rbc_bue, rbc_man = rbc[0], rbc[1], rbc[2], rbc[3]
        gl_esp_b = med_esp + est_esp + ala_esp + rbc_esp
        gl_rec_b = med_rec + est_rec + ala_rec + rbc_rec
        gl_bue_b = med_bue + est_bue + ala_bue + rbc_bue
        gl_man_b = med_man + est_man + ala_man + rbc_man

        def pct(num, den): return f"   ( {num/den*100:.2f} % )" if den else ""

        prc = pct(gl_rec, gl_esp); pbc = pct(gl_bue, gl_esp); pmc = pct(gl_man, gl_esp)
        pnrc = pct(ui_c_norec, gl_esp); pnvc = pct(ui_c_noval, gl_esp)
        prb = pct(gl_rec_b, gl_esp_b); pbb = pct(gl_bue_b, gl_esp_b); pmb = pct(gl_man_b, gl_esp_b)
        denom_b = med_esp * 1 + est_esp * 0.25 + ala_esp * 0.125 + rbc_esp
        pnrb = pct(ui_b_norec, denom_b); pnvb = pct(ui_b_noval, denom_b)
    else:
        is_datos_norm = is_datos_mant = 0.0

    is_total_norm = is_cortes_norm + is_datos_norm
    is_total_mant = is_cortes_mant + is_datos_mant

    ultimo_dia = (fin - timedelta(seconds=1)).strftime('%d/%m/%Y')
    intervalo_str = f"{ini.strftime('%d/%m/%Y')} al {ultimo_dia}"

    t = ""
    t += f"Indisponibilidad del SOTR ENARSA - ENLACE: {enlace_name}\n"
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
    t += (f" * Asoc. Periódica     :{_completar(str(_cant_cortes_pd(ac,0,tol_c,id_enlace,False,df_cortes)), 6)}"
          f"   ( {_cant_cortes_pd(ac,0,tol_c,id_enlace,True,df_cortes)} exceden {tol_c} seg )\n")
    t += (f" * Asoc. No Solicitada :{_completar(str(_cant_cortes_pd(ab,0,tol_c,id_enlace,False,df_cortes)), 6)}"
          f"   ( {_cant_cortes_pd(ab,0,tol_c,id_enlace,True,df_cortes)} exceden {tol_c} seg )\n")
    t += "Por Mantenimiento\n"
    t += f" * Asoc. Periódica     :{_completar(str(_cant_cortes_pd(ac,1,tol_c,id_enlace,False,df_cortes)), 6)}\n"
    t += f" * Asoc. No Solicitada :{_completar(str(_cant_cortes_pd(ab,1,tol_c,id_enlace,False,df_cortes)), 6)}\n\n"
    t += "Tiempos de indisponibilidad\n"
    t += "Ordinaria Bruta\n"
    t += f" * Asoc. Periódica     :{_completar(str(bruta_c), 11)} seg   ( {seg_to_hms(bruta_c)} )\n"
    t += f" * Asoc. No Solicitada :{_completar(str(bruta_b), 11)} seg   ( {seg_to_hms(bruta_b)} )\n"
    t += "Ordinaria Neta\n"
    t += f" * Asoc. Periódica     :{_completar(str(int(isc_norm)), 11)} seg   ( {seg_to_hms(isc_norm)} )\n"
    t += f" * Asoc. No Solicitada :{_completar(str(int(isb_norm)), 11)} seg   ( {seg_to_hms(isb_norm)} )\n"
    t += f" * Promedio Neto       :{_completar(str(round(is_cortes_norm)), 11)} seg   ( {seg_to_hms(round(is_cortes_norm))} )\n\n"
    t += "Por Mantenimiento:\n"
    t += f" * Asoc. Periódica     :{_completar(str(int(isc_mant)), 11)} seg   ( {seg_to_hms(isc_mant)} )\n"
    t += f" * Asoc. No Solicitada :{_completar(str(int(isb_mant)), 11)} seg   ( {seg_to_hms(isb_mant)} )\n"
    t += f" * Promedio Mant.      :{_completar(str(round(is_cortes_mant)), 11)} seg   ( {seg_to_hms(round(is_cortes_mant))} )\n\n"
    t += "En la indisponibilidad neta y por mantenimiento, no se incluyen cortes de menos\n"
    t += f"de {tol_c} seg. En los cortes mayores, se deducen {tol_c} seg.\n\n"
    t += "En estos promedios se consideraron los siguientes volumenes de información:\n"
    t += f"{_completar(f'{vi_ct:.3f}', 10)} u.i - asociación datos periódicos\n"
    t += f"{_completar(f'{vi_bt:.3f}', 10)} u.i - asociación datos no solicitados\n"
    t += "\n*****************************************************************\n\n"
    t += f"2) Indisponibilidad por calidad de datos para el enlace {enlace_name}\n\n"
    if vi_total > 0:
        t += " Computada solamente en períodos normales\n"
        t += f" Tolerancia para datos no recibidos: {tol_d}%\n"
        t += f" Tolerancia para datos inválidos   : {tol_d}%\n\n"
        t += "Estadísticas\n\n"
        t += f"Datos periódicos sobre {np_c} períodos.\n"
        t += f"  Esperados                  :{_completar(str(int(gl_esp)), 11)}\n"
        t += f"  Recibidos                  :{_completar(str(int(gl_rec)), 11)}{prc}\n"
        t += f"  Buenos                     :{_completar(str(int(gl_bue)), 11)}{pbc}\n"
        t += f"  Manuales                   :{_completar(str(int(gl_man)), 11)}{pmc}\n\n"
        t += f"  Vol. Info no recibidos     :{_completar(f'{ui_c_norec:.2f}', 11)} ui{pnrc}\n"
        t += f"  Vol. Info Inválidos        :{_completar(f'{ui_c_noval:.2f}', 11)} ui{pnvc}\n\n\n"
        t += f"Datos no solicitados sobre {np_b} períodos.\n"
        t += "                          Mediciones    Estados    Alarmas        RBC\n"
        t += (f"  Esperados          :{_completar(str(int(med_esp)), 14)}"
              f"{_completar(str(int(est_esp)), 11)}{_completar(str(int(ala_esp)), 11)}{_completar(str(int(rbc_esp)), 11)}\n")
        t += (f"  Recibidos          :{_completar(str(int(med_rec)), 14)}"
              f"{_completar(str(int(est_rec)), 11)}{_completar(str(int(ala_rec)), 11)}{_completar(str(int(rbc_rec)), 11)}{prb}\n")
        t += (f"  Buenos             :{_completar(str(int(med_bue)), 14)}"
              f"{_completar(str(int(est_bue)), 11)}{_completar(str(int(ala_bue)), 11)}{_completar(str(int(rbc_bue)), 11)}{pbb}\n")
        t += (f"  Manuales (al 50%)  :{_completar(str(int(med_man)), 14)}"
              f"{_completar(str(int(est_man)), 11)}{_completar(str(int(ala_man)), 11)}{_completar(str(int(rbc_man)), 11)}{pmb}\n\n")
        t += f"  Vol. Info no recibidos     :{_completar(f'{ui_b_norec:.2f}', 11)} ui{pnrb}\n"
        t += f"  Vol. Info Inválidos        :{_completar(f'{ui_b_noval:.2f}', 11)} ui{pnvb}\n\n\n"
        t += "Indisponibilidades de datos periódicos\n"
        t += "  * Indisponibilidad por datos no recibidos:\n"
        t += f"{_completar(str(round(is_c_norec)), 21)} seg   ( {seg_to_hms(round(is_c_norec))} )\n"
        t += "  * Indisponibilidad por datos inválidos:\n"
        t += f"{_completar(str(round(is_c_noval)), 21)} seg   ( {seg_to_hms(round(is_c_noval))} )\n\n"
        t += "Indisponibilidades de datos no solicitados\n"
        t += "  * Indisponibilidad por datos no recibidos:\n"
        t += f"{_completar(str(round(is_b_norec)), 21)} seg   ( {seg_to_hms(round(is_b_norec))} )\n"
        t += "  * Indisponibilidad por datos inválidos:\n"
        t += f"{_completar(str(round(is_b_noval)), 21)} seg   ( {seg_to_hms(round(is_b_noval))} )\n\n"
        t += "* Indisponibilidad promedio Mediciones/Estados no recibidos e inválidos\n"
        t += f"{_completar(str(round(is_datos_norm)), 21)} seg   ( {seg_to_hms(round(is_datos_norm))} )\n\n"
        t += "Indisponibilidades por mantenimientos programados\n"
        t += f"  * Mediciones    :{_completar(str(round(is_c_mant)), 12)} seg   ( {seg_to_hms(round(is_c_mant))} )\n"
        t += f"  * No solicitados:{_completar(str(round(is_b_mant)), 12)} seg   ( {seg_to_hms(round(is_b_mant))} )\n"
        t += f"  * Promedio      :{_completar(str(round(is_datos_mant)), 12)} seg   ( {seg_to_hms(round(is_datos_mant))} )\n\n"
        t += "En estos promedios se consideraron los siguientes volumenes de información:\n"
        t += f"{_completar(f'{vi_c:.3f}', 10)} u.i - asociación datos periódicos \n"
        t += f"{_completar(f'{vi_b:.3f}', 10)} u.i - no solicit. salvo alar. dinámicas y energías\n\n"
    else:
        t += "Sin datos .dat disponibles para este período. La indisponibilidad por calidad no pudo calcularse.\n\n"
    t += "=================================================================\n\n"
    t += "Resumen de resultados\n\n"
    t += f"* Indisponibilidad en el período (total por cortes de enlace y calidad de datos) de {enlace_name}\n"
    t += f"{_completar(str(round(is_total_norm)), 21)} seg   ( {seg_to_hms(round(is_total_norm))} )\n\n"
    t += f"* Mantenimientos en el período (total por cortes de enlace y calidad de datos) de {enlace_name}\n"
    t += f"{_completar(str(round(is_total_mant)), 21)} seg   ( {seg_to_hms(round(is_total_mant))} )\n\n"
    t += "=================================================================\n"

    valores = {
        "enlace_nombre": enlace_name,
        "bruta_c": bruta_c, "bruta_b": bruta_b,
        "neta_c": isc_norm, "neta_b": isb_norm,
        "promedio_neto": is_cortes_norm,
        "mant_cortes_c": isc_mant, "mant_cortes_b": isb_mant,
        "promedio_mant_cortes": is_cortes_mant,
        "ind_norec_c": is_c_norec if vi_total > 0 else 0.0,
        "ind_noval_c": is_c_noval if vi_total > 0 else 0.0,
        "ind_norec_b": is_b_norec if vi_total > 0 else 0.0,
        "ind_noval_b": is_b_noval if vi_total > 0 else 0.0,
        "ind_datos_norm": is_datos_norm,
        "ind_mant_c": is_c_mant if vi_total > 0 else 0.0,
        "ind_mant_b": is_b_mant if vi_total > 0 else 0.0,
        "ind_datos_mant": is_datos_mant,
        "ind_total_norm": is_total_norm, "ind_total_mant": is_total_mant,
    }
    return t, valores


# ─── Procesador principal (sin tablas temporales) ────────────────────────────

def _excluir_periodos_con_corte(df_dat: pd.DataFrame, df_cortes: pd.DataFrame) -> pd.DataFrame:
    """Excluye registros .dat cuyo período 30-min se solapa con algún corte.

    Alinea el comportamiento al VB6: la sección de calidad de datos solo evalúa
    períodos donde el enlace estuvo disponible durante los 30 minutos completos.
    Los períodos parcialmente afectados por un corte ya están cubiertos por la
    sección de cortes, evitando doble conteo.
    """
    if df_cortes.empty or df_dat.empty:
        return df_dat

    cortes_ini = pd.to_datetime(df_cortes["inicio"])
    cortes_fin = pd.to_datetime(df_cortes["fin"])

    def periodo_limpio(fecha: pd.Timestamp) -> bool:
        p_ini = fecha - pd.Timedelta(minutes=30)
        p_fin = fecha
        return not ((cortes_ini < p_fin) & (cortes_fin > p_ini)).any()

    mask = pd.to_datetime(df_dat["fecha"]).apply(periodo_limpio)
    return df_dat[mask].reset_index(drop=True)


def _procesar_enlace_pd(id_enlace: int, ini: datetime, fin: datetime,
                        db: Session) -> tuple[str, dict, pd.DataFrame]:
    """
    Procesa un enlace usando pandas en memoria.
    Retorna (texto_informe, valores_calculados, df_cortes).
    """
    tol = int(db.execute(text("SELECT tol_cortes FROM configuracion LIMIT 1")).scalar() or 120)
    ac = _nombre_asoc("C", id_enlace, db)
    ab = _nombre_asoc("B", id_enlace, db)

    df_dat = _procesar_datos_dat_pd(ini, fin, id_enlace, db)

    # Solo procesar las 2 asociaciones relevantes según dirección del enlace:
    # directo (rol='directo' o idtipo=2) → prefijo A → ab, ac
    # concentrador (idtipo=3 o sin rol)  → prefijo B → bb, bc
    asocs = ["ab", "ac"] if _es_directo(id_enlace, db) else ["bb", "bc"]

    all_cortes: list[dict] = []
    for asoc in asocs:
        all_cortes.extend(_procesar_corte_asoc_pd(asoc, ini, fin, id_enlace, tol, df_dat, db))

    df_cortes = pd.DataFrame(all_cortes) if all_cortes else pd.DataFrame(
        columns=["inicio", "fin", "idenlace", "asoc", "ind_bruta", "ind_neta", "tipo"])

    # Excluir períodos .dat que se solapan con cortes (comportamiento VB6)
    if not df_dat.empty and not df_cortes.empty:
        df_dat = _excluir_periodos_con_corte(df_dat, df_cortes)

    if not df_dat.empty:
        df_dat = _update_excluidos_pd(df_dat, df_cortes)
        df_dat = _misc1_pd(df_dat)
        df_sum = _sumas_parciales_pd(df_dat)
        df_dat = _misc2_pd(df_dat, df_sum, ac, ab)
    else:
        df_sum = pd.DataFrame()

    txt, valores = _armar_informe_pd(id_enlace, ini, fin, df_dat, df_sum, df_cortes, db)
    return txt, valores, df_cortes


# ─── Corte efectivo (Tipo 2): intersección de ventanas de corte ──────────────

def _generar_txt_corte_efectivo(df_a: pd.DataFrame, df_b: pd.DataFrame,
                                ini: datetime, fin: datetime, nemo: str) -> str:
    """Calcula la intersección de cortes entre el enlace directo y el concentrador."""
    if df_a.empty or df_b.empty:
        return ""

    intersecciones = []
    for _, a in df_a.iterrows():
        for _, b in df_b.iterrows():
            start = max(a["inicio"], b["inicio"])
            end   = min(a["fin"],    b["fin"])
            if start < end:
                dur_seg = (end - start).total_seconds()
                intersecciones.append({"inicio": start, "fin": end, "dur_seg": dur_seg})

    if not intersecciones:
        return ""

    total_seg   = sum(i["dur_seg"] for i in intersecciones)
    periodo_seg = (fin - ini).total_seconds()
    disp        = (1.0 - total_seg / periodo_seg) * 100.0 if periodo_seg > 0 else 100.0

    lines = [
        "=" * 60,
        f"CORTE EFECTIVO — {nemo}",
        f"Período: {ini.strftime('%d/%m/%Y %H:%M')} — {fin.strftime('%d/%m/%Y %H:%M')}",
        "-" * 60,
    ]
    for i in intersecciones:
        lines.append(
            f"  {i['inicio'].strftime('%d/%m/%Y %H:%M')} → "
            f"{i['fin'].strftime('%d/%m/%Y %H:%M')}  ({seg_to_hms(i['dur_seg'])})"
        )
    lines += [
        "-" * 60,
        f"Indisponibilidad efectiva: {seg_to_hms(total_seg)}",
        f"Disponibilidad efectiva:   {disp:.3f}%",
        "=" * 60,
        "",
    ]
    return "\n".join(lines) + "\n"


# ─── Punto de entrada para TXT ───────────────────────────────────────────────

def generar_reporte_txt(db: Session, id_central: int,
                        fecha_ini: datetime, fecha_fin: datetime) -> str:
    fecha_ini = _a_hora_local(fecha_ini)
    fecha_fin = _a_hora_local(fecha_fin)

    central = db.execute(
        text("SELECT id, nemo, tipo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central}
    ).fetchone()
    if not central:
        return f"Central {id_central} no encontrada.\n"

    _, nemo, tipo = central

    # Enlace directo propio: buscar por rol='directo'; fallback a nombre *_CAMM
    enlace_directo = db.execute(
        text("SELECT id FROM enlaces WHERE rol='directo' AND idcentral=:c LIMIT 1"),
        {"c": id_central}
    ).scalar()
    if not enlace_directo:
        enlace_directo = db.execute(
            text("""SELECT id FROM enlaces WHERE idcentral=:c AND nombre LIKE '%\_CAMM'
                    AND nombre NOT LIKE 'BCOG\_%' LIMIT 1"""),
            {"c": id_central}
        ).scalar()

    # Enlace concentrador: idtipo=3, nombre='{nemo}_CAMM', pertenece a BCOG
    bcog_id = db.execute(
        text("SELECT id FROM centrales WHERE UPPER(nemo)='BCOG' LIMIT 1")
    ).scalar()
    enlace_bcog = None
    if bcog_id:
        enlace_bcog = db.execute(
            text("SELECT id FROM enlaces WHERE idtipo=3 AND nombre=:nombre AND idcentral=:bcog LIMIT 1"),
            {"nombre": f"{nemo}_CAMM", "bcog": bcog_id}
        ).scalar()

    txt = ""

    if tipo == 1:
        # Central directa: solo enlace propio (idtipo=2)
        if not enlace_directo:
            return f"Central {nemo} (tipo 1) sin enlace directo configurado.\n"
        txt += _procesar_enlace_pd(enlace_directo, fecha_ini, fecha_fin, db)[0]

    elif tipo == 2:
        # Central redundante: enlace directo + enlace concentrador + corte efectivo
        if not enlace_directo and not enlace_bcog:
            return f"Central {nemo} (tipo 2) sin enlaces configurados.\n"

        df_cortes_directo = pd.DataFrame()
        df_cortes_bcog    = pd.DataFrame()

        if enlace_directo:
            txt_d, _, df_cortes_directo = _procesar_enlace_pd(enlace_directo, fecha_ini, fecha_fin, db)
            txt += txt_d
        if enlace_bcog:
            txt_b, _, df_cortes_bcog = _procesar_enlace_pd(enlace_bcog, fecha_ini, fecha_fin, db)
            txt += txt_b

        txt += _generar_txt_corte_efectivo(
            df_cortes_directo, df_cortes_bcog, fecha_ini, fecha_fin, nemo
        )

    elif tipo == 3:
        # Central solo-backup: solo enlace concentrador en BCOG
        if not enlace_bcog:
            return f"Central {nemo} (tipo 3) sin enlace BCOG configurado.\n"
        txt += _procesar_enlace_pd(enlace_bcog, fecha_ini, fecha_fin, db)[0]

    else:
        return f"Tipo de central desconocido: {tipo}\n"

    return txt or f"No se encontraron datos para la central {nemo}.\n"


# ─── Funciones existentes (JSON endpoint) ────────────────────────────────────

def _minutos_periodo(inicio: datetime, fin: datetime) -> float:
    return (fin - inicio).total_seconds() / 60.0


def calcular_reporte(db, id_central: int, fecha_inicio: datetime,
                     fecha_fin: datetime) -> schemas.ReporteOut:
    fecha_inicio = _a_hora_local(fecha_inicio)
    fecha_fin = _a_hora_local(fecha_fin)

    central = db.query(models.Central).filter(models.Central.id == id_central).first()
    if not central:
        raise ValueError(f"Central {id_central} no encontrada")

    enlaces = db.query(models.Enlace).filter(models.Enlace.idcentral == id_central).all()
    if not enlaces:
        raise ValueError(f"La central {central.nemo} no tiene enlaces configurados")

    total_minutos = _minutos_periodo(fecha_inicio, fecha_fin)
    todos_cortes = []

    def _cargar_conexiones(id_enlace):
        rows = db.query(models.Conexion).filter(
            models.Conexion.id_enlace == id_enlace,
            models.Conexion.fecha >= fecha_inicio,
            models.Conexion.fecha <= fecha_fin,
        ).order_by(models.Conexion.fecha).all()
        if not rows:
            return pd.DataFrame(columns=["fecha", "estado"])
        df = pd.DataFrame([{"fecha": r.fecha, "estado": r.asoc_bc} for r in rows])
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["estado"] = pd.to_numeric(df["estado"], errors="coerce").fillna(0).astype(int)
        return df

    def _cargar_mantenimientos(id_enlace):
        rows = db.query(models.Mantenimiento).filter(
            models.Mantenimiento.idenlace == id_enlace,
            models.Mantenimiento.inicio < fecha_fin,
            models.Mantenimiento.fin > fecha_inicio,
        ).all()
        if not rows:
            return pd.DataFrame(columns=["inicio", "fin", "tipo"])
        df = pd.DataFrame([{"inicio": r.inicio, "fin": r.fin, "tipo": r.tipo} for r in rows])
        df["inicio"] = pd.to_datetime(df["inicio"])
        df["fin"] = pd.to_datetime(df["fin"])
        return df

    def _detectar_cortes(df_con):
        cortes = []
        if df_con.empty:
            return pd.DataFrame(columns=["inicio_corte", "fin_corte"])
        inicio_corte = None
        for _, row in df_con.iterrows():
            if row["estado"] == 0 and inicio_corte is None:
                inicio_corte = row["fecha"]
            elif row["estado"] == 1 and inicio_corte is not None:
                cortes.append({"inicio_corte": inicio_corte, "fin_corte": row["fecha"]})
                inicio_corte = None
        if inicio_corte is not None:
            cortes.append({"inicio_corte": inicio_corte, "fin_corte": fecha_fin})
        if not cortes:
            return pd.DataFrame(columns=["inicio_corte", "fin_corte"])
        df = pd.DataFrame(cortes)
        df["inicio_corte"] = df["inicio_corte"].clip(lower=pd.Timestamp(fecha_inicio))
        df["fin_corte"] = df["fin_corte"].clip(upper=pd.Timestamp(fecha_fin))
        return df

    def _marcar_mant(df_cortes, df_mant):
        if df_cortes.empty:
            return df_cortes
        df_cortes = df_cortes.copy()
        df_cortes["es_mantenimiento"] = False
        df_cortes["tipo_mant"] = None
        if df_mant.empty:
            return df_cortes
        for idx, corte in df_cortes.iterrows():
            for _, mant in df_mant.iterrows():
                if corte["inicio_corte"] >= mant["inicio"] and corte["inicio_corte"] < mant["fin"]:
                    df_cortes.at[idx, "es_mantenimiento"] = True
                    df_cortes.at[idx, "tipo_mant"] = int(mant["tipo"])
                    break
        return df_cortes

    def _cortes_enlace(enlace):
        df_con = _cargar_conexiones(enlace.id)
        df_mant = _cargar_mantenimientos(enlace.id)
        df_cortes = _detectar_cortes(df_con)
        df_cortes = _marcar_mant(df_cortes, df_mant)
        items = []
        tipo_map = {1: "Enlace", 2: "Ordinario", 3: "Electrico"}
        for _, row in df_cortes.iterrows():
            dur = _minutos_periodo(row["inicio_corte"].to_pydatetime(), row["fin_corte"].to_pydatetime())
            tipo_str = tipo_map.get(int(row["tipo_mant"])) if row["es_mantenimiento"] and row.get("tipo_mant") is not None else None
            items.append(schemas.CorteItem(
                id_enlace=enlace.id, nombre_enlace=enlace.nombre,
                inicio=row["inicio_corte"].to_pydatetime(), fin=row["fin_corte"].to_pydatetime(),
                duracion_minutos=round(dur, 2), es_mantenimiento=bool(row["es_mantenimiento"]), tipo=tipo_str,
            ))
        return items

    if central.tipo == 1:
        for e in enlaces:
            todos_cortes.extend(_cortes_enlace(e))
    elif central.tipo == 2:
        cortes_por_enlace = [_cortes_enlace(e) for e in enlaces]
        todos_cortes = _intersectar_cortes(cortes_por_enlace, fecha_inicio, fecha_fin)
    elif central.tipo == 3:
        for e in enlaces:
            todos_cortes.extend(_cortes_enlace(e))

    minutos_real = sum(c.duracion_minutos for c in todos_cortes if not c.es_mantenimiento)
    disponibilidad = max(0.0, (1 - minutos_real / total_minutos) * 100) if total_minutos > 0 else 100.0

    return schemas.ReporteOut(
        idCentral=id_central, nemo=central.nemo, tipo_central=central.tipo,
        fechaInicio=fecha_inicio, fechaFin=fecha_fin, cortes=todos_cortes,
        disponibilidad_pct=round(disponibilidad, 4),
        total_minutos_corte=round(minutos_real, 2),
        total_minutos_periodo=round(total_minutos, 2),
    )


def _intersectar_cortes(cortes_por_enlace, inicio, fin):
    if not cortes_por_enlace:
        return []
    index = pd.date_range(start=inicio, end=fin, freq="60s", inclusive="left")
    df = pd.DataFrame(False, index=index, columns=range(len(cortes_por_enlace)))
    for i, cortes in enumerate(cortes_por_enlace):
        for c in cortes:
            mask = (index >= pd.Timestamp(c.inicio)) & (index < pd.Timestamp(c.fin))
            df.loc[mask, i] = True
    todos = df.all(axis=1)
    resultado = []
    en_corte = False
    ini_corte = None
    for ts, caido in todos.items():
        if caido and not en_corte:
            en_corte = True; ini_corte = ts
        elif not caido and en_corte:
            en_corte = False
            dur = (ts - ini_corte).total_seconds() / 60.0
            resultado.append(schemas.CorteItem(id_enlace=0, nombre_enlace="Redundante",
                inicio=ini_corte.to_pydatetime(), fin=ts.to_pydatetime(),
                duracion_minutos=round(dur, 2), es_mantenimiento=False))
    if en_corte and ini_corte:
        dur = (pd.Timestamp(fin) - ini_corte).total_seconds() / 60.0
        resultado.append(schemas.CorteItem(id_enlace=0, nombre_enlace="Redundante",
            inicio=ini_corte.to_pydatetime(), fin=fin,
            duracion_minutos=round(dur, 2), es_mantenimiento=False))
    return resultado


def formatear_reporte_txt(reporte: schemas.ReporteOut) -> str:
    return ""


# ─── Corte efectivo para centrales redundantes ───────────────────────────────

def _ventanas_corte_enlace(id_enlace: int, ini: datetime, fin: datetime,
                            db: Session) -> list[tuple[datetime, datetime]]:
    row = db.execute(
        text("SELECT idtipo FROM enlaces WHERE id = :id LIMIT 1"), {"id": id_enlace}
    ).fetchone()
    prefix = "A" if (row and row[0] == 2) else "B"
    col = f"{prefix.lower()}c"

    EV_DOWN, EV_UP = 1, 2
    fin_dia = fin - timedelta(seconds=1)

    try:
        rows = db.execute(
            text(f"""SELECT fecha, CAST({col} AS SIGNED)
                     FROM vista_asoc_con1
                     WHERE fecha >= :ini AND fecha < :fin
                       AND id_enlace = :e AND {col} IS NOT NULL
                     ORDER BY fecha"""),
            {"ini": ini, "fin": fin, "e": id_enlace}
        ).fetchall()
    except Exception:
        return []

    ventanas: list[tuple[datetime, datetime]] = []
    estado = 0
    t_down: datetime | None = None

    for fecha, ev in rows:
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha)
        ev = int(ev) if ev is not None else -1

        if estado == 0:
            if ev == EV_DOWN:
                t_down = fecha; estado = 1
            elif ev == EV_UP:
                ventanas.append((ini, fecha)); estado = 2
        elif estado == 1:
            if ev == EV_UP:
                ventanas.append((t_down, fecha)); t_down = None; estado = 2
        elif estado == 2:
            if ev == EV_DOWN:
                t_down = fecha; estado = 1

    if estado == 1 and t_down is not None:
        ventanas.append((t_down, fin_dia))

    return ventanas


def _interseccion_segundos(va: list[tuple[datetime, datetime]],
                            vb: list[tuple[datetime, datetime]]) -> float:
    total = 0.0
    for a0, a1 in va:
        for b0, b1 in vb:
            s = max(a0, b0)
            e = min(a1, b1)
            if e > s:
                total += (e - s).total_seconds()
    return max(0.0, total)


def _calcular_corte_efectivo_redundantes(ini: datetime, fin: datetime, db: Session):
    redundantes = db.execute(
        text("SELECT id, nemo FROM centrales WHERE tipo = 2")
    ).fetchall()

    for c_id, c_nemo in redundantes:
        id_prim = db.execute(text("""
            SELECT id FROM enlaces
            WHERE idcentral = :cid AND UPPER(nombre) = 'CGEN_CAMM' LIMIT 1
        """), {"cid": c_id}).scalar()

        id_bck = db.execute(text("""
            SELECT e.id FROM enlaces e
            JOIN centrales bc ON bc.id = e.idcentral AND UPPER(bc.nemo) = 'BCOG'
            WHERE UPPER(e.nombre) = UPPER(CONCAT(:n, '_CAMM')) LIMIT 1
        """), {"n": c_nemo}).scalar()

        if not id_prim or not id_bck:
            continue

        va = _ventanas_corte_enlace(id_prim, ini, fin, db)
        vb = _ventanas_corte_enlace(id_bck, ini, fin, db)

        if not va and not vb:
            continue

        corte_ef = _interseccion_segundos(va, vb)
        fecha_dia = ini.date()

        for id_e in (id_prim, id_bck):
            try:
                db.execute(
                    text("""UPDATE resultados_reporte
                            SET corte_efectivo = :ce
                            WHERE id_enlace = :e AND fecha = :f"""),
                    {"ce": corte_ef, "e": id_e, "f": fecha_dia}
                )
            except Exception:
                pass
    db.commit()


# ─── Cálculo de indisponibilidad por central ─────────────────────────────────

def _estado_inicial_enlace(id_enlace: int, col: str, ini: datetime, db: Session) -> bool:
    """True si el enlace estaba UP justo antes de ini.
    Busca el último evento significativo (e+/i+), ignorando valores intermedios
    del mismo batch (e, i, u, etc.) que no representan el estado final del enlace."""
    last = db.execute(
        text(f"SELECT {col} FROM con WHERE id_enlace=:e AND {col} IN ('i+','e+') AND fecha<:ini ORDER BY fecha DESC LIMIT 1"),
        {"e": id_enlace, "ini": ini}
    ).scalar()
    if last is None:
        return True  # sin historial → asumir UP
    return last == "e+"


def _get_link_events(id_enlace: int, ini: datetime, fin: datetime,
                     db: Session) -> list[tuple[datetime, str]]:
    """Retorna eventos i+/e+ del enlace en [ini, fin] usando la asociación no solicitada."""
    prefix = "a" if _es_directo(id_enlace, db) else "b"
    col = f"asoc_{prefix}b"
    rows = db.execute(
        text(f"SELECT fecha, {col} FROM con"
             f" WHERE id_enlace=:e AND fecha>=:ini AND fecha<=:fin AND {col} IN ('i+','e+')"
             f" ORDER BY fecha"),
        {"e": id_enlace, "ini": ini, "fin": fin}
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _construir_timeline_tipo2(
    id_prim: int, id_bck: int, ini: datetime, fin: datetime, db: Session
) -> tuple[list[dict], list[dict], list[dict], float]:
    """
    Construye la línea de tiempo unificada de dos enlaces en modo failover.

    Retorna:
      segments       — list[{inicio, fin, estado: 'prim'|'bck'|'ambos'|'ninguno', dur_seg}]
      cortes_ef      — list[{inicio, fin, dur_seg}]  (estado='ninguno')
      inconsistencias — list[{tipo, descripcion, t1, t2}]
      corte_ef_seg   — float (segundos totales sin cobertura)
    """
    prefix_prim = "a" if _es_directo(id_prim, db) else "b"
    col_prim    = f"asoc_{prefix_prim}b"
    prefix_bck  = "a" if _es_directo(id_bck, db) else "b"
    col_bck     = f"asoc_{prefix_bck}b"

    prim_up = _estado_inicial_enlace(id_prim, col_prim, ini, db)
    bck_up  = _estado_inicial_enlace(id_bck,  col_bck,  ini, db)

    events_prim = _get_link_events(id_prim, ini, fin, db)
    events_bck  = _get_link_events(id_bck,  ini, fin, db)

    all_events = sorted(
        [(t, ev, "prim") for t, ev in events_prim] +
        [(t, ev, "bck")  for t, ev in events_bck],
        key=lambda x: x[0]
    )

    def _estado_str(p: bool, b: bool) -> str:
        if p and b:  return "ambos"
        if p:        return "prim"
        if b:        return "bck"
        return "ninguno"

    segments: list[dict]       = []
    inconsistencias: list[dict] = []
    current_t     = ini
    current_estado = _estado_str(prim_up, bck_up)

    for t, ev, source in all_events:
        t = min(t, fin)
        if t > current_t:
            segments.append({
                "inicio": current_t, "fin": t,
                "estado": current_estado,
                "dur_seg": (t - current_t).total_seconds(),
            })

        if source == "prim":
            prim_up = (ev == "e+")
        else:
            bck_up = (ev == "e+")

        new_estado = _estado_str(prim_up, bck_up)

        if new_estado == "ambos":
            inconsistencias.append({
                "tipo": "overlap",
                "descripcion": (
                    f'Enlace {"primario" if source == "prim" else "backup"} establecido '
                    f"mientras el otro sigue activo"
                ),
                "t1": t, "t2": t,
            })

        current_t     = t
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


def _get_enlace_directo(id_central: int, db: Session) -> int | None:
    """Enlace directo de una central: busca por rol='directo', fallback por nombre *_CAMM."""
    eid = db.execute(
        text("SELECT id FROM enlaces WHERE idcentral=:c AND rol='directo' LIMIT 1"),
        {"c": id_central}
    ).scalar()
    if eid:
        return eid
    return db.execute(
        text("SELECT id FROM enlaces WHERE idcentral=:c"
             " AND nombre LIKE '%\\_CAMM' AND nombre NOT LIKE 'BCOG\\_%' LIMIT 1"),
        {"c": id_central}
    ).scalar()


def _get_enlace_backup_bcog(nemo: str, db: Session) -> int | None:
    """Enlace concentrador en BCOG para la central con el nemo dado."""
    return db.execute(
        text("""SELECT e.id FROM enlaces e
                JOIN centrales bc ON bc.id=e.idcentral AND UPPER(bc.nemo)='BCOG'
                WHERE UPPER(e.nombre)=UPPER(CONCAT(:n,'_CAMM')) LIMIT 1"""),
        {"n": nemo}
    ).scalar()


def _calcular_tipo2(
    id_prim: int, id_bck: int, ini: datetime, fin: datetime, db: Session
) -> tuple[float, bool]:
    """
    Calcula indisponibilidad total para una central Tipo 2 (redundante/failover).

    Estrategia:
    - Corte efectivo = gaps donde ningún enlace cubre (de la línea de tiempo unificada)
    - Ind. datos = blend proporcional de ind_datos_norm de cada enlace,
      ponderado por el tiempo que cada uno fue el enlace activo en el día

    Retorna (ind_total_seg, tiene_inconsistencia).
    """
    segments, _, inconsistencias, corte_ef_seg = _construir_timeline_tipo2(
        id_prim, id_bck, ini, fin, db
    )

    prim_active = sum(s["dur_seg"] for s in segments if s["estado"] == "prim")
    bck_active  = sum(s["dur_seg"] for s in segments if s["estado"] == "bck")
    total_active = prim_active + bck_active

    if total_active > 0:
        prim_frac = prim_active / total_active
        bck_frac  = bck_active  / total_active
    else:
        prim_frac = bck_frac = 0.0

    _, valores_prim, _ = _procesar_enlace_pd(id_prim, ini, fin, db)
    _, valores_bck,  _ = _procesar_enlace_pd(id_bck,  ini, fin, db)

    ind_datos_prim = float(valores_prim.get("ind_datos_norm", 0.0)) if valores_prim else 0.0
    ind_datos_bck  = float(valores_bck.get("ind_datos_norm",  0.0)) if valores_bck  else 0.0

    ind_datos_seg = ind_datos_prim * prim_frac + ind_datos_bck * bck_frac
    ind_total_seg = corte_ef_seg + ind_datos_seg

    return ind_total_seg, len(inconsistencias) > 0


def _calcular_ind_central(
    id_central: int, ini: datetime, fin: datetime, db: Session
) -> tuple[float | None, bool]:
    """
    Dispatcher por tipo de central.
    Retorna (ind_total_seg, inconsistencia).
    ind_total_seg=None si no hay datos suficientes.
    """
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
        _, valores, _ = _procesar_enlace_pd(id_e, ini, fin, db)
        if not valores:
            return 0.0, False
        return float(valores.get("ind_total_norm", 0.0)), False

    if tipo == 3:
        id_e = _get_enlace_backup_bcog(nemo, db)
        if not id_e:
            return None, False
        _, valores, _ = _procesar_enlace_pd(id_e, ini, fin, db)
        if not valores:
            return 0.0, False
        return float(valores.get("ind_total_norm", 0.0)), False

    if tipo == 2:
        id_prim = _get_enlace_directo(id_central, db)
        id_bck  = _get_enlace_backup_bcog(nemo, db)
        if not id_prim or not id_bck:
            return None, False
        return _calcular_tipo2(id_prim, id_bck, ini, fin, db)

    return None, False


# ─── Detalle on-the-fly para la página de detalle ────────────────────────────

def _fracciones_periodo(
    p_start: datetime, p_end: datetime, segments: list[dict]
) -> tuple[float, float]:
    """Fracción del período 30-min cubierto por primario y backup respectivamente."""
    period_sec = (p_end - p_start).total_seconds()
    if period_sec <= 0:
        return 0.0, 0.0
    prim_sec = bck_sec = 0.0
    for seg in segments:
        ov_start = max(seg["inicio"], p_start)
        ov_end   = min(seg["fin"],    p_end)
        if ov_end > ov_start:
            dur = (ov_end - ov_start).total_seconds()
            if seg["estado"] == "prim":
                prim_sec += dur
            elif seg["estado"] == "bck":
                bck_sec  += dur
    return prim_sec / period_sec, bck_sec / period_sec


def _detalle_central(
    id_central: int, ini: datetime, fin: datetime, db: Session
) -> dict:
    """
    Calcula el detalle completo de un día para mostrar en la página de detalle.
    Se ejecuta on-the-fly (no se persiste).

    Retorna un dict con:
      central, tipo, ind_total_seg, inconsistencias,
      segments (timeline), cortes_efectivos,
      periodos_dat (tabla de 30-min con fracciones y métricas),
      eventos_prim, eventos_bck (para Tipo 2)
    """
    row = db.execute(
        text("SELECT id, nemo, tipo FROM centrales WHERE id=:id LIMIT 1"),
        {"id": id_central}
    ).fetchone()
    if not row:
        return {}
    c_id, nemo, tipo = row

    def _eventos_enlace(id_e: int) -> list[dict]:
        prefix = "a" if _es_directo(id_e, db) else "b"
        col = f"asoc_{prefix}b"
        rows = db.execute(
            text(f"SELECT fecha, {col} FROM con"
                 f" WHERE id_enlace=:e AND fecha>=:ini AND fecha<=:fin AND {col} IN ('i+','e+')"
                 f" ORDER BY fecha"),
            {"e": id_e, "ini": ini, "fin": fin}
        ).fetchall()
        return [{"t": r[0].isoformat(), "tipo": r[1]} for r in rows]

    def _periodos_dat_enlace(id_e: int) -> dict[str, dict]:
        """Retorna dict keyed by fecha ISO → métricas del período."""
        df = _procesar_datos_dat_pd(ini, fin, id_e, db)
        if df.empty:
            return {}
        result: dict[str, dict] = {}
        for _, row in df.iterrows():
            key = pd.Timestamp(row["fecha"]).isoformat()
            result.setdefault(key, {
                "esperados": 0.0, "recibidos": 0.0, "buenos": 0.0,
                "norecibidos": 0.0, "invalidos": 0.0,
                "ui_norec": 0.0, "ui_noval": 0.0,
            })
            result[key]["esperados"]   += float(row.get("esperados",   0) or 0)
            result[key]["recibidos"]   += float(row.get("recibidos",   0) or 0)
            result[key]["buenos"]      += float(row.get("buenos",      0) or 0)
            result[key]["norecibidos"] += float(row.get("norecibidos", 0) or 0)
            result[key]["invalidos"]   += float(row.get("invalidos",   0) or 0)
            result[key]["ui_norec"]    += float(row.get("ui_norecibidas", 0) or 0)
            result[key]["ui_noval"]    += float(row.get("ui_invalidas",   0) or 0)
        return result

    # ─── Tipo 1 / Tipo 3 ───────────────────────────────────────────────────
    if tipo in (1, 3):
        id_e = _get_enlace_directo(id_central, db) if tipo == 1 else _get_enlace_backup_bcog(nemo, db)
        if not id_e:
            return {"central": nemo, "tipo": tipo, "error": "Enlace no encontrado"}

        _, valores, df_cortes = _procesar_enlace_pd(id_e, ini, fin, db)
        eventos = _eventos_enlace(id_e)

        # Construir segmentos de disponibilidad para timeline
        prefix = "a" if _es_directo(id_e, db) else "b"
        col    = f"asoc_{prefix}b"
        up_ini = _estado_inicial_enlace(id_e, col, ini, db)
        raw_ev = [(r["t"], r["tipo"]) for r in eventos]
        segs: list[dict] = []
        cur_t  = ini
        cur_up = up_ini
        for t_str, ev in raw_ev:
            t = datetime.fromisoformat(t_str)
            segs.append({"inicio": cur_t.isoformat(), "fin": t.isoformat(),
                         "estado": "up" if cur_up else "down",
                         "dur_seg": (t - cur_t).total_seconds()})
            cur_up = (ev == "e+")
            cur_t  = t
        segs.append({"inicio": cur_t.isoformat(), "fin": fin.isoformat(),
                     "estado": "up" if cur_up else "down",
                     "dur_seg": (fin - cur_t).total_seconds()})

        nombre_e = db.execute(
            text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_e}
        ).scalar() or str(id_e)
        cortes = [
            {"enlace": nombre_e, "inicio": s["inicio"], "fin": s["fin"], "dur_seg": s["dur_seg"]}
            for s in segs if s["estado"] == "down"
        ]

        periodos_dat = _periodos_dat_enlace(id_e)
        periodos_lista = [
            {"intervalo_fin": k, "enlace": "unico", **v}
            for k, v in sorted(periodos_dat.items())
        ]

        return {
            "central": nemo, "tipo": tipo,
            "ind_total_seg": float(valores.get("ind_total_norm", 0.0)) if valores else 0.0,
            "inconsistencias": [],
            "segments": segs,
            "cortes_efectivos": cortes,
            "periodos_dat": periodos_lista,
        }

    # ─── Tipo 2 ────────────────────────────────────────────────────────────
    id_prim = _get_enlace_directo(id_central, db)
    id_bck  = _get_enlace_backup_bcog(nemo, db)
    if not id_prim or not id_bck:
        return {"central": nemo, "tipo": tipo, "error": "Faltan enlaces (directo o backup)"}

    segments, cortes_ef, inconsistencias, corte_ef_seg = \
        _construir_timeline_tipo2(id_prim, id_bck, ini, fin, db)

    # Serializar segmentos para JSON
    segments_out = [
        {**s, "inicio": s["inicio"].isoformat(), "fin": s["fin"].isoformat()}
        for s in segments
    ]
    nombre_prim = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_prim}
    ).scalar() or "Directo"
    nombre_bck = db.execute(
        text("SELECT nombre FROM enlaces WHERE id=:id"), {"id": id_bck}
    ).scalar() or "Backup"

    def _merge_link_cortes(nombre, estados_down):
        result, cur = [], None
        for seg in segments_out:
            if seg["estado"] in estados_down:
                if cur is None:
                    cur = {"enlace": nombre, "inicio": seg["inicio"],
                           "fin": seg["fin"], "dur_seg": seg["dur_seg"]}
                else:
                    cur["fin"] = seg["fin"]
                    cur["dur_seg"] += seg["dur_seg"]
            else:
                if cur is not None:
                    result.append(cur)
                    cur = None
        if cur is not None:
            result.append(cur)
        return result

    cortes_individuales = sorted(
        _merge_link_cortes(nombre_prim, {"bck", "ninguno"}) +
        _merge_link_cortes(nombre_bck,  {"prim", "ninguno"}),
        key=lambda x: x["inicio"]
    )
    cortes_efectivos_merged = [
        {"enlace": "Sin cobertura",
         "inicio": c["inicio"].isoformat(), "fin": c["fin"].isoformat(),
         "dur_seg": c["dur_seg"]}
        for c in cortes_ef
    ]
    cortes_out = cortes_individuales + cortes_efectivos_merged
    inconsistencias_out = [
        {**inc, "t1": inc["t1"].isoformat(), "t2": inc["t2"].isoformat()}
        for inc in inconsistencias
    ]

    # ind_datos proporcional
    prim_active = sum(s["dur_seg"] for s in segments if s["estado"] == "prim")
    bck_active  = sum(s["dur_seg"] for s in segments if s["estado"] == "bck")
    total_active = prim_active + bck_active
    prim_frac = prim_active / total_active if total_active > 0 else 0.0
    bck_frac  = bck_active  / total_active if total_active > 0 else 0.0

    _, valores_prim, _ = _procesar_enlace_pd(id_prim, ini, fin, db)
    _, valores_bck,  _ = _procesar_enlace_pd(id_bck,  ini, fin, db)
    ind_datos_prim = float(valores_prim.get("ind_datos_norm", 0.0)) if valores_prim else 0.0
    ind_datos_bck  = float(valores_bck.get("ind_datos_norm",  0.0)) if valores_bck  else 0.0
    ind_datos_seg  = ind_datos_prim * prim_frac + ind_datos_bck * bck_frac
    ind_total_seg  = corte_ef_seg + ind_datos_seg

    # Construir tabla de períodos 30-min
    dat_prim = _periodos_dat_enlace(id_prim)
    dat_bck  = _periodos_dat_enlace(id_bck)
    all_fechas = sorted(set(dat_prim.keys()) | set(dat_bck.keys()))

    periodos_lista = []
    for k in all_fechas:
        p_end   = datetime.fromisoformat(k)
        p_start = p_end - timedelta(minutes=30)
        frac_p, frac_b = _fracciones_periodo(p_start, p_end, segments)
        frac_gap = max(0.0, 1.0 - frac_p - frac_b)

        def _w(d: dict, f: float) -> dict:
            return {key: val * f for key, val in d.items()} if d else {}

        prim_w = _w(dat_prim.get(k, {}), frac_p)
        bck_w  = _w(dat_bck.get(k, {}),  frac_b)

        combined = {}
        for campo in ("esperados", "recibidos", "buenos", "norecibidos", "invalidos",
                      "ui_norec", "ui_noval"):
            combined[campo] = prim_w.get(campo, 0.0) + bck_w.get(campo, 0.0)

        tipo_periodo = (
            "excluido"     if frac_gap >= 1.0 else
            "proporcional" if 0 < frac_gap < 1.0 else
            "normal"
        )

        periodos_lista.append({
            "intervalo_fin": k,
            "prim_pct": round(frac_p * 100, 1),
            "bck_pct":  round(frac_b * 100, 1),
            "gap_pct":  round(frac_gap * 100, 1),
            "tipo_periodo": tipo_periodo,
            **combined,
        })

    return {
        "central": nemo, "tipo": tipo,
        "ind_total_seg": ind_total_seg,
        "corte_efectivo_seg": corte_ef_seg,
        "ind_datos_seg": ind_datos_seg,
        "inconsistencias": inconsistencias_out,
        "segments": segments_out,
        "cortes_efectivos": cortes_out,
        "eventos_prim": _eventos_enlace(id_prim),
        "eventos_bck":  _eventos_enlace(id_bck),
        "periodos_dat": periodos_lista,
    }


# ─── Guardado de resultados ───────────────────────────────────────────────────

def guardar_resultados_dia(fecha_reporte, db: Session) -> list[dict]:
    from datetime import date as date_type
    if isinstance(fecha_reporte, date_type) and not isinstance(fecha_reporte, datetime):
        fecha_reporte = datetime(fecha_reporte.year, fecha_reporte.month, fecha_reporte.day)

    ini = fecha_reporte.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = ini + timedelta(days=1)
    fecha_dia = ini.date()

    # ── Paso 1: cortes por enlace (se mantiene igual que antes) ──────────────
    enlaces = db.execute(text("SELECT id FROM enlaces")).fetchall()
    for (id_enlace,) in enlaces:
        try:
            _, _, df_cortes = _procesar_enlace_pd(id_enlace, ini, fin, db)
            db.execute(
                text("DELETE FROM cortes_reporte WHERE id_enlace=:e AND fecha=:f"),
                {"e": id_enlace, "f": fecha_dia}
            )
            if not df_cortes.empty:
                cortes_data = [
                    {"e": id_enlace, "f": fecha_dia, "asoc": r["asoc"],
                     "inicio": r["inicio"], "fin": r["fin"],
                     "bruta": r["ind_bruta"], "neta": r["ind_neta"], "tipo": r["tipo"]}
                    for r in df_cortes[df_cortes["idenlace"] == id_enlace].to_dict("records")
                ]
                if cortes_data:
                    db.execute(
                        text("""INSERT INTO cortes_reporte
                                (id_enlace, fecha, asoc, inicio, fin, ind_bruta, ind_neta, tipo)
                                VALUES (:e, :f, :asoc, :inicio, :fin, :bruta, :neta, :tipo)"""),
                        cortes_data
                    )
            db.commit()
        except Exception:
            db.rollback()

    # ── Paso 2: indisponibilidad por central ──────────────────────────────────
    centrales = db.execute(
        text("SELECT id, nemo FROM centrales WHERE UPPER(nemo) != 'BCOG'")
    ).fetchall()
    resultados = []

    for (id_central, nemo) in centrales:
        try:
            ind_seg, inconsistencia = _calcular_ind_central(id_central, ini, fin, db)

            db.execute(
                text("DELETE FROM resultados_central WHERE id_central=:c AND fecha=:f"),
                {"c": id_central, "f": fecha_dia}
            )
            db.execute(
                text("""INSERT INTO resultados_central
                        (id_central, fecha, ind_total_seg, inconsistencia, generado_en)
                        VALUES (:c, :f, :ind, :inc, :gen)"""),
                {"c": id_central, "f": fecha_dia,
                 "ind": ind_seg, "inc": int(inconsistencia),
                 "gen": datetime.now()}
            )
            db.commit()
            resultados.append({"id_central": id_central, "nemo": nemo, "ok": True,
                                "ind_total_seg": ind_seg, "inconsistencia": inconsistencia})
        except Exception as exc:
            db.rollback()
            resultados.append({"id_central": id_central, "nemo": nemo,
                                "ok": False, "detalle": str(exc)})

    return resultados


def guardar_resultados_mes(year: int, month: int, db: Session) -> dict:
    from datetime import date as date_type
    import calendar

    hoy = date_type.today()
    primer_dia = date_type(year, month, 1)
    ultimo_dia_mes = date_type(year, month, calendar.monthrange(year, month)[1])
    ultimo_dia = min(hoy - timedelta(days=1), ultimo_dia_mes)

    if ultimo_dia < primer_dia:
        return {
            "periodo": f"{year}-{month:02d}",
            "dias_procesados": 0,
            "exitosos_total": 0,
            "fallidos_total": 0,
            "detalle_dias": [],
        }

    detalle_dias = []
    exitosos_total = 0
    fallidos_total = 0

    dia_actual = primer_dia
    while dia_actual <= ultimo_dia:
        detalle = guardar_resultados_dia(dia_actual, db)
        ok = sum(1 for r in detalle if r.get("ok"))
        fallidos = len(detalle) - ok
        exitosos_total += ok
        fallidos_total += fallidos
        detalle_dias.append({
            "fecha": str(dia_actual),
            "procesados": len(detalle),
            "exitosos": ok,
            "fallidos": fallidos,
        })
        dia_actual += timedelta(days=1)

    return {
        "periodo": f"{year}-{month:02d}",
        "dias_procesados": len(detalle_dias),
        "exitosos_total": exitosos_total,
        "fallidos_total": fallidos_total,
        "detalle_dias": detalle_dias,
    }
