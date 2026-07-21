# -*- coding: utf-8 -*-
"""Lee los pedidos de Shopify y arma la confirmación COD por WhatsApp.

La lógica vive aquí (y no en app.py) porque la misma sirve para los dos caminos:
hoy genera links wa.me para mandar a mano, y el día que Meta apruebe la plantilla
solo se cambia el enviador — los pedidos, los teléfonos y el texto no se tocan.
"""
import os
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
ENV_SHOPIFY = BASE / "Shopify" / ".env"
API_VERSION = "2024-10"
CONTACTADOS = BASE / "confirmaciones_contactados.json"


def cargar_contactados() -> dict:
    """{ '#1033': '2026-07-15T21:04' } — a quién ya se le escribió."""
    if CONTACTADOS.exists():
        try:
            return json.loads(CONTACTADOS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def marcar_contactado(pedido: str) -> dict:
    d = cargar_contactados()
    d[pedido] = datetime.now().isoformat(timespec="minutes")
    CONTACTADOS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


# ------------------------------------------------------------------ #
# Notas de contacto: qué dijo cada cliente al contactarlo.
# Es la materia prima para los insights: no solo "cuántos no confirman"
# sino POR QUÉ (no reconoce el pedido, no responde, precio, etc.).
# ------------------------------------------------------------------ #
NOTAS = BASE / "confirmaciones_notas.json"

# Categorías de resultado. El texto es lo que ve Carlos; la clave agrupa para contar.
RESULTADOS = {
    "confirmo":        "✅ Confirmó — despachar",
    "no_reconoce":     "❓ No sabe de qué trata el pedido",
    "no_responde":     "🔇 No responde / no contesta",
    "corregir_dir":    "📝 Corrige la dirección",
    "cancela":         "❌ Se arrepiente / cancela",
    "dice_si_no_paga": "⚠️ Dice sí pero duda / no aterriza",
    "precio_info":     "💬 Pregunta precio / más info",
    "num_equivocado":  "📵 Número equivocado / no existe",
    "recontactar":     "⏳ Pide que lo contacten después",
    "otro":            "⋯ Otro (ver nota)",
}


def cargar_notas() -> dict:
    """{ '#1008': [ {ts, resultado, texto}, ... ] } — historial por pedido."""
    if NOTAS.exists():
        try:
            return json.loads(NOTAS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def agregar_nota(pedido: str, resultado: str, texto: str = "", cuando=None) -> dict:
    """`cuando` = datetime del contacto. Si es None, usa el momento actual."""
    d = cargar_notas()
    ts = (cuando or datetime.now()).isoformat(timespec="minutes")
    d.setdefault(pedido, []).append({
        "ts": ts,
        "resultado": resultado,
        "texto": texto.strip(),
    })
    NOTAS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


# ------------------------------------------------------------------ #
# Evidencias de entrega: la foto que Dropi da como prueba de entregado.
# Sirven para (a) verlas en el pedido y (b) más adelante subirlas a la
# tienda como prueba social. Se nombran <pedido>_<guia>_<cliente>.jpg
# ------------------------------------------------------------------ #
EVIDENCIAS = BASE / "evidencias_entrega"


def evidencias_de(pedido: str) -> list:
    """Rutas de las fotos de evidencia de un pedido (por prefijo del nombre)."""
    if not EVIDENCIAS.exists():
        return []
    num = pedido.lstrip("#")
    return sorted(str(p) for p in EVIDENCIAS.iterdir()
                  if p.is_file() and p.name.startswith(f"{num}_"))


def borrar_nota(pedido: str, indice: int) -> dict:
    """Elimina una nota del historial de un pedido por su posición."""
    d = cargar_notas()
    hist = d.get(pedido, [])
    if 0 <= indice < len(hist):
        hist.pop(indice)
        if hist:
            d[pedido] = hist
        else:
            d.pop(pedido, None)  # sin notas, quita el pedido del archivo
        NOTAS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


# ------------------------------------------------------------------ #
# Etiquetas (tags) por pedido — para clasificar clientes en el CRM.
# ------------------------------------------------------------------ #
ETIQUETAS = {
    "riesgoso":   {"txt": "⛔ RIESGOSO",       "color": "#dc2626"},
    "vip":        {"txt": "⭐ VIP",            "color": "#f59e0b"},
    "recontactar":{"txt": "🔁 Recontactar",   "color": "#3b82f6"},
    "dificil":    {"txt": "⚠️ Difícil",        "color": "#ef4444"},
    "prometio":   {"txt": "💰 Prometió pagar", "color": "#10b981"},
    "oficina":    {"txt": "🏢 Oficina",        "color": "#8b5cf6"},
    "revisar":    {"txt": "👀 Revisar",         "color": "#ec4899"},
}
_ETIQ_FILE = BASE / "confirmaciones_etiquetas.json"


def cargar_etiquetas() -> dict:
    """{ '#1032': ['vip','oficina'] }"""
    if _ETIQ_FILE.exists():
        try:
            return json.loads(_ETIQ_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def toggle_etiqueta(pedido: str, tag: str) -> dict:
    d = cargar_etiquetas()
    actuales = d.get(pedido, [])
    if tag in actuales:
        actuales.remove(tag)
    elif tag in ETIQUETAS:
        actuales.append(tag)
    if actuales:
        d[pedido] = actuales
    else:
        d.pop(pedido, None)
    _ETIQ_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def resumen_resultados(notas: dict) -> dict:
    """Cuenta el ÚLTIMO resultado de cada pedido — para insights sin doble conteo."""
    from collections import Counter
    ultimos = [hist[-1]["resultado"] for hist in notas.values() if hist]
    return dict(Counter(ultimos))


def _leer_env(ruta: Path) -> dict:
    d = {}
    if ruta.exists():
        for ln in ruta.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def normalizar_tel(tel: str, pais: str = "EC") -> str:
    """Devuelve el celular en formato internacional (E.164) o "" si no se puede.

    Ecuador escribe sus celulares como 09XXXXXXXX en local, pero en internacional
    ese 0 inicial NO va: +593 9XXXXXXXX. Shopify guarda en shipping_address.phone
    un "+593" pegado al número local SIN quitar el 0 -> "+5930983519210", que tiene
    un dígito de más y no existe. 17 de 33 pedidos estaban así.
    """
    if not tel:
        return ""
    t = re.sub(r"[^\d+]", "", str(tel))
    if not t:
        return ""

    if pais.upper() == "EC":
        t = t.lstrip("+")
        if t.startswith("5930"):        # el caso roto: +593 + 0983519210
            t = "593" + t[4:]
        elif t.startswith("09"):        # local: 0983519210
            t = "593" + t[1:]
        elif t.startswith("9") and len(t) == 9:   # sin 0 ni país: 983519210
            t = "593" + t
        if not t.startswith("593"):
            t = "593" + t
        # celular EC valido = 593 + 9 + 8 digitos = 12
        return "+" + t if len(t) == 12 else ""

    return t if t.startswith("+") else "+" + t


def _attr(pedido: dict, nombre: str) -> str:
    """Saca un campo del formulario COD (Releasit los deja en note_attributes)."""
    for a in pedido.get("note_attributes") or []:
        if a.get("name", "").strip().lower() == nombre.strip().lower():
            return (a.get("value") or "").strip()
    return ""


# Nombres con los que Carlos hace sus pedidos de prueba. Un match por nombre SOLO
# cuenta si ademas el celular se parece a los suyos (ver es_prueba): "Carlos" a secas
# es un nombre comun y no queremos descartar a un cliente real que se llame asi.
NOMBRES_PRUEBA = ("carlos", "hola", "diaz", "díaz")


def _es_prueba(tel: str, nombre: str, tels_prueba: set) -> bool:
    """Detecta pedidos de prueba de Carlos.

    No basta comparar contra un celular exacto: usa variantes del mismo prefijo
    y nombres tipo "Hola" o "Carlos Díaz". La regla: mismo prefijo de celular
    (los primeros 6 digitos del nacional) O celular exacto O (nombre de prueba Y
    celular de la misma familia que se usa para testear).
    """
    solo_num = re.sub(r"\D", "", tel or "")
    nac = solo_num[3:] if solo_num.startswith("593") else solo_num  # sin codigo pais
    nom = (nombre or "").strip().lower()

    for t in tels_prueba:
        if not t:
            continue
        if t == nac or t in solo_num:
            return True
        if len(t) >= 6 and len(nac) >= 6 and t[:6] == nac[:6]:
            return True   # mismo prefijo de 6 digitos -> misma linea de pruebas

    if any(n in nom for n in NOMBRES_PRUEBA):
        for t in tels_prueba:
            if len(t) >= 4 and len(nac) >= 4 and t[:4] == nac[:4]:
                return True
    return False


PRUEBAS_FILE = BASE / "confirmaciones_pruebas.json"


def cargar_pruebas() -> list:
    """Lista de pedidos marcados A MANO como prueba (ej: ['#1017','#1003'])."""
    if PRUEBAS_FILE.exists():
        try:
            return json.loads(PRUEBAS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def toggle_prueba(pedido: str) -> list:
    d = cargar_pruebas()
    if pedido in d:
        d.remove(pedido)
    else:
        d.append(pedido)
    PRUEBAS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def leer_pedidos(limite: int = 250, tels_prueba: str = "") -> list:
    """Trae los pedidos de Shopify ya normalizados y listos para confirmar."""
    env = _leer_env(ENV_SHOPIFY)
    tienda = os.environ.get("SHOPIFY_STORE") or env.get("SHOPIFY_STORE", "")
    token = os.environ.get("SHOPIFY_TOKEN") or env.get("SHOPIFY_TOKEN", "")
    if not (tienda and token):
        raise RuntimeError("Faltan SHOPIFY_STORE / SHOPIFY_TOKEN en Shopify/.env")

    url = (f"https://{tienda}/admin/api/{API_VERSION}/orders.json"
           f"?status=any&limit={min(limite, 250)}")
    req = urllib.request.Request(url, headers={"X-Shopify-Access-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        crudos = json.loads(r.read()).get("orders", [])

    # celulares de prueba de Carlos -> se marcan, no ensucian la lista real
    prueba = {re.sub(r"\D", "", t) for t in (tels_prueba or "").split(",") if t.strip()}
    manual = set(cargar_pruebas())  # pedidos marcados a mano como prueba

    pedidos = []
    for o in crudos:
        env_dir = o.get("shipping_address") or {}
        # SIEMPRE order.phone: shipping_address.phone viene roto (ver normalizar_tel)
        tel = normalizar_tel(o.get("phone") or _attr(o, "Número de Whatsapp")
                             or env_dir.get("phone"))
        # formato local ecuatoriano CON el 0 inicial (0982875678): es el que Carlos
        # copia y pega en WhatsApp. El wa.me sigue usando 'tel' internacional sin 0.
        if tel:
            _dig = re.sub(r"\D", "", tel)               # 593982875678
            _nac = _dig[3:] if _dig.startswith("593") else _dig  # 982875678
            tel_local = _nac if _nac.startswith("0") else "0" + _nac  # 0982875678
        else:
            tel_local = ""
        etiquetas = o.get("tags") or ""
        nombre = (_attr(o, "Nombre y Apellido")
                  or " ".join(filter(None, [(o.get("customer") or {}).get("first_name"),
                                            (o.get("customer") or {}).get("last_name")])))
        es_prueba = _es_prueba(tel, nombre, prueba) or (o.get("name", "") in manual)

        pedidos.append({
            "pedido": o.get("name") or "",
            "fecha": o.get("created_at") or "",
            "cliente": (_attr(o, "Nombre y Apellido")
                        or " ".join(filter(None, [(o.get("customer") or {}).get("first_name"),
                                                  (o.get("customer") or {}).get("last_name")]))),
            "telefono": tel,
            "tel_local": tel_local,
            "tel_ok": bool(tel),
            "producto": ", ".join(f"{li.get('title')} x{li.get('quantity')}"
                                  for li in o.get("line_items") or []),
            "total": o.get("total_price") or "0",
            "moneda": o.get("currency") or "USD",
            "direccion": _attr(o, "Dirección completa") or env_dir.get("address1") or "",
            "referencia": _attr(o, "Referencia de domicilio o trabajo") or env_dir.get("address2") or "",
            "ciudad": _attr(o, "Ciudad") or env_dir.get("city") or "",
            "provincia": _attr(o, "Provincia") or env_dir.get("province") or "",
            "cancelado": bool(o.get("cancelled_at")),
            "en_dropi": "order sent to dropi" in etiquetas.lower(),
            "error_dropi": "dropi sync error" in etiquetas.lower(),
            "es_prueba": es_prueba,
            "utm_campaign": _attr(o, "UTM campaign"),
        })
    return pedidos


def mensaje_confirmacion(p: dict, con_emojis: bool = True) -> str:
    """El texto que ve el cliente. Incluye la dirección a propósito: las entregas
    fallan por direcciones incompletas, así que se confirma pedido Y dirección.

    con_emojis=False para los links wa.me: Windows mangla los caracteres de 4 bytes
    (los emojis) al pasarle el texto a WhatsApp por el protocolo, y llegan como "?".
    Las tildes (2 bytes) sí sobreviven. En la plantilla de Meta los emojis van bien
    porque ese camino es HTTPS puro y no pasa por Windows.
    """
    primer = (p["cliente"] or "").strip().split()[0] if (p["cliente"] or "").strip() else "hola"
    # telefono para pegar en WhatsApp: +593 + numero local con 0  ->  +5930994512808
    tel_pega = ("+593" + p["tel_local"]) if p.get("tel_local") else p.get("telefono", "")
    direccion = p["direccion"]
    if p["referencia"] and p["referencia"] not in ("-", ""):
        direccion += f". Referencia: {p['referencia']}"
    ciudad = ", ".join(filter(None, [p["ciudad"], p["provincia"]]))
    dir_full = ", ".join(filter(None, [direccion, ciudad])) + "."

    if con_emojis:
        return (
            f"¡Hola {primer}! 👋 Gracias por tu pedido de {p['producto']}. "
            f"Te saluda *Martha* de PitStore.\n\n"
            f"A partir de mañana la *transportadora* se comunicará contigo para "
            f"coordinar la entrega. Por favor, mantente atento a tu teléfono. 📦\n\n"
            f"*Confirma que estos datos sean correctos:*\n\n"
            f"📍 *Dirección:* {dir_full}\n"
            f"👤 *Destinatario:* {p['cliente']}\n"
            f"📞 *Teléfono:* {tel_pega}\n\n"
            f"Si algún dato es incorrecto, por favor avísanos para actualizarlo antes del envío.\n\n"
            f"💵 *Recuerda que el pago se realiza contra entrega al recibir tu pedido (${p['total']}).*"
        )
    return (
        f"Hola {primer}! Gracias por tu pedido de {p['producto']}. "
        f"Te saluda Martha de PitStore.\n\n"
        f"A partir de mañana la transportadora se comunicara contigo para "
        f"coordinar la entrega. Por favor mantente atento a tu telefono.\n\n"
        f"Confirma que estos datos sean correctos:\n"
        f"Direccion: {dir_full}\n"
        f"Destinatario: {p['cliente']}\n"
        f"Telefono: {tel_pega}\n\n"
        f"Si algun dato es incorrecto, avisanos para actualizarlo antes del envio.\n\n"
        f"Recuerda que el pago se realiza contra entrega al recibir tu pedido (${p['total']})."
    )


def wa_link(p: dict) -> str:
    """Link wa.me que abre el chat con el mensaje ya escrito (sin emojis, ver arriba)."""
    if not p["tel_ok"]:
        return ""
    return (f"https://wa.me/{p['telefono'].lstrip('+')}"
            f"?text={urllib.parse.quote(mensaje_confirmacion(p, con_emojis=True))}")


def horas_desde(fecha_iso: str) -> float:
    """Horas transcurridas desde que entró el pedido."""
    if not fecha_iso:
        return 9999.0
    try:
        f = datetime.fromisoformat(fecha_iso)
        return (datetime.now(timezone.utc) - f.astimezone(timezone.utc)).total_seconds() / 3600
    except Exception:
        return 9999.0


def urgencia(pedido: dict) -> tuple:
    """(emoji, etiqueta) según qué tan fresco está.

    La tasa de confirmación se desploma con las horas: un pedido de hoy se salva,
    uno de hace una semana ya está muerto y escribirle es perder el tiempo.
    """
    h = horas_desde(pedido["fecha"])
    if h <= 6:
        return ("🔥", "RECIÉN ENTRADO — escríbele YA")
    if h <= 24:
        return ("⏰", "de hoy — todavía se salva")
    if h <= 72:
        return ("🥶", "enfriándose")
    return ("🧊", "frío — probablemente perdido")


def por_confirmar(pedidos: list) -> list:
    """Los que valen la pena tocar: no cancelados, no prueba, con teléfono.
    Ordenados del más fresco al más viejo: los de arriba son los que dan plata."""
    vivos = [p for p in pedidos
             if not p["cancelado"] and not p["es_prueba"] and p["tel_ok"]]
    return sorted(vivos, key=lambda p: p["fecha"], reverse=True)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    todos = leer_pedidos(tels_prueba=os.environ.get("TEST_PHONES", ""))
    print(f"pedidos leidos: {len(todos)}")
    print(f"por confirmar : {len(por_confirmar(todos))}")
    print(f"error dropi   : {sum(1 for p in todos if p['error_dropi'])}")
    print(f"sin telefono  : {sum(1 for p in todos if not p['tel_ok'])}")
    p = por_confirmar(todos)[0]
    print("\n--- ejemplo ---")
    print(mensaje_confirmacion(p))
    print("\n" + wa_link(p)[:110] + "...")
