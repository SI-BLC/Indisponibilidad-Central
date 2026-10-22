from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from config import settings
from datetime import datetime
import httpx
import asyncio

router = APIRouter(prefix="/nodos", tags=["Nodos"])


def _node_base_url(ip: str, ssl: int = 0) -> str:
    if ssl:
        return f"https://{ip}:8443"
    return f"http://{ip}:8089"


def _node_auth(ssl: int = 0) -> httpx.BasicAuth | None:
    if ssl and settings.NODE_HTTPS_USER:
        return httpx.BasicAuth(settings.NODE_HTTPS_USER, settings.NODE_HTTPS_PASS)
    return None


@router.get("")
def get_nodos(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT c.ip1, c.nemo, c.tipo, c.protocolo, c.`ssl`,
               n.online, n.ultimo_check, n.ultimo_online, n.ultimo_caida, n.error_msg
        FROM centrales c
        LEFT JOIN nodos_estado n ON n.ip = c.ip1
        WHERE c.ip1 IS NOT NULL
        ORDER BY c.nemo
    """)).fetchall()

    nodos = {}
    for r in rows:
        ip = r[0]
        if ip not in nodos:
            nodos[ip] = {
                "ip": ip,
                "ssl": r[4],
                "online": bool(r[5]) if r[5] is not None else None,
                "ultimo_check": r[6].isoformat() if r[6] else None,
                "ultimo_online": r[7].isoformat() if r[7] else None,
                "ultimo_caida": r[8].isoformat() if r[8] else None,
                "error_msg": r[9],
                "centrales": [],
            }
        nodos[ip]["centrales"].append({
            "nemo": r[1],
            "tipo": r[2],
            "protocolo": r[3],
        })

    return list(nodos.values())


async def _check_single(ip: str, ssl: int, client: httpx.AsyncClient) -> dict:
    base = _node_base_url(ip, ssl)
    auth = _node_auth(ssl)
    try:
        resp = await client.get(f"{base}/checkenlaces", auth=auth)
        resp.raise_for_status()
        return {"ip": ip, "online": True, "error": None}
    except httpx.TimeoutException:
        return {"ip": ip, "online": False, "error": "Timeout"}
    except httpx.HTTPError as e:
        return {"ip": ip, "online": False, "error": str(e)[:200]}
    except Exception as e:
        return {"ip": ip, "online": False, "error": str(e)[:200]}


@router.post("/check")
async def check_nodos(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT DISTINCT c.ip1, c.`ssl`
        FROM centrales c
        WHERE c.ip1 IS NOT NULL
    """)).fetchall()

    nodes = [(r[0], r[1]) for r in rows]
    now = datetime.now()

    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        tasks = [_check_single(ip, ssl, client) for ip, ssl in nodes]
        results = await asyncio.gather(*tasks)

    checked = 0
    online_count = 0
    for r in results:
        was_online = db.execute(
            text("SELECT online FROM nodos_estado WHERE ip = :ip"),
            {"ip": r["ip"]},
        ).scalar()

        if was_online is None:
            db.execute(text("""
                INSERT INTO nodos_estado (ip, online, ultimo_check, ultimo_online, ultimo_caida, error_msg)
                VALUES (:ip, :on, :now, :uon, :uca, :err)
            """), {
                "ip": r["ip"], "on": int(r["online"]), "now": now,
                "uon": now if r["online"] else None,
                "uca": now if not r["online"] else None,
                "err": r["error"],
            })
        else:
            sets = ["online = :on", "ultimo_check = :now", "error_msg = :err"]
            params = {"ip": r["ip"], "on": int(r["online"]), "now": now, "err": r["error"]}
            if r["online"]:
                sets.append("ultimo_online = :now")
                if not was_online:
                    pass  # was down, now up — keep ultimo_caida as-is
            else:
                if was_online:
                    sets.append("ultimo_caida = :now")
            db.execute(text(f"UPDATE nodos_estado SET {', '.join(sets)} WHERE ip = :ip"), params)

        checked += 1
        if r["online"]:
            online_count += 1

    db.commit()
    return {"checked": checked, "online": online_count, "offline": checked - online_count}
