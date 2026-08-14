from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from database import get_db

router = APIRouter(prefix="/cortes-manuales", tags=["Cortes Manuales"])

ID_SOTR_MANUAL = 0


class CorteManualIn(BaseModel):
    id_enlace: int
    fecha_inicio: str  # ISO datetime
    fecha_fin: str     # ISO datetime


class CorteManualOut(BaseModel):
    id_inicio: int
    id_fin: int
    id_enlace: int
    fecha_inicio: str
    fecha_fin: str


def _get_asoc_col(id_enlace: int, db: Session) -> str:
    """Determina la columna de asociación correcta para el enlace."""
    idtipo = db.execute(
        text("SELECT idtipo FROM enlaces WHERE id=:id"), {"id": id_enlace}
    ).scalar()
    if idtipo == 2:
        return "asoc_ab"
    return "asoc_bb"


@router.post("/", response_model=CorteManualOut)
def insertar_corte_manual(
    body: CorteManualIn,
    db: Session = Depends(get_db),
):
    enlace = db.execute(
        text("SELECT id, nombre FROM enlaces WHERE id=:id"),
        {"id": body.id_enlace}
    ).fetchone()
    if not enlace:
        raise HTTPException(404, "Enlace no encontrado")

    ini = datetime.fromisoformat(body.fecha_inicio)
    fin = datetime.fromisoformat(body.fecha_fin)
    if fin <= ini:
        raise HTTPException(400, "La fecha fin debe ser posterior a la fecha inicio")

    col = _get_asoc_col(body.id_enlace, db)

    protocolo = db.execute(
        text("""SELECT c.protocolo FROM centrales c
                JOIN enlaces e ON e.idcentral = c.id
                WHERE e.id = :eid"""),
        {"eid": body.id_enlace}
    ).scalar() or "elcom"
    tabla = "con_iccp" if protocolo == "iccp" else "con"

    if tabla == "con":
        db.execute(
            text(f"""INSERT INTO con (fecha, id_enlace, {col}, id_sotr, asoc_change)
                     VALUES (:f, :e, 'i+', :sotr, 'manual')"""),
            {"f": ini, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )
        id_inicio = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        db.execute(
            text(f"""INSERT INTO con (fecha, id_enlace, {col}, id_sotr, asoc_change)
                     VALUES (:f, :e, 'e+', :sotr, 'manual')"""),
            {"f": fin, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )
        id_fin = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    else:
        srv_col = "asoc_c" if col.endswith("b") else "asoc_s"
        db.execute(
            text(f"""INSERT INTO con_iccp (fecha, id_enlace, {srv_col}, id_sotr)
                     VALUES (:f, :e, 'i+', :sotr)"""),
            {"f": ini, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )
        id_inicio = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        db.execute(
            text(f"""INSERT INTO con_iccp (fecha, id_enlace, {srv_col}, id_sotr)
                     VALUES (:f, :e, 'e+', :sotr)"""),
            {"f": fin, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )
        id_fin = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

    db.commit()

    return CorteManualOut(
        id_inicio=id_inicio,
        id_fin=id_fin,
        id_enlace=body.id_enlace,
        fecha_inicio=body.fecha_inicio,
        fecha_fin=body.fecha_fin,
    )


@router.get("/")
def listar_cortes_manuales(
    id_enlace: Optional[int] = None,
    fecha: Optional[str] = None,
    db: Session = Depends(get_db),
):
    conditions = ["asoc_change = 'manual'"]
    params: dict = {}
    if id_enlace:
        conditions.append("id_enlace = :e")
        params["e"] = id_enlace
    if fecha:
        conditions.append("DATE(fecha) = :f")
        params["f"] = fecha

    where = " AND ".join(conditions)
    rows = db.execute(
        text(f"""SELECT id, fecha, id_enlace, asoc_ab, asoc_ac, asoc_bb, asoc_bc
                 FROM con WHERE {where} ORDER BY fecha DESC LIMIT 200"""),
        params,
    ).fetchall()

    return [
        {
            "id": r[0],
            "fecha": r[1].isoformat() if r[1] else None,
            "id_enlace": r[2],
            "tipo": next(
                (v for v in [r[3], r[4], r[5], r[6]] if v in ("i+", "e+")), None
            ),
        }
        for r in rows
    ]


@router.delete("/{id_con}")
def eliminar_corte_manual(
    id_con: int,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT id, asoc_change FROM con WHERE id=:id"),
        {"id": id_con}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    if row[1] != "manual":
        raise HTTPException(400, "Solo se pueden eliminar registros manuales")

    db.execute(text("DELETE FROM con WHERE id=:id"), {"id": id_con})
    db.commit()
    return {"ok": True}
