from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/datasets", tags=["DataSets"])

DEFAULT_DS = ["DS_1_0", "DS_2_0", "DS_3_0"]


@router.get("/", response_model=list[schemas.DataSetOut])
def get_datasets(id_enlace: int, db: Session = Depends(get_db)):
    return db.query(models.DataSet).filter(
        models.DataSet.id_enlace == id_enlace
    ).all()


@router.post("/", response_model=schemas.DataSetOut, status_code=201)
def crear_dataset(ds: schemas.DataSetCreate, db: Session = Depends(get_db)):
    existing = db.query(models.DataSet).filter(
        models.DataSet.id_enlace == ds.id_enlace,
        models.DataSet.ds_nombre == ds.ds_nombre,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"DataSet '{ds.ds_nombre}' ya existe para este enlace")
    db_ds = models.DataSet(**ds.model_dump())
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    return db_ds


@router.post("/defaults/{id_enlace}", response_model=list[schemas.DataSetOut], status_code=201)
def crear_defaults(id_enlace: int, db: Session = Depends(get_db)):
    """Crea los 3 DataSets por defecto para un enlace ICCP."""
    created = []
    for ds_nombre in DEFAULT_DS:
        existing = db.query(models.DataSet).filter(
            models.DataSet.id_enlace == id_enlace,
            models.DataSet.ds_nombre == ds_nombre,
        ).first()
        if not existing:
            db_ds = models.DataSet(id_enlace=id_enlace, ds_nombre=ds_nombre, tipo=0, calcular=1)
            db.add(db_ds)
            created.append(db_ds)
    db.commit()
    for ds in created:
        db.refresh(ds)
    return created


@router.put("/{ds_id}", response_model=schemas.DataSetOut)
def actualizar_dataset(ds_id: int, data: schemas.DataSetUpdate, db: Session = Depends(get_db)):
    ds = db.query(models.DataSet).filter(models.DataSet.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSet no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(ds, field, value)
    db.commit()
    db.refresh(ds)
    return ds


@router.delete("/{ds_id}", status_code=204)
def eliminar_dataset(ds_id: int, db: Session = Depends(get_db)):
    ds = db.query(models.DataSet).filter(models.DataSet.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSet no encontrado")
    db.delete(ds)
    db.commit()
