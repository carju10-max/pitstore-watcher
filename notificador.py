# -*- coding: utf-8 -*-
"""Avisos por Telegram reusando el bot de ClassRoom_Hijos (el mismo token/chat)."""
import os
import urllib.request
import urllib.parse
import json
from pathlib import Path

BASE = Path(__file__).parent


def _env():
    d = {}
    p = BASE / ".env.telegram"
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    # las variables de entorno (secretos de GitHub) tienen prioridad
    for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(k):
            d[k] = os.environ[k]
    return d


def avisar(texto: str) -> bool:
    """Manda un mensaje de texto a Carlos por Telegram. Devuelve True si llegó."""
    e = _env()
    tok, cid = e.get("TELEGRAM_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", "")
    if not (tok and cid):
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": cid, "text": texto}).encode()
    try:
        r = json.loads(urllib.request.urlopen(url, data=data, timeout=20).read())
        return bool(r.get("ok"))
    except Exception:
        return False


def enviar_foto(ruta_foto: str, caption: str = "") -> bool:
    """Manda una foto (con texto opcional) a Carlos por Telegram. multipart/form-data."""
    e = _env()
    tok, cid = e.get("TELEGRAM_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", "")
    if not (tok and cid) or not Path(ruta_foto).exists():
        return False
    url = f"https://api.telegram.org/bot{tok}/sendPhoto"
    boundary = "----claudeform"
    ruta = Path(ruta_foto)
    body = bytearray()

    def campo(nombre, valor):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode())
        body.extend(f"{valor}\r\n".encode())

    campo("chat_id", cid)
    if caption:
        campo("caption", caption[:1024])
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="photo"; filename="{ruta.name}"\r\n'.encode())
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(ruta.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=bytes(body),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return bool(r.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "ping de prueba"
    print("enviado:", avisar(msg))
