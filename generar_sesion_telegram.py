import sys
import os
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Forzar lectura de .env local (si existe)
from dotenv import load_dotenv
load_dotenv()

# Intentar sacar las credenciales del .env o pedir por consola
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("No se encontraron TELEGRAM_API_ID o TELEGRAM_API_HASH en el archivo .env")
    print("Por favor, introducí tus credenciales manualmente.")
    api_id = input("TELEGRAM_API_ID (número): ").strip()
    api_hash = input("TELEGRAM_API_HASH (texto): ").strip()

print("\nConectando a Telegram para generar tu String Session...")
print("Se te pedirá tu número de teléfono (incluyendo código de país, ej: +54911...)")
print("Telegram te enviará un código por mensaje (en la app) para validar el inicio de sesión.\n")

with TelegramClient(StringSession(), int(api_id), api_hash) as client:
    session_string = client.session.save()
    
    print("\n" + "="*50)
    print("¡SESIÓN GENERADA CON ÉXITO!")
    print("Copia el siguiente texto larguísimo y pégalo como una nueva variable en tu .env (o en GitHub Actions):")
    print("\nTELEGRAM_STRING_SESSION=" + session_string)
    print("\n" + "="*50)
    print("NOTA: Mantén este texto en secreto. Cualquiera que lo tenga puede acceder a tu cuenta de Telegram.")
    
print("\nPresiona Enter para salir...")
input()
