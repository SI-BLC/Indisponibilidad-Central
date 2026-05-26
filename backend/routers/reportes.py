from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from database import get_db
from schemas import ReporteRequest, ReporteOut
from services.reporte_service import calcular_reporte, generar_reporte_txt

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.post("/", response_model=ReporteOut)
def generar_reporte(req: ReporteRequest, db: Session = Depends(get_db)):
    try:
        return calcular_reporte(db, req.idCentral, req.fechaInicio, req.fechaFin)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/txt", response_class=PlainTextResponse)
def generar_reporte_txt_endpoint(req: ReporteRequest, db: Session = Depends(get_db)):
    try:
        return generar_reporte_txt(db, req.idCentral, req.fechaInicio, req.fechaFin)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
