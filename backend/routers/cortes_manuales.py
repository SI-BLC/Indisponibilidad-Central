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
    fecha: str  # ISO datetime del i+ a insertar


class CorteManualOut(BaseModel):
    id: int
    id_enlace: int
    fecha: str


def _get_asoc_cols(id_enlace: int, db: Session) -> list[str]:
    """Retorna las dos columnas de asociación del enlace (ab/ac o bb/bc)."""
    idtipo = db.execute(
        text("SELECT idtipo FROM enlaces WHERE id=:id"), {"id": id_enlace}
    ).scalar()
    if idtipo == 2:
        return ["asoc_ab", "asoc_ac"]
    return ["asoc_bb", "asoc_bc"]


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

    fecha = datetime.fromisoformat(body.fecha)
    cols = _get_asoc_cols(body.id_enlace, db)

    protocolo = db.execute(
        text("""SELECT c.protocolo FROM centrales c
                JOIN enlaces e ON e.idcentral = c.id
                WHERE e.id = :eid"""),
        {"eid": body.id_enlace}
    ).scalar() or "elcom"

    if protocolo == "iccp":
        db.execute(
            text("""INSERT INTO con_iccp (fecha, id_enlace, asoc_c, asoc_s, id_sotr)
                     VALUES (:f, :e, 'i+', 'i+', :sotr)"""),
            {"f": fecha, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )
    else:
        set_clause = ", ".join(f"{c} = 'i+'" for c in cols)
        db.execute(
            text(f"""INSERT INTO con (fecha, id_enlace, {', '.join(cols)}, id_sotr, asoc_change)
                     VALUES (:f, :e, {', '.join(["'i+'"] * len(cols))}, :sotr, 'manual')"""),
            {"f": fecha, "e": body.id_enlace, "sotr": ID_SOTR_MANUAL}
        )

    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.commit()

    return CorteManualOut(
        id=new_id,
        id_enlace=body.id_enlace,
        fecha=body.fecha,
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
