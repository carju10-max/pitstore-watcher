# -*- coding: utf-8 -*-
"""Vigilante RÁPIDO: el mismo watcher, pero corriendo en la laptop cada minuto.

¿Por qué existe si ya hay uno en la nube? Porque GitHub Actions no cumple el
cron de 5 minutos en repos gratis: en la práctica pasa entre 15 y 30 minutos
entre pasada y pasada. Para enterarte de un pedido al minuto hay que vigilar
desde aquí.

Los dos conviven: el local avisa rápido mientras la laptop está encendida, el
de la nube cubre cuando está apagada. No se duplican porque comparten
.watcher_seen.json a través del repo (ver bajar_estado/subir_estado).

Las credenciales NO se copian: se leen de donde ya viven, en el proyecto
principal, y se pasan por variables de entorno.
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent
PROYECTO = Path(r"C:\Users\HP\Documents\CARLOS\ClaudeCode\Productos Ganadores DropShipping")


def _cargar(archivo: Path) -> int:
    """Mete las claves de un .env en el entorno. Devuelve cuántas cargó."""
    if not archivo.exists():
        print(f"  aviso: no encuentro {archivo}")
        return 0
    n = 0
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v
            n += 1
    return n


def _cargar_es(archivo: Path) -> int:
    """Igual que _cargar, pero renombrando SHOPIFY_STORE -> SHOPIFY_STORE_ES."""
    if not archivo.exists():
        print(f"  aviso: no encuentro {archivo} (España quedaría sin vigilar)")
        return 0
    n = 0
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN") and v:
            destino = k + "_ES"
            if not os.environ.get(destino):
                os.environ[destino] = v
                n += 1
    return n


def main() -> int:
    n = _cargar(PROYECTO / "Shopify" / ".env")
    n += _cargar(PROYECTO / ".env.telegram")
    # España vive en su propio archivo y con las claves SIN sufijo; el watcher
    # las espera con _ES. Sin esta traduccion el vigilante ve solo Ecuador, que
    # es justo el punto ciego que tuvimos 10 dias.
    n += _cargar_es(PROYECTO / "Shopify" / ".env.es")
    print(f"credenciales cargadas: {n} claves")

    import watcher
    # Sin argumentos, watcher.main() entra en el bucle de cada minuto.
    sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:]]
    return watcher.main() or 0


if __name__ == "__main__":
    raise SystemExit(main())
