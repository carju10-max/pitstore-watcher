# -*- coding: utf-8 -*-
"""Vigilante de pedidos Shopify -> alerta a Carlos por Telegram con el mensaje
de confirmacion LISTO y un link wa.me para enviarlo desde su WhatsApp personal.

Cero costo: no usa plantillas de Meta ni saldo de Pancake. El envio final lo hace
Carlos con un tap (wa.me abre su WhatsApp con el texto ya escrito).

Uso:
    python watcher.py            # loop, revisa cada 3 min
    python watcher.py --once     # una sola pasada (ideal para Programador de tareas)
    python watcher.py --test     # marca todo lo actual como visto, sin avisar
"""
import json
import sys
import time
from pathlib import Path

import confirmaciones as conf
from notificador import avisar, enviar_foto

BASE = Path(__file__).parent
SEEN = BASE / ".watcher_seen.json"
INTERVALO = 30  # segundos entre revisiones en modo loop


def _foto_producto():
    """Si existe una foto de producto (producto.jpg/png/jpeg), la usa para adjuntar."""
    for nombre in ("producto.jpg", "producto.png", "producto.jpeg"):
        f = BASE / nombre
        if f.exists():
            return str(f)
    return None


def _seen() -> set:
    if SEEN.exists():
        try:
            return set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _guardar(vistos: set) -> None:
    SEEN.write_text(json.dumps(sorted(vistos)), encoding="utf-8")


def _alerta(p: dict) -> str:
    """Texto que le llega a Carlos por Telegram."""
    partes = [
        f"🔔 PEDIDO NUEVO {p['pedido']} — {p['cliente']}",
        f"{p.get('etiqueta', '')}".strip(),
        f"{p['producto']}  |  {p['total']} {p.get('moneda', '')}  |  {p['ciudad']}",
        "",
        "── Mensaje listo para el cliente ──",
        conf.mensaje_confirmacion(p, con_emojis=True),
    ]
    link = conf.wa_link(p)
    if link:
        partes += ["", "Tocar para enviar por tu WhatsApp:", link]
    else:
        partes += ["", "⚠️ Telefono no valido para WhatsApp, revisa el pedido en el panel."]
    return "\n".join(partes)


def _clave_seen(p: dict) -> str:
    """Clave del pedido en el archivo de vistos, con la tienda por delante.

    Hace falta porque los números de pedido EMPIEZAN EN #1001 EN CADA TIENDA: sin
    el prefijo, el #1001 de España se daría por avisado solo porque ya existía el
    #1001 de Ecuador, y ese pedido nunca te llegaría.
    """
    return f"{p.get('clave_tienda', 'ec')}:{p['pedido']}"


def _ya_visto(p: dict, vistos: set) -> bool:
    """Un pedido está visto si tiene su clave nueva o —solo en la tienda original—
    la clave antigua sin prefijo, que es como quedaron guardados los de antes."""
    if _clave_seen(p) in vistos:
        return True
    return p.get("clave_tienda") == "ec" and p["pedido"] in vistos


def revisar(avisar_nuevos: bool = True) -> int:
    tiendas = conf.tiendas_configuradas()
    if not tiendas:
        raise RuntimeError("No hay ninguna tienda configurada (SHOPIFY_STORE/TOKEN)")

    reales = []
    for t in tiendas:
        try:
            pedidos = conf.leer_pedidos(limite=100, tienda=t["tienda"],
                                        token=t["token"], pais=t["pais"])
        except Exception as e:
            # una tienda caída no puede dejar sin avisos a las demás
            print(f"error leyendo {t['etiqueta']} ({t['tienda']}): {e}")
            continue
        for p in pedidos:
            if p.get("es_prueba"):
                continue
            p["clave_tienda"] = t["clave"]
            p["etiqueta"] = t["etiqueta"]
            reales.append(p)
        print(f"{t['etiqueta']}: {len(pedidos)} pedidos leidos")

    vistos = _seen()
    nuevos = [p for p in reales if not _ya_visto(p, vistos)]

    if avisar_nuevos:
        foto = _foto_producto()
        for p in sorted(nuevos, key=lambda x: x["pedido"]):
            ok = False
            if foto:
                # foto del producto + mensaje como pie (como lo manda Carlos a mano)
                cap = (f"🔔 {p['pedido']} — {p['cliente']}  {p.get('etiqueta','')}\n\n"
                       + conf.mensaje_confirmacion(p, con_emojis=True))
                if enviar_foto(foto, caption=cap):
                    ok = True
                    link = conf.wa_link(p)
                    if link:
                        avisar("Abrir el WhatsApp del cliente:\n" + link)
            if not ok:  # sin foto o si fallo el envio de foto -> solo texto
                ok = avisar(_alerta(p))
            if ok:
                vistos.add(_clave_seen(p))
                print(f"avisado {p.get('etiqueta','')} {p['pedido']} {p['cliente']}")
            else:
                print(f"FALLO telegram para {p['pedido']} (reintento luego)")
    else:
        for p in reales:
            vistos.add(_clave_seen(p))

    _guardar(vistos)
    return len(nuevos)


def main():
    args = set(sys.argv[1:])
    if "--test" in args:
        revisar(avisar_nuevos=False)
        print("Marcado todo lo actual como visto. Los proximos pedidos si te avisan.")
        return
    if "--once" in args:
        n = revisar()
        print(f"revision unica: {n} nuevos")
        return
    # candado: si ya hay otro bucle vivo (heartbeat fresco), no arranco un segundo
    lock = BASE / ".watcher.lock"
    if lock.exists() and (time.time() - lock.stat().st_mtime) < INTERVALO * 3:
        print("Ya hay un watcher corriendo (candado fresco). Salgo.")
        return
    print(f"Vigilando Shopify cada {INTERVALO}s. Ctrl+C para parar.")
    while True:
        try:
            lock.write_text(str(int(time.time())), encoding="utf-8")  # heartbeat
            n = revisar()
            if n:
                print(f"  {n} pedidos nuevos avisados")
        except Exception as e:
            print("error en revision:", e)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
