# PitStore · Watcher de pedidos (nube)

Revisa los pedidos nuevos de Shopify **cada 5 minutos, 24/7** (aunque la PC esté apagada)
y avisa por Telegram con el mensaje de confirmación COD listo para enviar al cliente.

Corre en **GitHub Actions** (gratis, en repo público). No guarda ni expone credenciales:
la tienda, el token de Shopify y el bot de Telegram viven como **Secrets** del repo.

## Cómo funciona
- `watcher.py` — compara los pedidos de Shopify con los ya avisados (`.watcher_seen.json`)
  y manda los nuevos a Telegram. Modo `--once` para la nube.
- `confirmaciones.py` — lee Shopify y arma el mensaje (corrige el bug del teléfono de Ecuador).
- `notificador.py` — envía por Telegram.
- `.github/workflows/watcher.yml` — el cron cada 5 minutos.

## Secrets necesarios
`SHOPIFY_STORE`, `SHOPIFY_TOKEN`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TEST_PHONES` (opcional).
