from datetime import datetime


def parse_con_iccp_file(file_content: str, enlaces_map: dict, id_sotr: int):
    rows = []
    log = []

    for line_num, line in enumerate(file_content.splitlines(), 1):
        try:
            parts = line.split()
            if not parts or len(parts) < 4:
                continue
            if '-=-=-' in line:
                continue

            fecha_str = parts[0] + ' ' + parts[1]
            fecha = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')

            srv_token = parts[2]
            if not srv_token.startswith('SRV='):
                continue
            srv = srv_token.split('=', 1)[1]

            enlace_nombre = parts[3]
            id_enlace = enlaces_map.get(enlace_nombre)
            if not id_enlace:
                log.append(f"Línea {line_num}: enlace desconocido '{enlace_nombre}' — omitido")
                continue

            row = {
                'fecha': fecha,
                'id_enlace': id_enlace,
                'srv': srv,
                'event_type': 'state',
                'c_state': '',
                's_state': '',
                'id_sotr': id_sotr,
            }

            remaining = parts[4:]
            if remaining and remaining[0] == 'ENABLED':
                row['event_type'] = 'enable'
            elif remaining and remaining[0] == 'DISABLED':
                row['event_type'] = 'disable'
            else:
                for token in remaining:
                    if token.startswith('C='):
                        row['c_state'] = token.split('=', 1)[1]
                    elif token.startswith('S='):
                        row['s_state'] = token.split('=', 1)[1]

            rows.append(row)

        except (ValueError, IndexError) as e:
            log.append(f"Línea {line_num}: error de parseo — {e}")

    return rows, log
