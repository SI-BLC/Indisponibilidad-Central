from datetime import datetime


def parse_dat_file(file_content: str, enlaces_map: dict, id_sotr: int):
    """
    Parsea el contenido de un archivo .dat y retorna filas listas para insertar en MySQL.

    Args:
        file_content: Contenido del archivo como string
        enlaces_map: Dict {nombre_enlace: id_enlace}
        id_sotr: ID del SOTR (0 = carga manual)

    Returns:
        tuple: (rows: list[dict], log: list[str])
    """
    rows = []
    log = []
    current_enlace = None
    current_id_enlace = None
    current_fecha = None
    current_elc = None
    current_periodo = None

    for line_num, line in enumerate(file_content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or '-=-=-' in line:
            continue

        if stripped.startswith('*'):
            # Línea de datos de grupo: * Gr=1 Id=R Typ=1 UI=0 Siz=14 Exp=2520 T=2268 ...
            if current_id_enlace is None or current_fecha is None:
                continue

            kv = {}
            for token in stripped.split():
                if '=' in token:
                    k, v = token.split('=', 1)
                    kv[k] = v

            id_gr = kv.get('Id', 'R')
            if id_gr != 'R':
                continue

            try:
                rows.append({
                    'fecha': current_fecha,
                    'elc': current_elc,
                    'id_enlace': current_id_enlace,
                    'periodo': current_periodo,
                    'gr_grupo': int(kv['Gr']),
                    'id_gr': id_gr,
                    'typ': kv.get('Typ'),
                    'ui': kv.get('UI'),
                    'siz': int(kv.get('Siz', 0)),
                    'exp': int(kv.get('Exp', 0)),
                    't': int(kv.get('T', 0)),
                    'g': int(kv.get('G', 0)),
                    'h': int(kv.get('H', 0)),
                    'c': int(kv.get('C', 0)),
                    'e': int(kv.get('E', 0)),
                    'm': int(kv.get('M', 0)),
                    'i': int(kv.get('I', 0)),
                    'freq': int(kv['Freq']) if 'Freq' in kv else None,
                    'st': int(kv['St']) if 'St' in kv else None,
                    'transmitido': 0,
                    'id_sotr': id_sotr,
                })
            except (KeyError, ValueError) as ex:
                log.append(f"Línea {line_num}: error parseando grupo — {ex}")

        else:
            # Posible línea de encabezado de período:
            # 10/06/2026 10:30:00   ELC=a    CGEN_CAMM    Data count. Period: 30 min.
            parts = stripped.split()
            if len(parts) < 4:
                continue
            if 'Data' not in line:
                continue  # línea de sistema (SYSTEM, etc.)

            try:
                fecha_str = parts[0] + ' ' + parts[1]
                current_fecha = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')
            except ValueError:
                log.append(f"Línea {line_num}: fecha inválida '{parts[0]} {parts[1]}'")
                current_fecha = None
                current_id_enlace = None
                continue

            current_elc = parts[2].split('=')[1] if '=' in parts[2] else None
            current_enlace = parts[3]
            current_id_enlace = enlaces_map.get(current_enlace)

            # Período: buscar "Period: 30 min." en la línea
            if 'Period:' in line:
                idx = line.index('Period:')
                current_periodo = line[idx + len('Period:'):].strip().rstrip('.')
            else:
                current_periodo = None

            if not current_id_enlace:
                log.append(f"Línea {line_num}: enlace desconocido '{current_enlace}' — omitido")
                current_id_enlace = None

    return rows, log
