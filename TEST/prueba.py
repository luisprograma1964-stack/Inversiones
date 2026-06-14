from google import genai
from pathlib import Path

# 1. LEER LA NUEVA KEY
ROOT_DIR = Path(__file__).parent.parent
API_KEY_PATH = ROOT_DIR / 'creds' / 'api_key.txt'

with open(API_KEY_PATH, 'r') as f:
    key = f.read().strip()

client = genai.Client(api_key=key)

try:
    # Intento directo con el modelo más básico y activo
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Hola, responde solo con la palabra OK si funcionas."
    )
    print(f"RESULTADO IA: {response.text}")
except Exception as e:
    print(f"LA LLAVE SIGUE FALLANDO: {e}")