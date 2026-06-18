from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/transfersets", tags=["TransferSets"])

DEFAULT_TS = ["TS_DOM_00000", "TS_DOM_00001", "TS_DOM_00002"]


@router.get("/", response_model=list[schemas.TransferSetOut])
def get_transfersets(id_enlace: int, db: Session = Depends(get_db)):
    return db.query(models.TransferSet).filter(
        models.TransferSet.id_enlace == id_enlace
    ).all()


@router.post("/", response_model=schemas.TransferSetOut, status_code=201)
def crear_transferset(ts: schemas.TransferSetCreate, db: Session = Depends(get_db)):
    existing = db.query(models.TransferSet).filter(
        models.TransferSet.id_enlace == ts.id_enlace,
        models.TransferSet.ts_nombre == ts.ts_nombre,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"TransferSet '{ts.ts_nombre}' ya existe para este enlace")
    db_ts = models.TransferSet(**ts.model_dump())
    db.add(db_ts)
    db.commit()
    db.refresh(db_ts)
    return db_ts


@router.post("/defaults/{id_enlace}", response_model=list[schemas.TransferSetOut], status_code=201)
def crear_defaults(id_enlace: int, db: Session = Depends(get_db)):
    """Crea los 3 TransferSets por defecto para un enlace ICCP."""
    created = []
    for ts_nombre in DEFAULT_TS:
        existing = db.query(models.TransferSet).filter(
            models.TransferSet.id_enlace == id_enlace,
            models.TransferSet.ts_nombre == ts_nombre,
        ).first()
        if not existing:
            db_ts = models.TransferSet(id_enlace=id_enlace, ts_nombre=ts_nombre, tipo=0, calcular=1)
            db.add(db_ts)
            created.append(db_ts)
    db.commit()
    for ts in created:
        db.refresh(ts)
    return created


@router.put("/{ts_id}", response_model=schemas.TransferSetOut)
def actualizar_transferset(ts_id: int, data: schemas.TransferSetUpdate, db: Session = Depends(get_db)):
    ts = db.query(models.TransferSet).filter(models.TransferSet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="TransferSet no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(ts, field, value)
    db.commit()
    db.refresh(ts)
    return ts


@router.delete("/{ts_id}", status_code=204)
def eliminar_transferset(ts_id: int, db: Session = Depends(get_db)):
    ts = db.query(models.TransferSet).filter(models.TransferSet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="TransferSet no encontrado")
    db.delete(ts)
    db.commit()
