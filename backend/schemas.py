from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional


# --- Centrales ---
class CentralBase(BaseModel):
    nemo: str
    tipo: Optional[int] = None
    ip1: Optional[str] = None
    ip2: Optional[str] = None
    protocolo: str = "elcom"


class CentralCreate(CentralBase):
    pass


class CentralUpdate(BaseModel):
    nemo: Optional[str] = None
    tipo: Optional[int] = None
    ip1: Optional[str] = None
    ip2: Optional[str] = None
    protocolo: Optional[str] = None


class CentralOut(CentralBase):
    id: int
    model_config = {"from_attributes": True}


# --- Enlaces ---
class EnlaceBase(BaseModel):
    nombre: str
    idcentral: int
    idtipo: Optional[int] = None
    rol: Optional[str] = None


class EnlaceCreate(EnlaceBase):
    pass


class EnlaceUpdate(BaseModel):
    nombre: Optional[str] = None
    idtipo: Optional[int] = None
    rol: Optional[str] = None


class EnlaceOut(EnlaceBase):
    id: int
    model_config = {"from_attributes": True}


# --- TransferSets (ICCP) ---
class TransferSetBase(BaseModel):
    id_enlace: int
    ts_nombre: str
    tipo: int = 0
    calcular: int = 1


class TransferSetCreate(TransferSetBase):
    pass


class TransferSetUpdate(BaseModel):
    ts_nombre: Optional[str] = None
    tipo: Optional[int] = None
    calcular: Optional[int] = None


class TransferSetOut(TransferSetBase):
    id: int
    model_config = {"from_attributes": True}


# --- Grupos ---
class GrupoBase(BaseModel):
    idenlace: int
    grupo: int
    tipo: int = 0
    periodico: int = 0
    periodo: int = 0
    direccion: int = 0
    calcular: Optional[int] = 1


class GrupoCreate(GrupoBase):
    pass


class GrupoUpdate(BaseModel):
    grupo: Optional[int] = None
    tipo: Optional[int] = None
    periodico: Optional[int] = None
    periodo: Optional[int] = None
    direccion: Optional[int] = None
    calcular: Optional[int] = None


class GrupoOut(GrupoBase):
    id: int
    model_config = {"from_attributes": True}


# --- Mantenimientos ---
class MantenimientoBase(BaseModel):
    idenlace: int
    tipo: int
    inicio: datetime
    fin: datetime
    intervalos: Optional[str] = None
    grupo: int = 0
    cantobjetos: int = 0


class MantenimientoCreate(MantenimientoBase):
    pass


class MantenimientoOut(MantenimientoBase):
    id: int
    model_config = {"from_attributes": True}


# --- Reporte Request ---
class ReporteRequest(BaseModel):
    idCentral: int
    fechaInicio: datetime
    fechaFin: datetime


# --- Reporte Response ---
class CorteItem(BaseModel):
    id_enlace: int
    nombre_enlace: str
    inicio: datetime
    fin: datetime
    duracion_minutos: float
    es_mantenimiento: bool
    tipo: Optional[str] = None


class ReporteOut(BaseModel):
    idCentral: int
    nemo: str
    tipo_central: Optional[int]
    fechaInicio: datetime
    fechaFin: datetime
    cortes: list[CorteItem]
    disponibilidad_pct: float
    total_minutos_corte: float
    total_minutos_periodo: float


# --- Resultados Central (resumen por central/día) ---
class ResultadoCentralOut(BaseModel):
    id: int
    id_central: int
    fecha: date
    ind_total_seg: Optional[float] = None
    inconsistencia: int = 0
    generado_en: Optional[datetime] = None
    # Enriquecidos por el endpoint
    central_nemo: Optional[str] = None
    central_tipo: Optional[int] = None
    model_config = {"from_attributes": True}


# --- Resultados Reporte ---
class ResultadoReporteOut(BaseModel):
    id: int
    id_enlace: int
    fecha: date
    enlace_nombre: Optional[str]
    bruta_c: Optional[int]
    bruta_b: Optional[int]
    neta_c: Optional[float]
    neta_b: Optional[float]
    promedio_neto: Optional[float]
    mant_cortes_c: Optional[float]
    mant_cortes_b: Optional[float]
    promedio_mant_cortes: Optional[float]
    ind_norec_c: Optional[float]
    ind_noval_c: Optional[float]
    ind_norec_b: Optional[float]
    ind_noval_b: Optional[float]
    ind_datos_norm: Optional[float]
    ind_mant_c: Optional[float]
    ind_mant_b: Optional[float]
    ind_datos_mant: Optional[float]
    ind_total_norm: Optional[float]
    ind_total_mant: Optional[float]
    generado_en: Optional[datetime]
    central_nemo: Optional[str] = None
    central_tipo: Optional[int] = None
    corte_efectivo: Optional[float] = None
    id_central_enlace: Optional[int] = None
    model_config = {"from_attributes": True}


# --- Datos CON ---
class ConOut(BaseModel):
    id: int
    fecha: Optional[datetime] = None
    id_enlace: Optional[int] = None
    asoc_ab: Optional[str] = None
    asoc_ac: Optional[str] = None
    asoc_bb: Optional[str] = None
    asoc_bc: Optional[str] = None
    elc: Optional[str] = None
    link: Optional[str] = None
    integrity_scan: Optional[str] = None
    id_sotr: Optional[int] = None
    asoc_change: Optional[str] = None
    model_config = {"from_attributes": True}


# --- Datos DAT ---
class DatOut(BaseModel):
    id: int
    fecha: Optional[datetime] = None
    id_enlace: Optional[int] = None
    id_gr: Optional[str] = None
    gr_grupo: Optional[int] = None
    siz: Optional[int] = None
    t: Optional[int] = None
    g: Optional[int] = None
    h: Optional[int] = None
    c: Optional[int] = None
    e: Optional[int] = None
    m: Optional[int] = None
    i: Optional[int] = None
    exp: Optional[int] = None
    freq: Optional[int] = None
    st: Optional[int] = None
    model_config = {"from_attributes": True}


# --- Cortes Reporte ---
class CorteReporteOut(BaseModel):
    id: int
    id_enlace: int
    fecha: date
    asoc: Optional[str] = None
    inicio: datetime
    fin: datetime
    ind_bruta: int
    ind_neta: int
    tipo: int
    model_config = {"from_attributes": True}


# --- Dashboard ---
class DashboardCentral(BaseModel):
    id: int
    nemo: str
    tipo: Optional[int]
    cant_enlaces: int
    tiene_grupos: bool
