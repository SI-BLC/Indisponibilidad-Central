from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx
from database import get_db
from config import settings
import models
import schemas

router = APIRouter(prefix="/centrales", tags=["Centrales"])


@router.get("", response_model=list[schemas.CentralOut])
def get_centrales(db: Session = Depends(get_db)):
    return db.query(models.Central).all()


@router.get("/{central_id}", response_model=schemas.CentralOut)
def get_central(central_id: int, db: Session = Depends(get_db)):
    central = db.query(models.Central).filter(models.Central.id == central_id).first()
    if not central:
        raise HTTPException(status_code=404, detail="Central no encontrada")
    return central


@router.post("", response_model=schemas.CentralOut, status_code=201)
def crear_central(central: schemas.CentralCreate, db: Session = Depends(get_db)):
    db_central = models.Central(**central.model_dump())
    db.add(db_central)
    db.commit()
    db.refresh(db_central)
    return db_central


@router.put("/{central_id}", response_model=schemas.CentralOut)
def actualizar_central(
    central_id: int, data: schemas.CentralUpdate, db: Session = Depends(get_db)
):
    central = db.query(models.Central).filter(models.Central.id == central_id).first()
    if not central:
        raise HTTPException(status_code=404, detail="Central no encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(central, field, value)
    db.commit()
    db.refresh(central)
    return central


@router.delete("/{central_id}", status_code=204)
def eliminar_central(central_id: int, db: Session = Depends(get_db)):
    central = db.query(models.Central).filter(models.Central.id == central_id).first()
    if not central:
        raise HTTPException(status_code=404, detail="Central no encontrada")

    # Obtener IDs de enlaces de esta central
    enlace_ids = [r[0] for r in db.execute(
        text("SELECT id FROM enlaces WHERE idcentral = :cid"), {"cid": central_id}
    ).fetchall()]

    if enlace_ids:
        ids_sql = ",".join(str(i) for i in enlace_ids)
        # Eliminar datos relacionados a los enlaces, de hoja a raíz
        db.execute(text(f"DELETE FROM grupos          WHERE idenlace   IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM mantenimientos  WHERE idenlace   IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM resultados_reporte WHERE id_enlace IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM cortes_reporte  WHERE id_enlace  IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM con             WHERE id_enlace  IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM dat             WHERE id_enlace  IN ({ids_sql})"))
        db.execute(text(f"DELETE FROM enlaces         WHERE idcentral  = :cid"), {"cid": central_id})

    db.delete(central)
    db.commit()


def _node_base_url(ip: str, ssl: int = 0) -> str:
    if ssl:
        return f"https://{ip}:8443"
    return f"http://{ip}:8089"


def _node_auth(ssl: int = 0) -> httpx.BasicAuth | None:
    if ssl and settings.NODE_HTTPS_USER:
        return httpx.BasicAuth(settings.NODE_HTTPS_USER, settings.NODE_HTTPS_PASS)
    return None


@router.get("/checkenlaces/{ip}", response_class=PlainTextResponse)
def check_enlaces(ip: str, ssl: int = 0):
    base = _node_base_url(ip, ssl)
    try:
        with httpx.Client(timeout=30, verify=False, auth=_node_auth(ssl)) as client:
            response = client.get(f"{base}/checkenlaces")
            response.raise_for_status()
            return response.text
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout al conectar con {base}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con {base} — {e}")


@router.get("/checkgrupos/{ip}", response_class=PlainTextResponse)
def check_grupos(ip: str, nombre_enlace: str, ssl: int = 0):
    base = _node_base_url(ip, ssl)
    try:
        with httpx.Client(timeout=30, verify=False, auth=_node_auth(ssl)) as client:
            response = client.get(f"{base}/checkgrupos", params={"enlace": nombre_enlace})
            response.raise_for_status()
            return response.text
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout al conectar con {base}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con {base} — {e}")
