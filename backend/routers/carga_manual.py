from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from database import get_db
from services.parser_con import parse_con_file
from services.parser_dat import parse_dat_file

router = APIRouter(prefix="/carga-manual", tags=["carga-manual"])

ID_SOTR_MANUAL = 0


def _get_enlaces_map(central_id: int, db: Session) -> dict:
    """Retorna {nombre_enlace: id_enlace} para la central dada."""
    rows = db.execute(
        text("SELECT id, nombre FROM enlaces WHERE idcentral = :c"),
        {"c": central_id}
    ).fetchall()
    return {r[1]: r[0] for r in rows}


def _procesar_archivos(central_id: int, files: List[UploadFile], db: Session, dry_run: bool):
    enlaces_map = _get_enlaces_map(central_id, db)

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
            filas, parse_log = parse_con_file(contenido, enlaces_map, ID_SOTR_MANUAL)
            info["log"].extend(parse_log)

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
            resultado["resumen"]["con_a_insertar"] += info["a_insertar"]
            resultado["resumen"]["con_duplicados"] += info["duplicados"]

        elif ext == "dat":
            filas, parse_log = parse_dat_file(contenido, enlaces_map, ID_SOTR_MANUAL)
            info["log"].extend(parse_log)

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
