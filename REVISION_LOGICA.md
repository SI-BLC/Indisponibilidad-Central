# Revisión de Lógica de Cálculo — Indisponibilidad Central

## Estado: EN REVISIÓN

---

## 1. Dos pipelines distintos (problema estructural)

El frontend llama simultáneamente a dos endpoints:

```typescript
forkJoin({
    reporte: this.api.generarReporte(req),     // POST /reportes/
    txt:     this.api.generarReporteTxt(req),   // POST /reportes/txt
})
```

Estos endpoints usan **dos implementaciones completamente distintas**:

| Aspecto               | `calcular_reporte` (JSON)              | `generar_reporte_txt` (TXT)                     |
|-----------------------|----------------------------------------|-------------------------------------------------|
| Tabla cortes          | `con` (modelo `Conexion`, col `asoc_bc`) | `vista_asoc_con1` (eventos por asoc)           |
| Tabla datos           | No usa `dat`                           | `dat` (via `_procesar_datos_dat_pd`)            |
| Detección de cortes   | Transición 0→1 en `asoc_bc`            | Máquina de estados con EV_CAIDA/EV_ESTAB/MANT  |
| Tolerancia cortes     | No aplica                              | `tol_cortes` de configuracion                  |
| Semántica de estado   | `0 = caído`, `1 = conectado`           | `1 = EV_CAIDA`, `2 = EV_ESTAB`                 |
| Tipo 2 (Redundante)   | Intersecta todos los enlaces propios   | Según `idtipo` del enlace                       |

> **Inconsistencia #1**: Dos cálculos distintos pueden dar resultados diferentes para el mismo período.

---

## 2. Pipeline atomico: `_procesar_enlace_pd`

Este es el pipeline principal (TXT). Orden de ejecución:

### Paso 1 — Leer `dat` → `df_dat`
Función: `_procesar_datos_dat_pd(ini, fin, id_enlace, db)`

- Consulta `dat` WHERE `id_enlace = X AND fecha > ini+1min AND fecha <= fin+1min`
- Consulta `grupos` para ese enlace (una sola query, sin N+1)
- Filtra: solo filas con `calcular=1` e `id_gr='R'`
- Determina `asoc`: si `freq IS NULL` → asoc_b (AB o BB), sino → asoc_c (AC o BC)
  - El prefijo (A o B) depende de `idtipo` del enlace: `A` si `idtipo=2`, `B` si `idtipo=1`
- Calcula campos derivados: `ui_esperadas`, `ui_norecibidas`, `ui_invalidas`, etc.
- Retorna `df_dat`

### Paso 2 — Detectar cortes en `vista_asoc_con1` → `df_cortes`
Función: `_procesar_corte_asoc_pd(asoc, ini, fin, id_enlace, tol, df_dat, db)`

Llamada para cada asoc: `["ab", "ac", "bb", "bc"]`

- Consulta `vista_asoc_con1` con la columna correspondiente (`ab`, `ac`, `bb` o `bc`) filtrando por `id_enlace`
- Máquina de estados (SM):
  - `estado 0` (inicial): si EV_CAIDA → guardar t_inicio, pasar a 1; si EV_ESTAB → corte desde `ini`
  - `estado 1` (caído): si EV_ESTAB → registrar corte, pasar a 2
  - `estado 2` (conectado): si EV_CAIDA → pasar a 1
- Si no hay eventos en `vista_asoc_con1`:
  - Usa `df_dat` para determinar si había datos (`hay`) y cuál fue la última fecha (`fecha_max`)
  - Fallback: genera un corte artificial de duración mínima al final del período
- Agrega mantenimientos desde tabla `mantenimientos`
- Retorna lista de dicts con cortes (sin escribir en DB)

### Paso 3 — Marcar períodos excluidos en `df_dat`
Función: `_update_excluidos_pd(df_dat, df_cortes)`

- Para cada corte, marca `analizar=0` en las filas de `df_dat` que caen dentro de la ventana del corte

### Paso 4 — Normalizar indicadores por fila
Función: `_misc1_pd(df_dat)`

- Calcula `ui_norec_norm`, `ui_inv_norm`, `por_inv_esp`, `por_norec_esp` (vectorizado)

### Paso 5 — Sumas parciales por (fecha, enlace, agente, asoc)
Función: `_sumas_parciales_pd(df_dat)` → `df_sum`

- `groupby` + `agg` sobre filas con `analizar=1` y asoc en `[BC, BB, AC, AB]`
- Calcula indisponibilidades parciales: norec_norm, inv_norm, norec_mant, inv_mant, etc.

### Paso 6 — Ponderación por volumen de información
Función: `_misc2_pd(df_dat, df_sum, ac, ab)`

- Merge entre `df_dat` y `df_sum` para propagar sumas al nivel de fila
- Calcula `ind_norec_norm`, `ind_inv_norm`, `ind_norm`, `seg_ind_norm` por fila

### Paso 7 — Armar texto y valores finales
Función: `_armar_informe_pd(id_enlace, ini, fin, df_dat, df_sum, df_cortes, db)`

- Calcula VI (volumen de información) por asoc
- Si `vi_ct + vi_bt == 0` → retorna error "volumen nulo"
- Calcula IS (indisponibilidad en segundos) por cortes y por calidad de datos
- Genera texto TXT formato SOTR ENARSA
- Retorna `(texto, valores_dict)`

---

## 3. Lógica de selección de enlaces por tipo de central

### En `generar_reporte_txt`:

```python
directos = enlaces con idtipo=1 de la central
bcog    = enlaces con idtipo=2 de la central

if directos AND bcog:
    procesar directos + enlace backup (nombre = "{nemo}_CAMM" buscado en BCOG)
elif directos:
    procesar directos
elif bcog:
    procesar enlace backup (nombre = "{nemo}_CAMM" buscado en BCOG)
```

> **Pendiente de revision**: Esta lógica no considera el tipo de la central (tipo 1/2/3),
> solo si tiene enlaces directos (idtipo=1) o BCOG (idtipo=2).

### En `calcular_reporte` (JSON):

```python
if tipo == 1:
    todos los enlaces propios → union de cortes
elif tipo == 2:
    todos los enlaces propios → interseccion de cortes
elif tipo == 3:
    todos los enlaces propios → union de cortes
```

> **Inconsistencia #2**: Para tipo 2, usa TODOS los enlaces propios (incluyendo CGEN_BCOG si existe),
> pero NO incluye el enlace de retransmision BCOG (ARA2_CAMM), que pertenece a la central BCOG,
> no a ARA2. Resultado: la interseccion puede ser siempre vacia si CGEN_BCOG no tiene cortes.

---

## 4. Issues identificados

| # | Descripcion | Archivo | Estado |
|---|-------------|---------|--------|
| 1 | Dos pipelines distintos (JSON vs TXT) pueden dar resultados inconsistentes | `reporte_service.py` | ABIERTO |
| 2 | `calcular_reporte` tipo 2: no incluye enlace BCOG de retransmision, incluye todos los propios | `reporte_service.py` | ABIERTO |
| 3 | `_cargar_conexiones` usa `asoc_bc` como 0/1 pero `vista_asoc_con1` usa eventos 1/2 | `reporte_service.py` | ABIERTO |
| 4 | ARA2 (resultados page): `filterLinksByTipo` retorna vacío pese a datos en DB | `resultados.ts` | ABIERTO |

---

## 5. Correcciones aplicadas

| # | Descripcion | Archivo | Commit/Fecha |
|---|-------------|---------|--------------|
| 1 | Refactor pandas: eliminar tablas temporales MySQL del pipeline principal | `reporte_service.py` | sesion anterior |
| 2 | Fix `_procesar_corte_asoc_pd`: reemplazar queries a `dat_aux` (ya no existe) por operaciones sobre `df_dat` | `reporte_service.py` | sesion anterior |
| 3 | Fix `_procesar_enlace_pd`: detectar `idtipo` y procesar solo las 2 asocs relevantes (ab/ac si idtipo=2, bb/bc si idtipo=3) | `reporte_service.py` | sesion actual |
| 4 | Fix `_procesar_datos_dat_pd`: reemplazar hardcoded `c.id<>7` por `UPPER(c.nemo) != 'BCOG'` | `reporte_service.py` | sesion actual |
| 5 | Fix `generar_reporte_txt`: reescritura completa usando `central.tipo` (1/2/3) con idtipo correcto (2=directo, 3=concentrador) | `reporte_service.py` | sesion actual |
| 6 | Nuevo `_generar_txt_corte_efectivo`: intersección de ventanas de corte entre enlace directo y concentrador (Tipo 2) | `reporte_service.py` | sesion actual |
