import time
import json
from google import genai
from pathlib import Path

def descubrir_modelos():
    print("\n" + "="*60)
    print(f"DESCUBRIDOR DE MODELOS IA | Health Check")
    print("="*60)

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
        print(f"Error al cargar configuración o API KEY: {e}")
        return []

    # 2. "TRAER" MODELOS DISPONIBLES DESDE LA API
    print("[*] Consultando lista de modelos disponibles en tu cuenta...")
    try:
        modelos_candidatos = []
        for m in client.models.list():
            # Atributo correcto en google-genai: supported_generation_methods
            # Usamos getattr por seguridad ante diferentes versiones de la SDK
            metodos = getattr(m, 'supported_generation_methods', [])
            if "gemini" in m.name.lower() and ("generateContent" in metodos or not metodos):
                modelos_candidatos.append(m.name)
        
        if not modelos_candidatos:
            print("[-] No se encontraron modelos Gemini disponibles.")
            return []
    except Exception as e:
        print(f"[-] Error al traer lista de modelos: {e}")
        return []

    modelos_vivos = []
    print(f"{'MODELO':<25} | {'ESTADO':<10} | {'LATENCIA':<10} | {'RESULTADO'}")
    print("-" * 75)

    for nombre_full in modelos_candidatos:
        start_time = time.time()
        try:
            response = client.models.generate_content(model=nombre_full, contents="ping")
            latencia = round(time.time() - start_time, 2)
            if response.text:
                m_display = nombre_full.replace("models/", "")
                print(f"{m_display:<25} | {'OK':<10} | {latencia:<10}s | {'Disponible'}")
                modelos_vivos.append({"modelo": nombre_full, "latencia": latencia})
        except Exception as e:
            err = str(e)
            status = "CUOTA" if "429" in err else "ERROR"
            m_display = nombre_full.replace("models/", "")
            print(f"{m_display:<25} | {status:<10} | {'N/A':<10} | {err[:25]}...")

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
    
    print("-" * 75)
    print(f"[OK] {len(lista_final)} modelos listos para el pipeline.\n")
    return lista_final

if __name__ == "__main__":
    descubrir_modelos()