from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/comentarios", tags=["Comentarios"])


class ComentarioCreate(BaseModel):
    id_central: int
    fecha_dia: str
    tipo: str  # "corte" | "dat"
    duracion_seg: Optional[float] = None
    fecha_inicio: str
    fecha_fin: str
    texto: str


class ComentarioUpdate(BaseModel):
    texto: str


COLS = "id, id_central, fecha_dia, tipo, duracion_seg, fecha_inicio, fecha_fin, texto, usuario, created_at, updated_at"


def _row_to_dict(row) -> dict:
    return {
        "id":           row[0],
        "id_central":   row[1],
        "fecha_dia":    str(row[2]),
        "tipo":         row[3],
        "duracion_seg": row[4],
        "fecha_inicio": row[5],
        "fecha_fin":    row[6],
        "texto":        row[7],
        "usuario":      row[8],
        "created_at":   row[9].isoformat() if row[9] else None,
        "updated_at":   row[10].isoformat() if row[10] else None,
    }


@router.get("")
def listar_comentarios(
    id_central: int,
    fecha_dia: str,
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
):
    conditions = ["id_central = :c", "fecha_dia = :f"]
    params: dict = {"c": id_central, "f": fecha_dia}
    if tipo:
        conditions.append("tipo = :t")
        params["t"] = tipo
    where = " AND ".join(conditions)
    rows = db.execute(
        text(f"SELECT {COLS} FROM comentarios WHERE {where} ORDER BY created_at"),
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.post("", status_code=201)
def crear_comentario(
    body: ComentarioCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    if body.tipo not in ("corte", "dat"):
        raise HTTPException(400, "tipo debe ser 'corte' o 'dat'")
    usuario = request.state.user["sub"]
    now = datetime.now()
    db.execute(
        text("""INSERT INTO comentarios
                (id_central, fecha_dia, tipo, duracion_seg, fecha_inicio, fecha_fin, texto, usuario, created_at, updated_at)
                VALUES (:c, :fd, :t, :ds, :fi, :ff, :txt, :u, :ca, :ua)"""),
        {
            "c": body.id_central, "fd": body.fecha_dia, "t": body.tipo,
            "ds": body.duracion_seg,
            "fi": body.fecha_inicio, "ff": body.fecha_fin,
            "txt": body.texto, "u": usuario, "ca": now, "ua": now,
        },
    )
    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.commit()
    row = db.execute(
        text(f"SELECT {COLS} FROM comentarios WHERE id = :id"), {"id": new_id}
    ).fetchone()
    return _row_to_dict(row)


@router.put("/{id_comentario}")
def actualizar_comentario(
    id_comentario: int,
    body: ComentarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    row = db.execute(
        text(f"SELECT {COLS} FROM comentarios WHERE id = :id"), {"id": id_comentario}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Comentario no encontrado")
    if row[8] != usuario:
        raise HTTPException(403, "Solo el autor puede editar este comentario")
    db.execute(
        text("UPDATE comentarios SET texto = :t, updated_at = :ua WHERE id = :id"),
        {"t": body.texto, "ua": datetime.now(), "id": id_comentario},
    )
    db.commit()
    row = db.execute(
        text(f"SELECT {COLS} FROM comentarios WHERE id = :id"), {"id": id_comentario}
    ).fetchone()
    return _row_to_dict(row)


@router.delete("/{id_comentario}", status_code=204)
def eliminar_comentario(
    id_comentario: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = request.state.user["sub"]
    row = db.execute(
        text(f"SELECT {COLS} FROM comentarios WHERE id = :id"), {"id": id_comentario}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Comentario no encontrado")
    if row[8] != usuario:
        raise HTTPException(403, "Solo el autor puede eliminar este comentario")
    db.execute(text("DELETE FROM comentarios WHERE id = :id"), {"id": id_comentario})
    db.commit()
