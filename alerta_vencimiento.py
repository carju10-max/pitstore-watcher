# -*- coding: utf-8 -*-
"""Alerta de vencimiento de planes de Shopify.

Corre 1 vez al día en GitHub Actions y avisa por Telegram durante los últimos
DIAS_AVISO días antes de que cada tienda salte de la promo al precio full.
Al ser una corrida diaria, manda un solo mensaje por día por tienda (sin spam).
"""
from datetime import date, datetime, timedelta, timezone

import notificador

DIAS_AVISO = 7  # avisar cada día durante los últimos 7 días antes del salto

# Cada tienda: nombre, la fecha en que SALTA a precio full, y el detalle del salto.
# (fechas tomadas de los screenshots del panel de Shopify — 31/07/2026)
TIENDAS = [
    {"nombre": "PitStore (pitstore.lat)", "fecha": date(2026, 9, 25),
     "detalle": "pasa de $1 a $25 USD/mes"},
    {"nombre": "Tienda nueva (€)",        "fecha": date(2026, 11, 2),
     "detalle": "pasa de €1 a €32 EUR/mes"},
]


def _hoy_lima() -> date:
    """Fecha de hoy en hora de Perú (UTC-5, sin horario de verano)."""
    return datetime.now(timezone(timedelta(hours=-5))).date()


def revisar(hoy: date | None = None):
    hoy = hoy or _hoy_lima()
    for t in TIENDAS:
        faltan = (t["fecha"] - hoy).days
        if faltan < 0 or faltan > DIAS_AVISO:
            continue

        if faltan == 0:
            cab = f"🚨 HOY vence la promo de {t['nombre']}"
        elif faltan == 1:
            cab = f"⏰ MAÑANA vence la promo de {t['nombre']}"
        else:
            cab = f"⏳ Faltan {faltan} días — {t['nombre']}"

        msg = (f"{cab}\n\n"
               f"El {t['fecha'].strftime('%d/%m/%Y')} tu tienda {t['detalle']}.\n"
               f"Si no quieres pagar el precio full, cámbiala o cancélala antes en "
               f"Shopify → Configuración → Plan.")
        ok = notificador.avisar(msg)
        print(f"{t['nombre']}: faltan {faltan} día(s) -> enviado={ok}")


if __name__ == "__main__":
    revisar()
