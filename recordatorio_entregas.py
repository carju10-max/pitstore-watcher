# -*- coding: utf-8 -*-
"""Avisos de las reentregas pactadas tras una incidencia.

Cuando una entrega falla, Dropi da una fecha para el siguiente intento. Manda
dos avisos distintos por Telegram:

  · LA VÍSPERA — con el mensaje listo para que el cliente esté en casa. La
    ventana buena para escribir a España es 17-18 h de allí, o sea 10-11 de la
    mañana en Perú; por eso se avisa el día antes y no el mismo día.

  · CUANDO LA FECHA YA PASÓ y el pedido sigue sin entregarse. Esa fecha es una
    PROMESA de Dropi, no un hecho: puede que ese día no vayan, y ese fallo no
    avisa solo — se queda callado durante días.

Las fechas salen de `reentregas.json`, que se edita desde la ficha del pedido
en el CRM. Antes estaban escritas a mano aquí dentro.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import notificador

BASE = Path(__file__).parent
# El CRM manda: es donde Carlos las apunta. La copia del repo es el respaldo
# para cuando esto corre en GitHub Actions, sin acceso a la laptop.
PROYECTO = Path(r"C:\Users\HP\Documents\CARLOS\ClaudeCode\Productos Ganadores DropShipping")
FUENTES = [PROYECTO / "reentregas.json", BASE / "reentregas.json"]
# Para no repetir el mismo aviso en cada pasada del vigilante (corre cada minuto)
YA_AVISADO = BASE / ".reentregas_avisadas.json"


def _hoy_lima() -> date:
    """Hoy en hora de Perú (UTC-5, sin horario de verano)."""
    return datetime.now(timezone(timedelta(hours=-5))).date()


def _cargar() -> dict:
    """Las reentregas conocidas: las apuntadas a mano MÁS las que el CRM leyó
    del historial de Dropi. Lo apuntado a mano manda."""
    fuera = {}
    # 1) lo que el CRM detectó solo en el historial de Dropi
    for f in (PROYECTO / "reentregas_auto.json", BASE / "reentregas_auto.json"):
        if f.exists():
            try:
                fuera.update(json.loads(f.read_text(encoding="utf-8")))
                break
            except Exception as e:
                print(f"[reentregas] {f.name} ilegible: {e}")
    # 2) lo apuntado a mano, que pisa lo anterior
    for f in FUENTES:
        if f.exists():
            try:
                fuera.update(json.loads(f.read_text(encoding="utf-8")))
                break
            except Exception as e:
                print(f"[reentregas] {f.name} ilegible: {e}")
    return fuera


def _avisadas() -> dict:
    if YA_AVISADO.exists():
        try:
            return json.loads(YA_AVISADO.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _marcar(clave: str, tipo: str) -> None:
    d = _avisadas()
    d[f"{clave}|{tipo}|{_hoy_lima()}"] = True
    YA_AVISADO.write_text(json.dumps(d), encoding="utf-8")


def _entregado(clave: str) -> bool:
    """¿Ya se entregó? Si sí, no hay nada que avisar aunque la fecha pasara."""
    try:
        import confirmaciones as conf
        for n in conf.cargar_notas().get(clave, []):
            if n.get("resultado") in ("recibio", "gracias"):
                return True
    except Exception:
        pass
    return False


def _mensaje_cliente(nombre: str, fecha: date) -> str:
    """El texto para el cliente. Se manda la víspera, así que dice 'mañana'.

    Ojo con el tono: la fecha la da Dropi y puede fallar, así que no se promete
    la entrega — se le pide que esté disponible.
    """
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return (
        f"¡Hola {nombre}! Te escribo de PitStore.\n\n"
        f"Mañana {dias[fecha.weekday()]} deberían llevarte el pedido de las bolsas. "
        f"Como la otra vez no hubo suerte, te aviso con tiempo.\n\n"
        f"Estate atento por si el repartidor intenta contactarte, y si no vas a "
        f"estar, déjalo dicho con alguien que pueda recibirlo y tenga el importe "
        f"preparado.\n\n"
        f"Si mañana no te viene bien, dímelo hoy y lo movemos. ¡Gracias!"
    )


def main() -> int:
    hoy = _hoy_lima()
    manana = hoy + timedelta(days=1)
    datos = _cargar()
    if not datos:
        print(f"[reentregas] {hoy}: no hay ninguna apuntada.")
        return 0

    ya = _avisadas()
    vispera, vencidas = [], []
    for clave, r in datos.items():
        try:
            f = date.fromisoformat(str(r.get("fecha", ""))[:10])
        except ValueError:
            continue
        if f == manana and f"{clave}|vispera|{hoy}" not in ya:
            vispera.append((clave, r, f))
        elif f < hoy and not _entregado(clave):
            # solo una vez al día, no en cada pasada del vigilante
            if f"{clave}|vencida|{hoy}" not in ya:
                vencidas.append((clave, r, f))

    for clave, r, f in vispera:
        # Solo el nombre de pila: la nota trae "Isabel Garrido Arenas — Ciudad"
        # y saludar con el nombre completo suena a carta del banco.
        nombre = ((r.get("nota") or clave).split("—")[0].strip().split() or [clave])[0]
        pedido = clave.split(":")[-1]
        # Si la fecha vino del historial de Dropi no sabemos el número de intento,
        # pero una reprogramación es como mínimo el segundo.
        intento = r.get("intento") or 2
        notificador.avisar(
            f"📦 <b>MAÑANA deberían entregar {pedido}</b> ({f:%d-%m})\n"
            f"{r.get('nota', '')}\n"
            f"⚠️ Va por el intento {intento}: si falla, el siguiente "
            f"cobra envío extra.\n\n"
            f"Escríbele <b>hoy entre las 10 y las 11 de la mañana</b> (17-18 h en España):\n"
            f"<code>{_mensaje_cliente(nombre, f)}</code>")
        _marcar(clave, "vispera")
        print(f"[reentregas] avisado {pedido} (víspera)")

    for clave, r, f in vencidas:
        pedido = clave.split(":")[-1]
        notificador.avisar(
            f"⚠️ <b>{pedido}: la reentrega era el {f:%d-%m} y sigue sin entregarse</b>\n"
            f"{r.get('nota', '')}\n"
            f"Van {(hoy - f).days} día(s) de retraso. Pregúntale a Dropi qué pasó — "
            f"esa fecha era una promesa, no un hecho.")
        _marcar(clave, "vencida")
        print(f"[reentregas] avisado {pedido} (vencida)")

    if not vispera and not vencidas:
        print(f"[reentregas] {hoy}: nada que avisar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
