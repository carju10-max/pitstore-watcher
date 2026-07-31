# -*- coding: utf-8 -*-
"""Alerta de vencimiento de planes de Shopify.

Corre 1 vez al día en GitHub Actions y avisa por Telegram durante los últimos
DIAS_AVISO días antes de que cada tienda salte de la promo al precio full.
Al ser una corrida diaria, manda un solo mensaje por día por tienda (sin spam).
"""
from datetime import date, datetime, timedelta, timezone

import notificador

DIAS_AVISO = 7  # avisar cada día durante los últimos 7 días antes del salto

# Cada tienda: icono, nombre, la fecha en que SALTA a precio full, y el detalle.
# (fechas tomadas de los screenshots del panel de Shopify — 31/07/2026)
TIENDAS = [
    {"icono": "🏁", "nombre": "PitStore (pitstore.lat)", "fecha": date(2026, 9, 25),
     "detalle": "pasa de $1 a $25 USD/mes"},
    {"icono": "🇪🇺", "nombre": "Tienda nueva (€)",        "fecha": date(2026, 11, 2),
     "detalle": "pasa de €1 a €32 EUR/mes"},
]


def _hoy_lima() -> date:
    """Fecha de hoy en hora de Perú (UTC-5, sin horario de verano)."""
    return datetime.now(timezone(timedelta(hours=-5))).date()


def _barra(faltan: int) -> str:
    """Cuenta regresiva visual de 7 casillas: 🟥 = días que ya pasaron, 🟩 = los que quedan."""
    quedan = max(0, min(DIAS_AVISO, faltan))
    return "🟥" * (DIAS_AVISO - quedan) + "🟩" * quedan


def _urgencia(faltan: int) -> tuple:
    """(emoji de banda, etiqueta) según qué tan cerca está el salto de precio."""
    if faltan == 0:
        return ("🚨🚨🚨", "¡HOY SUBE EL PRECIO!")
    if faltan == 1:
        return ("🔴🔥", "¡MAÑANA sube el precio!")
    if faltan <= 3:
        return ("🟠⏰", f"Faltan {faltan} días")
    return ("🟡⏳", f"Faltan {faltan} días")


def revisar(hoy: date | None = None):
    hoy = hoy or _hoy_lima()
    for t in TIENDAS:
        faltan = (t["fecha"] - hoy).days
        if faltan < 0 or faltan > DIAS_AVISO:
            continue

        banda, etiqueta = _urgencia(faltan)
        msg = (
            f"{banda} ALERTA DE VENCIMIENTO {banda}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{t['icono']} {t['nombre']}\n\n"
            f"⌛ {etiqueta}\n"
            f"{_barra(faltan)}\n\n"
            f"📅 Vence: {t['fecha'].strftime('%d/%m/%Y')}\n"
            f"💸 {t['detalle'][:1].upper() + t['detalle'][1:]}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 Cámbiala o cancélala antes en:\n"
            f"🛒 Shopify → Configuración → Plan"
        )
        ok = notificador.avisar(msg)
        print(f"{t['nombre']}: faltan {faltan} día(s) -> enviado={ok}")


if __name__ == "__main__":
    revisar()
