from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import models
import schemas

router = APIRouter(prefix="/cogb55", tags=["COGB55"])

ID_CONCENTRADOR = 110
ID_ENLACE_CAMM = 476


@router.get("", response_model=list[schemas.Cogb55CentralGrupos])
def listar(db: Session = Depends(get_db)):
    """Todas las centrales con grupos asignados en COGB55."""
    rows = db.execute(text("""
        SELECT g.id_central, c.nemo, GROUP_CONCAT(g.grupo ORDER BY g.grupo) as grupos
        FROM cogb55_grupos g
        JOIN centrales c ON c.id = g.id_central
        GROUP BY g.id_central, c.nemo
        ORDER BY c.nemo
    """)).fetchall()
    return [
        schemas.Cogb55CentralGrupos(
            id_central=r[0],
            nemo=r[1],
            grupos=[int(x) for x in r[2].split(",")] if r[2] else [],
        )
        for r in rows
    ]


@router.get("/grupos-disponibles")
def grupos_disponibles(db: Session = Depends(get_db)):
    """Grupos que existen en dat para COGB_CAMM y aún no están asignados."""
    rows = db.execute(text("""
        SELECT DISTINCT d.gr_grupo
        FROM dat d
        WHERE d.id_enlace = :enlace
        AND d.gr_grupo NOT IN (SELECT grupo FROM cogb55_grupos)
        ORDER BY d.gr_grupo
    """), {"enlace": ID_ENLACE_CAMM}).fetchall()
    return [r[0] for r in rows]


@router.get("/centrales-disponibles")
def centrales_disponibles(db: Session = Depends(get_db)):
    """Centrales que aún no tienen grupos asignados en COGB55."""
    rows = db.execute(text("""
        SELECT c.id, c.nemo
        FROM centrales c
        WHERE c.id NOT IN (SELECT DISTINCT id_central FROM cogb55_grupos)
        ORDER BY c.nemo
    """)).fetchall()
    return [{"id": r[0], "nemo": r[1]} for r in rows]


@router.get("/{id_central}", response_model=schemas.Cogb55CentralGrupos)
def obtener(id_central: int, db: Session = Depends(get_db)):
    """Grupos asignados a una central."""
    central = db.execute(
        text("SELECT nemo FROM centrales WHERE id=:id"), {"id": id_central}
    ).scalar()
    if not central:
        raise HTTPException(404, "Central no encontrada")
    grupos = db.execute(
        text("SELECT grupo FROM cogb55_grupos WHERE id_central=:c ORDER BY grupo"),
        {"c": id_central},
    ).fetchall()
    return schemas.Cogb55CentralGrupos(
        id_central=id_central, nemo=central, grupos=[r[0] for r in grupos]
    )


@router.put("/{id_central}", response_model=schemas.Cogb55CentralGrupos)
def asignar(id_central: int, body: schemas.Cogb55SetGrupos, db: Session = Depends(get_db)):
    """Reemplaza los grupos asignados a una central."""
    central = db.execute(
        text("SELECT nemo FROM centrales WHERE id=:id"), {"id": id_central}
    ).scalar()
    if not central:
        raise HTTPException(404, "Central no encontrada")
    db.execute(
        text("DELETE FROM cogb55_grupos WHERE id_central=:c"), {"c": id_central}
    )
    for g in body.grupos:
        db.add(models.Cogb55Grupo(id_central=id_central, grupo=g))
    db.commit()
    return schemas.Cogb55CentralGrupos(
        id_central=id_central, nemo=central, grupos=sorted(body.grupos)
    )


@router.delete("/{id_central}", status_code=204)
def eliminar(id_central: int, db: Session = Depends(get_db)):
    """Elimina todos los grupos de una central."""
    db.execute(
        text("DELETE FROM cogb55_grupos WHERE id_central=:c"), {"c": id_central}
    )
    db.commit()
