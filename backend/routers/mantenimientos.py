from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
import models
import schemas

router = APIRouter(prefix="/mantenimientos", tags=["Mantenimientos"])


@router.get("/", response_model=list[schemas.MantenimientoOut])
def get_mantenimientos(idenlace: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Mantenimiento)
    if idenlace is not None:
        query = query.filter(models.Mantenimiento.idenlace == idenlace)
    return query.order_by(models.Mantenimiento.inicio).all()


@router.post("/", response_model=schemas.MantenimientoOut, status_code=201)
def crear_mantenimiento(
    mant: schemas.MantenimientoCreate, db: Session = Depends(get_db)
):
    if mant.inicio >= mant.fin:
        raise HTTPException(
            status_code=400, detail="La fecha de inicio debe ser anterior a la de fin"
        )
    if mant.inicio < datetime.now():
        raise HTTPException(
            status_code=400, detail="No se puede programar un mantenimiento en el pasado"
        )
    # Verificar solapamientos
    solapado = (
        db.query(models.Mantenimiento)
        .filter(
            models.Mantenimiento.idenlace == mant.idenlace,
            models.Mantenimiento.inicio < mant.fin,
            models.Mantenimiento.fin > mant.inicio,
        )
        .first()
    )
    if solapado:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un mantenimiento que se solapa con el período indicado",
        )
    db_mant = models.Mantenimiento(**mant.model_dump())
    db.add(db_mant)
    db.commit()
    db.refresh(db_mant)
    return db_mant


@router.delete("/{mant_id}", status_code=204)
def eliminar_mantenimiento(mant_id: int, db: Session = Depends(get_db)):
    mant = (
        db.query(models.Mantenimiento)
        .filter(models.Mantenimiento.id == mant_id)
        .first()
    )
    if not mant:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado")
    db.delete(mant)
    db.commit()
