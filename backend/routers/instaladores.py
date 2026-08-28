import re
import os
import json
import shutil
import sqlite3
import base64
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, field_validator, model_validator
from database import get_db
from config import settings

router = APIRouter(prefix="/instaladores", tags=["instaladores"])

IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
HOSTNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

SERVICE_DIR = Path(__file__).resolve().parent.parent.parent / "service"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "instaladores_output"
OUTPUT_DIR.mkdir(exist_ok=True)


class InstaladorRequest(BaseModel):
    planta_base: str
    hostname_sotra: str
    ip_vpn_sotra: str = ""
    ip_mpls_sotra: str = ""
    hostname_sotrb: str = ""
    ip_vpn_sotrb: str = ""
    ip_mpls_sotrb: str = ""
    central_nombre: str
    protocolo: str = "ELCOM"

    @field_validator("planta_base")
    @classmethod
    def validar_planta(cls, v):
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9]+$", v):
            raise ValueError("Solo letras minúsculas y números")
        return v

    @field_validator("hostname_sotra", "hostname_sotrb")
    @classmethod
    def validar_hostname(cls, v):
        if not v:
            return ""
        v = v.strip().lower()
        if not HOSTNAME_RE.match(v):
            raise ValueError("Hostname inválido: solo letras, números, puntos, guiones")
        return v

    @field_validator("ip_vpn_sotra", "ip_vpn_sotrb", "ip_mpls_sotra", "ip_mpls_sotrb")
    @classmethod
    def validar_ip(cls, v):
        if not v:
            return ""
        if not IP_RE.match(v):
            raise ValueError(f"IP inválida: {v}")
        return v

    @field_validator("protocolo")
    @classmethod
    def validar_protocolo(cls, v):
        v = v.upper()
        if v not in ("ELCOM", "ICCP"):
            raise ValueError("Protocolo debe ser ELCOM o ICCP")
        return v

    @model_validator(mode="after")
    def validar_sotrs(self):
        if not self.hostname_sotra:
            raise ValueError("Hostname SOTR A es requerido")
        if not (self.ip_vpn_sotra or self.ip_mpls_sotra):
            raise ValueError("SOTR A requiere al menos una IP (VPN o MPLS)")
        if self.tiene_sotrb and not (self.ip_vpn_sotrb or self.ip_mpls_sotrb):
            raise ValueError("SOTR B requiere al menos una IP si se especifica hostname")
        return self

    @property
    def tiene_sotrb(self) -> bool:
        return bool(self.hostname_sotrb)


def _build_inf(hostname: str, ip_vpn: str, ip_mpls: str) -> str:
    san_lines = [f'_continue_="dns={hostname}&"']
    if ip_vpn:
        san_lines.insert(0, f'_continue_="dns={hostname}.vpn&"')
    if ip_mpls:
        san_lines.append(f'_continue_="dns={hostname}.mpls&"')
    if ip_vpn:
        san_lines.append(f'_continue_="ipaddress={ip_vpn}"')
    if ip_mpls:
        if ip_vpn:
            san_lines[-1] = san_lines[-1].rstrip('"') + '&"'
        san_lines.append(f'_continue_="ipaddress={ip_mpls}"')

    san_block = "\n".join(san_lines)
    cn = f"{hostname}.vpn" if ip_vpn else (f"{hostname}.mpls" if ip_mpls else hostname)

    return f"""[Version]
Signature="$Windows NT$"

[NewRequest]
Subject="CN={cn},O=BLC"
KeyLength=2048
KeySpec=1
KeyUsage=0xA0
MachineKeySet=TRUE
Exportable=TRUE
RequestType=PKCS10
ProviderName="Microsoft RSA SChannel Cryptographic Provider"

[EnhancedKeyUsageExtension]
OID=1.3.6.1.5.5.7.3.1
OID=1.3.6.1.5.5.7.3.2

[Extensions]
2.5.29.17="{{text}}"
{san_block}"""


def _build_conf_db(hostname: str, sotr_label: str, planta: str, protocolo: str) -> str:
    template_path = SERVICE_DIR / "conf.db"
    out_path = OUTPUT_DIR / f"conf_{hostname}.db"
    shutil.copy2(template_path, out_path)

    conn = sqlite3.connect(str(out_path))
    c = conn.cursor()
    c.execute("UPDATE general SET host=?, central=?, protocolo=? WHERE id=1",
              (sotr_label.upper(), planta.upper(), protocolo.lower()))
    c.execute("UPDATE mysql SET user=?, pass='' WHERE id=1", (hostname,))
    conn.commit()
    conn.close()
    return str(out_path)


async def _emitir_cert(inf: str, pfx_password: str = "export") -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.CERT_HELPER_URL}/emitir-cert",
            headers={"Authorization": f"Bearer {settings.CERT_HELPER_TOKEN}"},
            json={"inf": inf, "pfx_password": pfx_password},
        )
    if resp.status_code != 200:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(502, detail=f"Cert-Helper error: {detail}")
    return resp.json()


async def _compilar_instalador(hostname: str, pfx_b64: str, pfx_password: str,
                                conf_db_path: str) -> dict:
    conf_db_b64 = base64.b64encode(open(conf_db_path, "rb").read()).decode()

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{settings.CERT_HELPER_URL}/compilar-instalador",
            headers={"Authorization": f"Bearer {settings.CERT_HELPER_TOKEN}"},
            json={
                "hostname": hostname,
                "pfx_base64": pfx_b64,
                "pfx_password": pfx_password,
                "conf_db_base64": conf_db_b64,
                "output_name": f"BLC_NODE_{hostname.upper()}",
            },
        )
    if resp.status_code != 200:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(502, detail=f"Compilación error: {detail}")
    return resp.json()


def _crear_usuario_mysql(hostname: str, ip_vpn: str):
    cn = f"{hostname}.vpn" if ip_vpn else (f"{hostname}.mpls" if ip_mpls else hostname)
    subject = f"/O=BLC/CN={cn}"
    admin_url = (
        f"mysql+pymysql://{settings.MYSQL_ADMIN_USER}:{settings.MYSQL_ADMIN_PASSWORD}"
        f"@{settings.MYSQL_ADMIN_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
    from sqlalchemy import create_engine
    engine = create_engine(admin_url)
    with engine.connect() as conn:
        existing = conn.execute(text("SELECT User FROM mysql.user WHERE User = :u"), {"u": hostname}).fetchone()
        if existing:
            engine.dispose()
            return {"status": "exists", "user": hostname}

        conn.execute(text(f"CREATE USER '{hostname}'@'%' IDENTIFIED BY '' REQUIRE SUBJECT '{subject}'"))
        for tbl in ("con", "dat", "con_iccp", "dat_iccp"):
            conn.execute(text(f"GRANT INSERT ON {settings.DB_NAME}.{tbl} TO '{hostname}'@'%'"))
        for tbl in ("enlaces", "centrales"):
            conn.execute(text(f"GRANT SELECT ON {settings.DB_NAME}.{tbl} TO '{hostname}'@'%'"))
        conn.execute(text("FLUSH PRIVILEGES"))
        conn.commit()
    engine.dispose()
    return {"status": "created", "user": hostname}


def _log_instalacion(db: Session, req: InstaladorRequest, usuario: str, resultados: dict):
    db.execute(text("""
        INSERT INTO instalaciones_log
        (planta_base, central_nombre, protocolo, usuario, sotra_cn, sotrb_cn, created_at)
        VALUES (:planta, :central, :proto, :user, :cna, :cnb, :now)
    """), {
        "planta": req.planta_base,
        "central": req.central_nombre,
        "proto": req.protocolo,
        "user": usuario,
        "cna": resultados.get("sotra", {}).get("cn", ""),
        "cnb": resultados.get("sotrb", {}).get("cn", ""),
        "now": datetime.now(),
    })
    db.commit()


def _save_exe(planta: str, sotr: str, exe_b64: str):
    exe_bytes = base64.b64decode(exe_b64)
    out_path = OUTPUT_DIR / f"BLC_NODE_{planta.upper()}_{sotr.upper()}.exe"
    out_path.write_bytes(exe_bytes)
    return str(out_path)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/check/{planta_base}")
def check_planta(planta_base: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id FROM instalaciones_log WHERE planta_base = :p LIMIT 1"),
        {"p": planta_base.strip().lower()}
    ).fetchone()
    return {"exists": row is not None}


@router.post("/generar")
async def generar_instaladores(req: InstaladorRequest, request: Request, db: Session = Depends(get_db)):
    user_data = getattr(request.state, "user", {})
    usuario = user_data.get("sub", "unknown") if isinstance(user_data, dict) else str(user_data)

    db.execute(text("DELETE FROM instalaciones_log WHERE planta_base = :p"), {"p": req.planta_base})
    db.commit()

    sotrs = [("sotra", req.hostname_sotra, req.ip_vpn_sotra, req.ip_mpls_sotra)]
    if req.tiene_sotrb:
        sotrs.append(("sotrb", req.hostname_sotrb, req.ip_vpn_sotrb, req.ip_mpls_sotrb))

    total_steps = len(sotrs) * 3 + 1

    async def event_stream():
        step = 0
        resultados = {}
        mysql_results = {}
        instaladores = {}

        try:
            for sotr, hostname, ip_vpn, ip_mpls in sotrs:
                label = sotr.upper().replace("SOTR", "SOTR ")

                step += 1
                yield _sse_event("progress", {
                    "step": step, "total": total_steps,
                    "message": f"Emitiendo certificado {label} ({hostname})...",
                })
                inf = _build_inf(hostname, ip_vpn, ip_mpls)
                cert = await _emitir_cert(inf)
                resultados[sotr] = {
                    "cn": cert["cn"],
                    "thumbprint": cert["thumbprint"],
                    "valid": f"{cert['not_before']} → {cert['not_after']}",
                    "pfx_password": cert["pfx_password"],
                }

                step += 1
                yield _sse_event("progress", {
                    "step": step, "total": total_steps,
                    "message": f"Creando usuario MySQL {hostname}...",
                })
                try:
                    mysql_results[sotr] = _crear_usuario_mysql(hostname, ip_vpn)
                except Exception as e:
                    mysql_results[sotr] = {"status": "error", "error": str(e)}

                step += 1
                yield _sse_event("progress", {
                    "step": step, "total": total_steps,
                    "message": f"Compilando instalador {label} ({hostname})...",
                })
                conf_db = _build_conf_db(hostname, sotr, req.planta_base, req.protocolo)
                compiled = await _compilar_instalador(
                    hostname, cert["pfx_base64"], cert["pfx_password"], conf_db,
                )
                _save_exe(req.planta_base, sotr, compiled["exe_base64"])
                instaladores[sotr] = {
                    "filename": compiled["output_name"],
                    "size_bytes": compiled["size_bytes"],
                }
                os.remove(conf_db)

            step += 1
            yield _sse_event("progress", {
                "step": step, "total": total_steps,
                "message": "Registrando en historial...",
            })
            _log_instalacion(db, req, usuario, resultados)

            yield _sse_event("done", {
                "success": True,
                "planta": req.planta_base,
                "certificados": resultados,
                "mysql_users": mysql_results,
                "instaladores": instaladores,
            })

        except HTTPException as e:
            yield _sse_event("error", {"message": str(e.detail)})
        except Exception as e:
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/eliminar/{planta_base}")
def eliminar_planta(planta_base: str, db: Session = Depends(get_db)):
    planta_base = planta_base.strip().lower()
    row = db.execute(
        text("SELECT id FROM instalaciones_log WHERE planta_base = :p"),
        {"p": planta_base}
    ).fetchone()
    if not row:
        raise HTTPException(404, detail="Planta no encontrada")

    db.execute(text("DELETE FROM instalaciones_log WHERE planta_base = :p"), {"p": planta_base})
    db.commit()

    for sotr in ("sotra", "sotrb"):
        exe_path = OUTPUT_DIR / f"BLC_NODE_{planta_base.upper()}_{sotr.upper()}.exe"
        if exe_path.exists():
            exe_path.unlink()

    return {"deleted": planta_base}


@router.get("/descargar/{planta_base}/{sotr}")
def descargar_exe(planta_base: str, sotr: str):
    if sotr not in ("sotra", "sotrb"):
        raise HTTPException(400, detail="sotr debe ser 'sotra' o 'sotrb'")

    filename = f"BLC_NODE_{planta_base.upper()}_{sotr.upper()}.exe"
    filepath = OUTPUT_DIR / filename

    if not filepath.exists():
        raise HTTPException(404, detail=f"Instalador no encontrado: {filename}")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/historial")
def historial(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, planta_base, central_nombre, protocolo, usuario, sotra_cn, sotrb_cn, created_at
        FROM instalaciones_log ORDER BY created_at DESC LIMIT 50
    """)).fetchall()
    return [
        {
            "id": r[0], "planta_base": r[1], "central_nombre": r[2],
            "protocolo": r[3], "usuario": r[4], "sotra_cn": r[5],
            "sotrb_cn": r[6], "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]
