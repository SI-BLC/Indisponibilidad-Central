from datetime import datetime


def parse_con_file(file_content: str, enlaces_map: dict, id_sotr: int):
    """
    Parsea el contenido de un archivo .con y retorna filas listas para insertar en MySQL.

    Args:
        file_content: Contenido del archivo como string
        enlaces_map: Dict {nombre_enlace: id_enlace}
        id_sotr: ID del SOTR (0 = carga manual)

    Returns:
        tuple: (rows: list[dict], log: list[str])
    """
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
            elc = parts[2].split('=')[1]
            enlace_nombre = parts[3]
            fecha = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')

            id_enlace = enlaces_map.get(enlace_nombre)
            if not id_enlace:
                log.append(f"Línea {line_num}: enlace desconocido '{enlace_nombre}' — omitido")
                continue

            row = {
                'fecha': fecha,
                'id_enlace': id_enlace,
                'asoc_ab': None,
                'asoc_ac': None,
                'asoc_bb': None,
                'asoc_bc': None,
                'asoc_change': None,
                'link': None,
                'integrity_scan': None,
                'elc': elc,
                'id_sotr': id_sotr,
            }

            if 'Integrity' in line:
                row['integrity_scan'] = 'AUTOMATIC'
            elif 'Link' in line:
                row['link'] = ' '.join(parts[5:]) if len(parts) > 5 else None
            else:
                row['asoc_ab'] = next((p.split('=')[1] for p in parts if p.startswith('AB=')), None)
                row['asoc_ac'] = next((p.split('=')[1] for p in parts if p.startswith('AC=')), None)
                row['asoc_bb'] = next((p.split('=')[1] for p in parts if p.startswith('BB=')), None)
                row['asoc_bc'] = next((p.split('=')[1] for p in parts if p.startswith('BC=')), None)

            rows.append(row)

        except (ValueError, IndexError) as e:
            log.append(f"Línea {line_num}: error de parseo — {e}")

    return rows, log
