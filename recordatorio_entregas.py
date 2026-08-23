# -*- coding: utf-8 -*-
"""Recordatorio de reentregas acordadas con el cliente.

Cuando una incidencia se gestiona y se pacta una nueva fecha de entrega, el
cliente tiene que ESTAR EN CASA ese día. Si no, se gasta el 2º intento y el
tercero ya cuesta envío extra (y a los 10 días el paquete se devuelve solo).

Este script corre 1 vez al día y avisa por Telegram **la víspera**, con el
mensaje ya escrito para copiar y pegar.

⏰ Por qué la víspera y no el mismo día: la ventana buena para escribir a España
es 17:00-18:00 hora de allí, que son las 10-11 de la mañana en Perú. El mismo
día por la mañana en España serían las 2 de la madrugada para Carlos.

Para añadir una reentrega: mete una entrada en ENTREGAS. Cuando pase la fecha,
deja de avisar solo.
"""
from datetime import date, datetime, timedelta, timezone

import notificador

# Reentregas pactadas. fecha = el día que la transportadora va a ir.
ENTREGAS = [
    {"pedido": "#1018", "nombre": "Isabel", "cliente": "Isabel Garrido Arenas",
     "tel": "+34627625079", "ciudad": "Castilleja del Campo (Sevilla)",
     "fecha": date(2026, 8, 25), "importe": "34,99 €", "intento": 2},
    {"pedido": "#1014", "nombre": "Maria Rosa", "cliente": "Maria Rosa López Fernandez",
     "tel": "+34679466943", "ciudad": "Oleiros (A Coruña)",
     "fecha": date(2026, 8, 25), "importe": "27,99 €", "intento": 2},
]


def _hoy_lima() -> date:
    """Hoy en hora de Perú (UTC-5, sin horario de verano)."""
    return datetime.now(timezone(timedelta(hours=-5))).date()


def _mensaje_cliente(e: dict) -> str:
    """El texto para el cliente. Se manda la víspera, así que dice 'mañana'."""
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    dia = dias[e["fecha"].weekday()]
    return (
        f"¡Hola {e['nombre']}! Te escribo de PitStore.\n\n"
        f"Mañana {dia} te llevan el pedido de las bolsas. Como la otra vez no hubo "
        f"suerte, te aviso con tiempo para que estés pendiente.\n\n"
        f"Si por lo que sea no vas a estar, dímelo hoy y lo movemos a otro día, sin "
        f"problema. Es mejor eso que se vuelva a perder el viaje. ¡Gracias!"
    )


def main() -> int:
    hoy = _hoy_lima()
    manana = hoy + timedelta(days=1)
    pendientes = [e for e in ENTREGAS if e["fecha"] == manana]
    if not pendientes:
        print(f"[recordatorio] {hoy}: ninguna reentrega para mañana ({manana}).")
        return 0

    cab = (f"📦 <b>MAÑANA hay {len(pendientes)} reentrega"
           f"{'s' if len(pendientes) > 1 else ''}</b> ({manana:%d-%m})\n"
           f"Escríbeles <b>hoy entre las 10 y las 11 de la mañana</b> "
           f"(17-18 h en España).\n"
           f"⚠️ Van por el intento 2 de 2: si falla, el tercero cobra envío extra.")
    notificador.avisar(cab)

    for e in pendientes:
        detalle = (f"👤 <b>{e['cliente']}</b>  ·  {e['pedido']}\n"
                   f"📍 {e['ciudad']}  ·  {e['importe']}\n"
                   f"📱 <code>{e['tel']}</code>\n\n"
                   f"Mensaje listo para copiar:\n"
                   f"<code>{_mensaje_cliente(e)}</code>")
        notificador.avisar(detalle)
        print(f"[recordatorio] avisado {e['pedido']} ({e['cliente']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
