# Análisis: Soporte ICCP en Sistema de Indisponibilidad

## Contexto

Las nuevas centrales utilizan protocolo ICCP (TASE.2), que coexistirá con las centrales ELCOM existentes. Se dispone de archivos .con y .dat de:
- Central CABO: `avails/central/28-08-2025.con` y `.dat`
- Concentrador ICCP: `avails/concentrador/13-06-2026.con` y `.dat`

---

## Archivos CON — Diferencias ELCOM vs ICCP

### ELCOM
```
10/06/2026 10:02:39   ELC=a  CGEN_BCOG    AB=e+ AC=i  BB=i  BC=i
```
- Identificador de servidor: `ELC=a`
- 4 asociaciones: `AB`, `AC`, `BB`, `BC`
- Estados: `e+`, `i+`, `e`, `i`, `u`

### ICCP (central y concentrador)
```
28/08/2025 11:56:43   SRV=CABO-SOTRA   CGEN_BCOG    C=i+ S=i+
13/06/2026 09:09:24   SRV=ICCP-COG     BCOG_QUIT    C=e+ S=e+
```
- Identificador de servidor: `SRV=X`
- 2 asociaciones: `C` y `S`
- Estados: `e+`, `i+`, `e`, `i`, `u`, **`s+`** (nuevo — aparece junto a DISABLED)

### Estado `s+` (definido)
`s` = stand-by, `s+` = cambió a stand-by. Aparece cuando el enlace se deshabilita (`DISABLED`):
```
28/08/2025 14:23:59   SRV=CABO-SOTRA   CGEN_CAMM    DISABLED
28/08/2025 14:23:59   SRV=CABO-SOTRA   CGEN_CAMM    C=s+ S=s+
```
`s+` **NO se usa** para el cálculo de cortes. Solo `i+` (interrupción/corte) y `e+` (establecimiento) son relevantes.

### Asociaciones C y S (definido)
- `C` = Cliente ICCP
- `S` = Servidor ICCP
- Asociaciones ICCP: `ACS`, `ASS`, `AS`

**Ambas se usan para detectar cortes**, de forma análoga a cómo ELCOM procesa AB/AC/BB/BC independientemente. Cuando `C` o `S` va a `i+` → inicio de corte en esa asociación. Cuando va a `e+` → fin de corte.

Equivalencia con ELCOM:
- ELCOM: 4 asociaciones (AB, AC, BB, BC) → 2 por link según prefijo (A=directo, B=concentrador)
- ICCP: 2 asociaciones (C, S) → ambas se procesan para cada link

---

## Archivos DAT — Diferencias ELCOM vs ICCP

### ELCOM
- Organizado por `grupo` (entero: 1, 2, 3, 5, 71, etc.)
- `freq` no nulo → dato periódico (AC/BC); `freq` nulo → no solicitado (AB/BB)
- Columnas: `Siz`, `Exp`, `T`, `G`, `H`, `C`, `E`, `M`, `I`, `freq`, `st`

### ICCP
```
28/08/2025 00:00:00   SRV=CABO-SOTRA   CGEN_BCOG    Data count. Period: 30 min.
* Dir=rx  Ts=1              Ds=              Siz=4   Exp=1440  T=1440  G=1440  H=0  C=0  E=0  M=0  I=0
* Dir=tx  Ts=TS_DOM_00000   Ds=DS_0003_03    Siz=6   Exp=2160  T=2160  G=2160  H=0  C=0  E=0  M=0  I=0
```

- Organizado por `Ts` (TransferSet) + `Dir` (dirección)
- `Dir=rx, Ts=numérico` → datos recibidos (desde central/CAMMESA hacia el nodo)
- `Dir=tx, Ts=TS_DOM_XXXX` → datos transmitidos (desde el nodo hacia CAMMESA)
- Las métricas `Siz, Exp, T, G, H, C, E, M, I` son **las mismas que ELCOM**
- `Ds` (DataSet) = vacío en rx, con valor en tx

### Enlace sin sub-líneas
Si un enlace aparece con la línea de cabecera pero sin TransferSets, significa que no hubo transmisión por ese enlace en ese período. Ejemplo: `CGEN_CAMM` sin sub-líneas + `CGEN_BCOG` con sub-líneas → la central transmitió vía concentrador ICCP.

### Dir=rx vs Dir=tx para el cálculo (definido)
- **`Dir=tx`** se usa para el cálculo de indisponibilidad de datos (lo que el nodo transmite a CAMMESA)
- `Dir=rx` queda fuera del cálculo (datos recibidos, no afectan la disponibilidad hacia CAMMESA)

---

## Arquitectura de enlaces ICCP

### Central (CABO)
- `CGEN_CAMM` → enlace directo a CAMMESA
- `CGEN_BCOG` → enlace al concentrador ICCP (equivalente al backup BCOG en ELCOM)

### Concentrador ICCP
- `BCOG_{CENTRAL}` → enlace concentrador → central (rx desde la central)
- `{CENTRAL}_CAMM` → enlace concentrador → CAMMESA (tx hacia CAMMESA)

Mismo patrón de nomenclatura que el BCOG ELCOM.

---

## Impacto en el sistema actual

### 4. Campo `protocolo` en tabla `centrales`
Agregar `protocolo ENUM('elcom','iccp') DEFAULT 'elcom'`. Las centrales existentes quedan automáticamente como `elcom`. Sin impacto en datos existentes.

### 5. Tablas `con_iccp` y `dat_iccp` (definido — ya existen en DB)

**`con_iccp`**:
```
id INT PK, fecha DATETIME, id_enlace INT, srv VARCHAR(32),
event_type VARCHAR(16), c_state VARCHAR(4), s_state VARCHAR(4), id_sotr INT
```
- `c_state` / `s_state` → equivalente a `asoc_ab/ac/bb/bc` de ELCOM
- `event_type` → ENABLED/DISABLED/estado (no existe en ELCOM)

**`dat_iccp`**:
```
id INT PK, fecha DATETIME, id_enlace INT, srv VARCHAR(32),
periodo VARCHAR(16), direction ENUM('rx','tx'), ts VARCHAR(32), ds VARCHAR(32),
siz INT, exp INT, t INT, g INT, h INT, c INT, e INT, m INT, i INT, id_sotr INT
```
- `direction` + `ts` + `ds` → reemplazan `gr_grupo`/`freq`/`st` de ELCOM
- Solo `direction='tx'` se usa para el cálculo

### 6. Campo `protocolo` en tabla `centrales` (definido)
Agregar `protocolo ENUM('elcom','iccp') DEFAULT 'elcom'`. Las centrales existentes quedan como `elcom` automáticamente.

### 7. Tabla de configuración TransferSets (definido)
Se crea tabla `transfersets` (equivalente a `grupos` de ELCOM):
```sql
CREATE TABLE transfersets (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    id_enlace  INT NOT NULL,
    ts_nombre  VARCHAR(50) NOT NULL,   -- ej: TS_DOM_00000, TS_DOM_00001
    tipo       INT DEFAULT 0,          -- mismo sistema de tipos que ELCOM (1, 3, 5...)
    calcular   INT DEFAULT 1,
    UNIQUE KEY uq_enlace_ts (id_enlace, ts_nombre)
);
```

Solo se configuran los TransferSets de `Dir=tx` (salida a CAMMESA). Son dinámicos, típicamente 3 por enlace:
- `TS_DOM_00000` → generalmente tipo=3 o tipo=5
- `TS_DOM_00001` → generalmente tipo=3 o tipo=5
- `TS_DOM_00002` → generalmente tipo=1

El tipo varía por enlace/central, por lo que debe ser configurable por cada `{CENTRAL}_CAMM`.

### 8. Lógica de cálculo (`reporte_service.py`)
Toda la lógica actual asume ELCOM (columnas `asoc_ab/ac/bb/bc`, grupos enteros, `freq`/`st`).
Para ICCP se necesitará una rama de procesamiento separada o parametrizar las funciones existentes.
**Pendiente**: definir rol de `C` y `S` en detección de cortes antes de diseñar esto.

---

## Estado de pendientes

1. ~~`s+`~~ → stand-by, NO se usa para cálculo. Solo `i+` y `e+`.
2. ~~`C` o `S`~~ → ambas se usan, análogo a AB/AC/BB/BC en ELCOM.
3. ~~`Dir=tx` o `Dir=rx`~~ → `Dir=tx` para cálculo.
4. ~~Tipo/peso por TransferSet~~ → configurable por enlace, tabla `transfersets`.
5. ~~Tabla separada o extender~~ → `con_iccp` y `dat_iccp` separadas.

## Principios de implementación

- **Código ICCP completamente separado de ELCOM**. No modificar lógica ELCOM existente.
- Servicios ICCP en archivos separados (ej: `reporte_service_iccp.py`)
- Las centrales ICCP soportan los mismos 3 tipos que ELCOM:
  - Tipo 1: enlace directo a CAMMESA
  - Tipo 2: redundante (directo + backup vía concentrador ICCP)
  - Tipo 3: solo backup (solo vía concentrador ICCP)
- El concentrador ICCP cumple el mismo rol que BCOG en ELCOM
- `s+` se ignora; solo `i+` y `e+` son relevantes para cortes
- Tolerancia y lógica de cortes: igual que ELCOM

## Pendientes restantes

1. **UI**: pantalla de configuración de TransferSets (similar a Grupos de ELCOM)
2. **Lógica de cálculo ICCP**: implementar servicio separado que lea de `con_iccp`/`dat_iccp`/`transfersets`
3. **Detalle ICCP**: adaptar `_detalle_central` para centrales ICCP (o crear versión ICCP)
4. **Reportes TXT ICCP**: generar informe similar al ELCOM pero con TransferSets
