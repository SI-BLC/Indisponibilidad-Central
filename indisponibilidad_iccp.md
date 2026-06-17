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

### Estado `s+` (pendiente de definir)
Aparece cuando el enlace se deshabilita (`DISABLED`):
```
28/08/2025 14:23:59   SRV=CABO-SOTRA   CGEN_CAMM    DISABLED
28/08/2025 14:23:59   SRV=CABO-SOTRA   CGEN_CAMM    C=s+ S=s+
```
**Pendiente**: confirmar qué significa `s+` y si cuenta como corte o como mantenimiento/suspensión.

### Asociaciones C y S — pendiente de definir
El usuario mencionó que en ICCP existen `ACS`, `ASS` y `AS`. Aún no está confirmado cuál de `C` o `S` equivale a la asociación usada para detección de cortes (en ELCOM: `asoc_ac` o `asoc_bc`).

**Pendiente**: determinar:
- ¿`C` es la asociación de control/corte? ¿`S` es la de supervisión/estado?
- ¿Cuál se usa para detectar cortes en el cálculo de indisponibilidad?
- ¿Se usan ambas o solo una?

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

### Dir=rx vs Dir=tx para el cálculo
**Pendiente confirmar**:
- ¿`Dir=tx` (TS_DOM_XXXX) es el equivalente a los datos periódicos AC/BC?
- ¿`Dir=rx` (Ts numérico) es el equivalente a los no-solicitados AB/BB?
- ¿Se usa solo `Dir=tx`, o ambas direcciones entran al cálculo?

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

### 5. Tabla `con` — columnas de asociaciones
Actualmente: `asoc_ab`, `asoc_ac`, `asoc_bb`, `asoc_bc`
Para ICCP: solo `C` y `S`
**Opciones**:
- Agregar columnas `asoc_c` y `asoc_s` (las ELCOM quedarían NULL para ICCP y viceversa)
- Mapear `C` → `asoc_ac` y `S` → `asoc_ab` (reutilizar columnas — más simple pero menos explícito)

### 6. Tabla `dat` — columna `gr_grupo`
Actualmente: `gr_grupo INT`
Para ICCP: Ts puede ser entero (1, 2, 3) o string (TS_DOM_00000)
**Opciones a evaluar**:
- Tabla separada `dat_iccp` (más limpio, sin impacto en ELCOM)
- Columna adicional `ts_nombre VARCHAR` en `dat` actual
- Cambiar `gr_grupo` a VARCHAR (rompe lógica ELCOM existente — descartado)

### 7. Tabla `grupos` → TransferSets
Actualmente: `grupo INT` + `tipo` + `calcular` por enlace
Para ICCP: habría que configurar tipo/calcular por TransferSet (string o entero)
**Pendiente**: definir si se extiende la tabla grupos o se crea una nueva `transfersets`.

### 8. Lógica de cálculo (`reporte_service.py`)
Toda la lógica actual asume ELCOM (columnas `asoc_ab/ac/bb/bc`, grupos enteros, `freq`/`st`).
Para ICCP se necesitará una rama de procesamiento separada o parametrizar las funciones existentes.
**Pendiente**: definir rol de `C` y `S` en detección de cortes antes de diseñar esto.

---

## Pendientes a confirmar con el equipo

1. ¿Qué significa `s+` en ICCP? ¿Equivale a mantenimiento, o es un estado de corte?
2. ¿`C` o `S` (o ambas) se usan para detectar cortes en indisponibilidad?
3. ¿`Dir=tx` son los datos periódicos y `Dir=rx` los no-solicitados, o al revés?
4. ¿Cómo se asigna el tipo/peso a cada TransferSet? ¿Es configurable por enlace o tiene reglas fijas?
5. Definir si se usa tabla `dat_iccp` separada o se extiende la tabla `dat` actual.
