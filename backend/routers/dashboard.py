from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/", response_model=list[schemas.DashboardCentral])
def get_dashboard(db: Session = Depends(get_db)):
    centrales = db.query(models.Central).all()
    resultado = []
    for c in centrales:
        cant_enlaces = (
            db.query(models.Enlace)
            .filter(models.Enlace.idcentral == c.id)
            .count()
        )
        enlaces_ids = [
            e.id
            for e in db.query(models.Enlace)
            .filter(models.Enlace.idcentral == c.id)
            .all()
        ]
        tiene_grupos = False
        if enlaces_ids:
            tiene_grupos = (
                db.query(models.Grupo)
                .filter(models.Grupo.idenlace.in_(enlaces_ids))
                .count()
            ) > 0
        resultado.append(
            schemas.DashboardCentral(
                id=c.id,
                nemo=c.nemo,
                tipo=c.tipo,
                cant_enlaces=cant_enlaces,
                tiene_grupos=tiene_grupos,
            )
        )
    return resultado
