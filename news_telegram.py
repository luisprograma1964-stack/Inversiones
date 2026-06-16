"""
Sub-módulo de captura de noticias vía Telegram.
Extrae mensajes recientes de canales financieros específicos.
"""
from telethon import TelegramClient
from datetime import datetime, timezone
import asyncio
import os
import config
import logging_config

logger = logging_config.get_logger(__name__)

async def capturar_mensajes(canales):
    """
    Se conecta a Telegram y extrae los últimos mensajes de los canales configurados.
    """
    noticias_capturadas = []
    
    # Asegurar que la carpeta creds existe para guardar la sesión
    if not os.path.exists('creds'):
        os.makedirs('creds')

    # Creamos el cliente de Telegram
    client = TelegramClient('creds/anon', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
    
    try:
        await client.start()
        for canal in canales:
            try:
                entity = await client.get_entity(canal)
                # Traemos los últimos 5 mensajes de cada canal
                async for message in client.iter_messages(entity, limit=5):
                    if message.text and len(message.text) > 10:
                        # Limpiamos el texto para que sea un titular (primera línea)
                        titular = message.text.split('\n')[0][:200]
                        
                        noticias_capturadas.append({
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "ticker": "9999",
                            "titular": titular,
                            "fuente": "Telegram",
                            "submodulo": "TELEGRAM",
                            "url": f"https://t.me/{canal.replace('@','')}/{message.id}",
                            "canal_origen": canal
                        })
            except Exception as e:
                logger.exception(f"Error en canal {canal}: {e}")
    finally:
        await client.disconnect()
        
    return noticias_capturadas

def capturar_telegram(canales):
    """Wrapper sincrónico para el orquestador"""
    if not canales: return []
    try:
        return asyncio.run(capturar_mensajes(canales))
    except Exception as e:
        logger.exception(f"Error crítico en sub-módulo Telegram: {e}")
        return []

if __name__ == "__main__":
    res = capturar_telegram(["@DolarHoy"])
    logger.info(f"Capturados {len(res)} mensajes de Telegram.")