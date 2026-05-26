from sqlalchemy import Column, Integer, String, DateTime, Float, Date
from database import Base


class Central(Base):
    __tablename__ = "centrales"
    id = Column(Integer, primary_key=True, index=True)
    nemo = Column(String(45), nullable=False)
    ip1 = Column(String(45), nullable=True)
    ip2 = Column(String(45), nullable=True)
    tipo = Column(Integer, nullable=True)  # 1=Directa, 2=Redundante, 3=Solo-backup


class Enlace(Base):
    __tablename__ = "enlaces"
    id = Column(Integer, primary_key=True, index=True)
    idcentral = Column(Integer, nullable=False, index=True)
    nombre = Column(String(45), nullable=False)
    idtipo = Column(Integer, nullable=True)
    rol = Column(String(20), nullable=True)  # 'directo' | 'concentrador' | NULL


class Grupo(Base):
    __tablename__ = "grupos"
    id = Column(Integer, primary_key=True, index=True)
    idenlace = Column(Integer, nullable=False, index=True)
    grupo = Column(Integer, nullable=False, index=True)
    tipo = Column(Integer, nullable=False)
    periodico = Column(Integer, nullable=False)
    periodo = Column(Integer, nullable=False)
    direccion = Column(Integer, nullable=False)
    calcular = Column(Integer, nullable=True, default=1)


class Mantenimiento(Base):
    __tablename__ = "mantenimientos"
    id = Column(Integer, primary_key=True, index=True)
    idenlace = Column(Integer, nullable=False)
    tipo = Column(Integer, nullable=False)  # 1=Enlace, 2=Ordinario, 3=Electrico
    inicio = Column(DateTime, nullable=False)
    fin = Column(DateTime, nullable=False)
    intervalos = Column(String(45), nullable=True)
    grupo = Column(Integer, nullable=False, default=0)
    cantobjetos = Column(Integer, nullable=False, default=0)


class Conexion(Base):
    __tablename__ = "con"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=True, index=True)
    id_enlace = Column(Integer, nullable=True, index=True)
    asoc_ab = Column(String(45), nullable=True)
    asoc_ac = Column(String(45), nullable=True)
    asoc_bb = Column(String(45), nullable=True)
    asoc_bc = Column(String(45), nullable=True)
    elc = Column(String(45), nullable=True)
    link = Column(String(45), nullable=True)
    integrity_scan = Column(String(45), nullable=True)
    id_sotr = Column(Integer, nullable=True)
    asoc_change = Column(String(45), nullable=True)


class Dat(Base):
    __tablename__ = "dat"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=True, index=True)
    id_enlace = Column(Integer, nullable=True, index=True)
    id_gr = Column(String(45), nullable=True)
    gr_grupo = Column(Integer, nullable=True)
    siz = Column(Integer, nullable=True)
    t = Column(Integer, nullable=True)
    g = Column(Integer, nullable=True)
    h = Column(Integer, nullable=True)
    c = Column(Integer, nullable=True)
    e = Column(Integer, nullable=True)
    m = Column(Integer, nullable=True)
    i = Column(Integer, nullable=True)
    exp = Column(Integer, nullable=True)
    freq = Column(Integer, nullable=True)
    st = Column(Integer, nullable=True)


class Configuracion(Base):
    __tablename__ = "configuracion"
    id = Column(Integer, primary_key=True, index=True)
    tol_cortes = Column(Integer, nullable=False)
    tol_datos = Column(Integer, nullable=False)


class ResultadoCentral(Base):
    __tablename__ = "resultados_central"
    id = Column(Integer, primary_key=True, index=True)
    id_central = Column(Integer, nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    ind_total_seg = Column(Float, nullable=True)   # segundos totales de indisponibilidad
    inconsistencia = Column(Integer, nullable=False, default=0)  # 0=ok, 1=requiere revisión
    generado_en = Column(DateTime, nullable=True)


class ResultadoReporte(Base):
    __tablename__ = "resultados_reporte"
    id = Column(Integer, primary_key=True, index=True)
    id_enlace = Column(Integer, nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    enlace_nombre = Column(String(45), nullable=True)
    # Cortes
    bruta_c = Column(Integer, nullable=True)
    bruta_b = Column(Integer, nullable=True)
    neta_c = Column(Float, nullable=True)
    neta_b = Column(Float, nullable=True)
    promedio_neto = Column(Float, nullable=True)
    mant_cortes_c = Column(Float, nullable=True)
    mant_cortes_b = Column(Float, nullable=True)
    promedio_mant_cortes = Column(Float, nullable=True)
    # Datos
    ind_norec_c = Column(Float, nullable=True)
    ind_noval_c = Column(Float, nullable=True)
    ind_norec_b = Column(Float, nullable=True)
    ind_noval_b = Column(Float, nullable=True)
    ind_datos_norm = Column(Float, nullable=True)
    ind_mant_c = Column(Float, nullable=True)
    ind_mant_b = Column(Float, nullable=True)
    ind_datos_mant = Column(Float, nullable=True)
    # Resumen
    ind_total_norm = Column(Float, nullable=True)
    ind_total_mant = Column(Float, nullable=True)
    generado_en = Column(DateTime, nullable=True)
