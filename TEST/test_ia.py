import time
import json
from google import genai
from pathlib import Path
import logging_config

logger = logging_config.get_logger(__name__)

def descubrir_modelos():
    logger.info("\n" + "="*60)
    logger.info(f"DESCUBRIDOR DE MODELOS IA | Health Check")
    logger.info("="*60)

    # 1. CARGAR TU CLAVE
    ROOT_DIR = Path(__file__).parent.parent
    API_KEY_PATH = ROOT_DIR / 'creds' / 'api_key.txt'
    CONFIG_FILE = ROOT_DIR / 'ia_params.json'

    try:
        with open(API_KEY_PATH, 'r') as f:
            key = f.read().strip()
        client = genai.Client(api_key=key)
        
        # Cargamos cuál es tu modelo preferido para darle prioridad
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            pref = config.get("modelo_preferido")
    except Exception as e:
        logger.exception(f"Error al cargar configuración o API KEY: {e}")
        return []

    # 2. "TRAER" MODELOS DISPONIBLES DESDE LA API
    logger.info("Consultando lista de modelos disponibles en tu cuenta...")
    try:
        modelos_candidatos = []
        for m in client.models.list():
            metodos = getattr(m, 'supported_generation_methods', [])
            name_lower = m.name.lower()
            
            # Filtro estricto: debe ser gemini, apto para generación y no ser de tuning, robótica o experimental interno
            is_valid_gemini = "gemini" in name_lower and ("generateContent" in metodos or not metodos)
            no_experimental = not any(x in name_lower for x in ["tuning", "robotics", "dolly", "bison", "gecko"])
            is_standard = any(x in name_lower for x in ["gemini-1.5", "gemini-2.0", "gemini-2.5", "gemini-3.0", "gemini-3.5", "gemini-flash", "gemini-pro"])
            
            if is_valid_gemini and no_experimental and is_standard:
                model_clean = m.name.replace("models/", "")
                modelos_candidatos.append(model_clean)
        
        if not modelos_candidatos:
            logger.warning("No se encontraron modelos Gemini disponibles.")
            return []
    except Exception as e:
        logger.exception(f"Error al traer lista de modelos: {e}")
        return []

    modelos_vivos = []
    logger.info(f"{'MODELO':<25} | {'ESTADO':<10} | {'LATENCIA':<10} | {'RESULTADO'}")
    logger.info("-" * 75)

    for nombre_full in modelos_candidatos:
        start_time = time.time()
        try:
            # Consultamos sin el prefijo 'models/'
            response = client.models.generate_content(model=nombre_full, contents="ping")
            latencia = round(time.time() - start_time, 2)
            if response.text:
                logger.info(f"{nombre_full:<25} | {'OK':<10} | {latencia:<10}s | {'Disponible'}")
                modelos_vivos.append({"modelo": nombre_full, "latencia": latencia})
        except Exception as e:
            err = str(e)
            # Si es un error de cuota o temporal del servidor, el modelo es válido pero está cargado. Lo conservamos.
            if any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                logger.info(f"{nombre_full:<25} | {'CUOTA/BUSY':<10} | {'10.0':<10}s | {'Disponible (Penalización latencia)'}")
                modelos_vivos.append({"modelo": nombre_full, "latencia": 10.0})
            else:
                logger.warning(f"{nombre_full:<25} | {'ERROR':<10} | {'N/A':<10} | {err[:25]}...")

    # Ordenar por latencia (el más rápido primero)
    modelos_vivos.sort(key=lambda x: x['latencia'])
    lista_final = [m['modelo'] for m in modelos_vivos]
    
    # 3. PRIORIZAR EL MODELO PREFERIDO
    # Si el preferido está vivo, lo movemos al principio de la lista
    if pref and pref in lista_final:
        lista_final.remove(pref)
        lista_final.insert(0, pref)

    # Guardar en un JSON para que ia_utils pueda leerlo
    output_path = Path(__file__).parent.parent / "modelos_activos.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=4)
    
    logger.info("-" * 75)
    logger.info(f"[OK] {len(lista_final)} modelos listos para el pipeline.\n")
    return lista_final

if __name__ == "__main__":
    descubrir_modelos()