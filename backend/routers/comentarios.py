from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/comentarios", tags=["Comentarios"])


class ComentarioBody(BaseModel):
    texto: str


def _row_to_dict(row) -> dict:
    return {
        "id":         row[0],
        "id_central": row[1],
        "fecha":      str(row[2]),
        "texto":      row[3],
        "usuario":    row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "updated_at": row[6].isoformat() if row[6] else None,
    }


def _get_row(id_central: int, fecha: str, db: Session):
    return db.execute(
        text("""SELECT id, id_central, fecha, texto, usuario, created_at, updated_at
                FROM comentarios WHERE id_central=:c AND fecha=:f LIMIT 1"""),
        {"c": id_central, "f": fecha}
    ).fetchone()


@router.get("/{id_central}/{fecha}")
def get_comentario(id_central: int, fecha: str, db: Session = Depends(get_db)):
    row = _get_row(id_central, fecha, db)
    return _row_to_dict(row) if row else None


@router.post("/{id_central}/{fecha}", status_code=201)
def crear_comentario(
    id_central: int, fecha: str,
    body: ComentarioBody,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    if _get_row(id_central, fecha, db):
        raise HTTPException(status_code=409, detail="Ya existe un comentario para este resultado")
    now = datetime.now()
    db.execute(
        text("""INSERT INTO comentarios (id_central, fecha, texto, usuario, created_at, updated_at)
                VALUES (:c, :f, :t, :u, :ca, :ua)"""),
        {"c": id_central, "f": fecha, "t": body.texto, "u": usuario, "ca": now, "ua": now},
    )
    db.commit()
    return _row_to_dict(_get_row(id_central, fecha, db))


@router.put("/{id_central}/{fecha}")
def actualizar_comentario(
    id_central: int, fecha: str,
    body: ComentarioBody,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    row = _get_row(id_central, fecha, db)
    if not row:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if row[4] != usuario:
        raise HTTPException(status_code=403, detail="Solo el autor puede editar este comentario")
    db.execute(
        text("UPDATE comentarios SET texto=:t, updated_at=:ua WHERE id_central=:c AND fecha=:f"),
        {"t": body.texto, "ua": datetime.now(), "c": id_central, "f": fecha},
    )
    db.commit()
    return _row_to_dict(_get_row(id_central, fecha, db))


@router.delete("/{id_central}/{fecha}", status_code=204)
def eliminar_comentario(
    id_central: int, fecha: str,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    row = _get_row(id_central, fecha, db)
    if not row:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if row[4] != usuario:
        raise HTTPException(status_code=403, detail="Solo el autor puede eliminar este comentario")
    db.execute(
        text("DELETE FROM comentarios WHERE id_central=:c AND fecha=:f"),
        {"c": id_central, "f": fecha},
    )
    db.commit()
