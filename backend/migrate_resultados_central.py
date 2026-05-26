"""
Migración: crea tabla resultados_central.
Ejecutar una sola vez: python migrate_resultados_central.py
"""
from database import engine
from sqlalchemy import text

SQL = """
CREATE TABLE IF NOT EXISTS resultados_central (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    id_central    INT NOT NULL,
    fecha         DATE NOT NULL,
    ind_total_seg FLOAT,
    inconsistencia TINYINT(1) NOT NULL DEFAULT 0,
    generado_en   DATETIME,
    UNIQUE KEY uq_central_fecha (id_central, fecha),
    INDEX idx_fecha (fecha),
    INDEX idx_central (id_central)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

with engine.connect() as conn:
    conn.execute(text(SQL))
    conn.commit()
    print("Tabla resultados_central creada (o ya existía).")
