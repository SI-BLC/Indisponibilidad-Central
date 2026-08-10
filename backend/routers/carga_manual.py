from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from database import get_db
from services.parser_con import parse_con_file
from services.parser_dat import parse_dat_file
from services.parser_con_iccp import parse_con_iccp_file
from services.parser_dat_iccp import parse_dat_iccp_file

router = APIRouter(prefix="/carga-manual", tags=["carga-manual"])

ID_SOTR_MANUAL = 0


def _get_enlaces_map(central_id: int, db: Session) -> dict:
    rows = db.execute(
        text("SELECT id, nombre FROM enlaces WHERE idcentral = :c"),
        {"c": central_id}
    ).fetchall()
    return {r[1]: r[0] for r in rows}


def _get_protocolo(central_id: int, db: Session) -> str:
    row = db.execute(
        text("SELECT protocolo FROM centrales WHERE id = :c"),
        {"c": central_id}
    ).fetchone()
    return row[0] if row else "elcom"


def _procesar_con_elcom(filas, info, db, dry_run):
    for fila in filas:
        existe = db.execute(
            text("SELECT 1 FROM con WHERE id_enlace=:e AND fecha=:f LIMIT 1"),
            {"e": fila["id_enlace"], "f": fila["fecha"]}
        ).fetchone()
        if existe:
            info["duplicados"] += 1
            info["log"].append(
                f"Duplicado omitido: enlace {fila['id_enlace']} "
                f"fecha {fila['fecha'].strftime('%d/%m/%Y %H:%M:%S')}"
            )
        else:
            info["a_insertar"] += 1
            if not dry_run:
                db.execute(
                    text("""INSERT INTO con
                            (fecha, id_enlace, asoc_ab, asoc_ac, asoc_bb, asoc_bc,
                             asoc_change, link, integrity_scan, elc, id_sotr)
                            VALUES (:fecha, :id_enlace, :asoc_ab, :asoc_ac, :asoc_bb, :asoc_bc,
                                    :asoc_change, :link, :integrity_scan, :elc, :id_sotr)"""),
                    fila
                )


def _procesar_dat_elcom(filas, info, db, dry_run):
    for fila in filas:
        existe = db.execute(
            text("SELECT 1 FROM dat WHERE id_enlace=:e AND fecha=:f AND gr_grupo=:g LIMIT 1"),
            {"e": fila["id_enlace"], "f": fila["fecha"], "g": fila["gr_grupo"]}
        ).fetchone()
        if existe:
            info["duplicados"] += 1
            info["log"].append(
                f"Duplicado omitido: enlace {fila['id_enlace']} "
                f"fecha {fila['fecha'].strftime('%d/%m/%Y %H:%M:%S')} "
                f"grupo {fila['gr_grupo']}"
            )
        else:
            info["a_insertar"] += 1
            if not dry_run:
                db.execute(
                    text("""INSERT INTO dat
                            (fecha, elc, id_enlace, periodo, gr_grupo, id_gr, typ, ui,
                             siz, exp, t, g, h, c, e, m, i, freq, st, transmitido, id_sotr)
                            VALUES (:fecha, :elc, :id_enlace, :periodo, :gr_grupo, :id_gr, :typ, :ui,
                                    :siz, :exp, :t, :g, :h, :c, :e, :m, :i, :freq, :st,
                                    :transmitido, :id_sotr)"""),
                    fila
                )


def _procesar_con_iccp(filas, info, db, dry_run):
    for fila in filas:
        existe = db.execute(
            text("""SELECT 1 FROM con_iccp
                    WHERE id_enlace=:e AND fecha=:f
                      AND event_type=:et AND c_state=:cs AND s_state=:ss
                    LIMIT 1"""),
            {
                "e": fila["id_enlace"], "f": fila["fecha"],
                "et": fila["event_type"],
                "cs": fila["c_state"],
                "ss": fila["s_state"],
            }
        ).fetchone()
        if existe:
            info["duplicados"] += 1
            info["log"].append(
                f"Duplicado omitido: enlace {fila['id_enlace']} "
                f"fecha {fila['fecha'].strftime('%d/%m/%Y %H:%M:%S')}"
            )
        else:
            info["a_insertar"] += 1
            if not dry_run:
                db.execute(
                    text("""INSERT INTO con_iccp
                            (fecha, id_enlace, srv, event_type, c_state, s_state, id_sotr)
                            VALUES (:fecha, :id_enlace, :srv, :event_type, :c_state, :s_state, :id_sotr)"""),
                    fila
                )


def _procesar_dat_iccp(filas, info, db, dry_run):
    for fila in filas:
        existe = db.execute(
            text("""SELECT 1 FROM dat_iccp
                    WHERE id_enlace=:e AND fecha=:f AND direction=:d AND ts=:ts
                    LIMIT 1"""),
            {"e": fila["id_enlace"], "f": fila["fecha"],
             "d": fila["direction"], "ts": fila["ts"]}
        ).fetchone()
        if existe:
            info["duplicados"] += 1
            info["log"].append(
                f"Duplicado omitido: enlace {fila['id_enlace']} "
                f"fecha {fila['fecha'].strftime('%d/%m/%Y %H:%M:%S')} "
                f"{fila['direction']} {fila['ts']}"
            )
        else:
            info["a_insertar"] += 1
            if not dry_run:
                db.execute(
                    text("""INSERT INTO dat_iccp
                            (fecha, id_enlace, srv, periodo, direction, ts, ds,
                             siz, exp, t, g, h, c, e, m, i, id_sotr)
                            VALUES (:fecha, :id_enlace, :srv, :periodo, :direction, :ts, :ds,
                                    :siz, :exp, :t, :g, :h, :c, :e, :m, :i, :id_sotr)"""),
                    fila
                )


def _procesar_archivos(central_id: int, files: List[UploadFile], db: Session, dry_run: bool):
    enlaces_map = _get_enlaces_map(central_id, db)
    protocolo = _get_protocolo(central_id, db)
    es_iccp = protocolo == "iccp"

    resultado = {
        "central_id": central_id,
        "enlaces_central": list(enlaces_map.keys()),
        "archivos": [],
        "resumen": {
            "con_a_insertar": 0,
            "dat_a_insertar": 0,
            "con_duplicados": 0,
            "dat_duplicados": 0,
        }
    }

    for upload in files:
        nombre = upload.filename or ""
        ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        contenido = upload.file.read().decode("latin-1")

        info = {"nombre": nombre, "tipo": ext, "log": [], "a_insertar": 0, "duplicados": 0}

        if ext == "con":
            if es_iccp:
                filas, parse_log = parse_con_iccp_file(contenido, enlaces_map, ID_SOTR_MANUAL)
                info["log"].extend(parse_log)
                _procesar_con_iccp(filas, info, db, dry_run)
            else:
                filas, parse_log = parse_con_file(contenido, enlaces_map, ID_SOTR_MANUAL)
                info["log"].extend(parse_log)
                _procesar_con_elcom(filas, info, db, dry_run)
            resultado["resumen"]["con_a_insertar"] += info["a_insertar"]
            resultado["resumen"]["con_duplicados"] += info["duplicados"]

        elif ext == "dat":
            if es_iccp:
                filas, parse_log = parse_dat_iccp_file(contenido, enlaces_map, ID_SOTR_MANUAL)
                info["log"].extend(parse_log)
                _procesar_dat_iccp(filas, info, db, dry_run)
            else:
                filas, parse_log = parse_dat_file(contenido, enlaces_map, ID_SOTR_MANUAL)
                info["log"].extend(parse_log)
                _procesar_dat_elcom(filas, info, db, dry_run)
            resultado["resumen"]["dat_a_insertar"] += info["a_insertar"]
            resultado["resumen"]["dat_duplicados"] += info["duplicados"]

        else:
            info["log"].append(f"Extensión desconocida '{ext}' — archivo ignorado")

        resultado["archivos"].append(info)

    if not dry_run:
        db.commit()

    return resultado


@router.post("/analizar")
def analizar(
    central_id: int = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    return _procesar_archivos(central_id, files, db, dry_run=True)


@router.post("/confirmar")
def confirmar(
    central_id: int = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    return _procesar_archivos(central_id, files, db, dry_run=False)
