from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/grupos", tags=["Grupos"])


@router.get("/", response_model=list[schemas.GrupoOut])
def get_grupos(idenlace: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Grupo)
    if idenlace is not None:
        query = query.filter(models.Grupo.idenlace == idenlace)
    return query.all()


@router.post("/", response_model=schemas.GrupoOut, status_code=201)
def crear_grupo(grupo: schemas.GrupoCreate, db: Session = Depends(get_db)):
    db_grupo = models.Grupo(**grupo.model_dump())
    db.add(db_grupo)
    db.commit()
    db.refresh(db_grupo)
    return db_grupo


@router.put("/{grupo_id}", response_model=schemas.GrupoOut)
def actualizar_grupo(grupo_id: int, data: schemas.GrupoUpdate, db: Session = Depends(get_db)):
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(grupo, field, value)
    db.commit()
    db.refresh(grupo)
    return grupo


@router.delete("/{grupo_id}", status_code=204)
def eliminar_grupo(grupo_id: int, db: Session = Depends(get_db)):
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    db.delete(grupo)
    db.commit()
