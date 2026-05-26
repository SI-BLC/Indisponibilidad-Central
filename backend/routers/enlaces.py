from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/enlaces", tags=["Enlaces"])


@router.get("/", response_model=list[schemas.EnlaceOut])
def get_enlaces(idcentral: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Enlace)
    if idcentral is not None:
        query = query.filter(models.Enlace.idcentral == idcentral)
    return query.all()


@router.get("/{enlace_id}", response_model=schemas.EnlaceOut)
def get_enlace(enlace_id: int, db: Session = Depends(get_db)):
    enlace = db.query(models.Enlace).filter(models.Enlace.id == enlace_id).first()
    if not enlace:
        raise HTTPException(status_code=404, detail="Enlace no encontrado")
    return enlace


@router.post("/", response_model=schemas.EnlaceOut, status_code=201)
def crear_enlace(enlace: schemas.EnlaceCreate, db: Session = Depends(get_db)):
    db_enlace = models.Enlace(**enlace.model_dump())
    db.add(db_enlace)
    db.commit()
    db.refresh(db_enlace)
    return db_enlace


@router.put("/{enlace_id}", response_model=schemas.EnlaceOut)
def actualizar_enlace(enlace_id: int, data: schemas.EnlaceUpdate, db: Session = Depends(get_db)):
    enlace = db.query(models.Enlace).filter(models.Enlace.id == enlace_id).first()
    if not enlace:
        raise HTTPException(status_code=404, detail="Enlace no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(enlace, field, value)
    db.commit()
    db.refresh(enlace)
    return enlace


@router.delete("/{enlace_id}", status_code=204)
def eliminar_enlace(enlace_id: int, db: Session = Depends(get_db)):
    enlace = db.query(models.Enlace).filter(models.Enlace.id == enlace_id).first()
    if not enlace:
        raise HTTPException(status_code=404, detail="Enlace no encontrado")
    db.delete(enlace)
    db.commit()
