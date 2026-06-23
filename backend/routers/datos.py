from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from database import get_db
import models
import schemas

router = APIRouter(prefix="/datos", tags=["Datos"])


@router.get("/con", response_model=list[schemas.ConOut])
def get_datos_con(
    ids_enlace: Optional[List[int]] = Query(default=None),
    fecha_inicio: Optional[datetime] = Query(default=None),
    fecha_fin: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Conexion)
    if ids_enlace:
        q = q.filter(models.Conexion.id_enlace.in_(ids_enlace))
    if fecha_inicio:
        q = q.filter(models.Conexion.fecha >= fecha_inicio)
    if fecha_fin:
        q = q.filter(models.Conexion.fecha <= fecha_fin)
    return q.order_by(models.Conexion.fecha.asc()).limit(5000).all()


@router.get("/dat", response_model=list[schemas.DatOut])
def get_datos_dat(
    ids_enlace: Optional[List[int]] = Query(default=None),
    fecha_inicio: Optional[datetime] = Query(default=None),
    fecha_fin: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Dat)
    if ids_enlace:
        q = q.filter(models.Dat.id_enlace.in_(ids_enlace))
    if fecha_inicio:
        q = q.filter(models.Dat.fecha >= fecha_inicio)
    if fecha_fin:
        q = q.filter(models.Dat.fecha <= fecha_fin)
    return q.order_by(models.Dat.fecha.asc()).limit(5000).all()


@router.get("/con_iccp", response_model=list[schemas.ConIccpOut])
def get_datos_con_iccp(
    ids_enlace: Optional[List[int]] = Query(default=None),
    fecha_inicio: Optional[datetime] = Query(default=None),
    fecha_fin: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(models.ConexionIccp)
    if ids_enlace:
        q = q.filter(models.ConexionIccp.id_enlace.in_(ids_enlace))
    if fecha_inicio:
        q = q.filter(models.ConexionIccp.fecha >= fecha_inicio)
    if fecha_fin:
        q = q.filter(models.ConexionIccp.fecha <= fecha_fin)
    return q.order_by(models.ConexionIccp.fecha.asc()).limit(5000).all()


@router.get("/dat_iccp", response_model=list[schemas.DatIccpOut])
def get_datos_dat_iccp(
    ids_enlace: Optional[List[int]] = Query(default=None),
    fecha_inicio: Optional[datetime] = Query(default=None),
    fecha_fin: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(models.DatIccp)
    if ids_enlace:
        q = q.filter(models.DatIccp.id_enlace.in_(ids_enlace))
    if fecha_inicio:
        q = q.filter(models.DatIccp.fecha >= fecha_inicio)
    if fecha_fin:
        q = q.filter(models.DatIccp.fecha <= fecha_fin)
    return q.order_by(models.DatIccp.fecha.asc()).limit(5000).all()
