import requests
import auth_google
import config

def enviar_mensaje_telegram(mensaje, destinatario="DEFAULT"):
    """
    Envía un mensaje de texto formateado en HTML a un canal de Telegram.
    Lee el token y chat_id en tiempo de ejecución desde la hoja CONFIG_IA_GENERAL.
    Soporta destinatario="VICKY" para enviarlo al chat personal de Vicky.
    """
    try:
        sh = auth_google.conectar()
        if not sh:
            return False
            
        ws = sh.worksheet(config.WS_CONFIG_IA_GENERAL)
        data = ws.get_all_records()
        if not data:
            return False
            
        row = data[0]
        token = str(row.get("TELEGRAM_TOKEN", "")).strip()
        
        if destinatario == "VICKY":
            chat_id = str(row.get("TELEGRAM_CHAT_ID_VICKY", "")).strip()
        else:
            chat_id = str(row.get("TELEGRAM_CHAT_ID", "")).strip()
        
        # Filtro de credenciales válidas
        if not token or not chat_id or token == "" or chat_id == "" or "ERROR" in token:
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML"
        }
        
        # Timeout de 8s para no trancar la ejecución de fondo del pipeline si hay mala red
        response = requests.post(url, json=payload, timeout=8)
        return response.status_code == 200
    except Exception as e:
        # Fallo silencioso por diseño para no romper ejecuciones críticas
        print(f"[-] Telegram omitido o con error: {e}")
        return False

if __name__ == "__main__":
    # Prueba de concepto
    enviar_mensaje_telegram("🚀 Prueba de conexión exitosa desde el Motor de Inversiones.")
