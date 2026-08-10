from datetime import datetime


def parse_dat_iccp_file(file_content: str, enlaces_map: dict, id_sotr: int):
    rows = []
    log = []
    current_id_enlace = None
    current_fecha = None
    current_srv = None
    current_periodo = None

    for line_num, line in enumerate(file_content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or '-=-=-' in line:
            continue

        if stripped.startswith('*'):
            if current_id_enlace is None or current_fecha is None:
                continue

            kv = {}
            for token in stripped.split():
                if '=' in token:
                    k, v = token.split('=', 1)
                    kv[k] = v

            try:
                rows.append({
                    'fecha': current_fecha,
                    'id_enlace': current_id_enlace,
                    'srv': current_srv,
                    'periodo': current_periodo,
                    'direction': kv.get('Dir', ''),
                    'ts': kv.get('Ts', ''),
                    'ds': kv.get('Ds', ''),
                    'siz': int(kv.get('Siz', 0)),
                    'exp': int(kv.get('Exp', 0)),
                    't': int(kv.get('T', 0)),
                    'g': int(kv.get('G', 0)),
                    'h': int(kv.get('H', 0)),
                    'c': int(kv.get('C', 0)),
                    'e': int(kv.get('E', 0)),
                    'm': int(kv.get('M', 0)),
                    'i': int(kv.get('I', 0)),
                    'id_sotr': id_sotr,
                })
            except (KeyError, ValueError) as ex:
                log.append(f"Línea {line_num}: error parseando datos — {ex}")
        else:
            parts = stripped.split()
            if len(parts) < 4:
                continue
            if 'Data' not in line:
                continue

            try:
                fecha_str = parts[0] + ' ' + parts[1]
                current_fecha = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')
            except ValueError:
                log.append(f"Línea {line_num}: fecha inválida '{parts[0]} {parts[1]}'")
                current_fecha = None
                current_id_enlace = None
                continue

            srv_token = parts[2]
            current_srv = srv_token.split('=', 1)[1] if '=' in srv_token else None
            current_enlace = parts[3]
            current_id_enlace = enlaces_map.get(current_enlace)

            if 'Period:' in line:
                idx = line.index('Period:')
                current_periodo = line[idx + len('Period:'):].strip().rstrip('.')
            else:
                current_periodo = None

            if not current_id_enlace:
                log.append(f"Línea {line_num}: enlace desconocido '{current_enlace}' — omitido")
                current_id_enlace = None

    return rows, log
