import sys
from pathlib import Path
# Añadir la ruta raíz para poder importar los módulos del proyecto
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import re
import unicodedata
from datetime import datetime
import pandas as pd
import auth_google
import config
import ia_utils

def normalizar_texto(texto):
    if not texto:
        return ""
    # Convertir a mayúsculas, remover acentos y caracteres especiales
    texto = str(texto).strip().upper()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    # Reemplazar caracteres no alfanuméricos comunes por espacios
    texto = re.sub(r'[^A-Z0-9]', ' ', texto)
    # Reducir múltiples espacios a uno
    return ' '.join(texto.split())

def buscar_ultimo_json_auditable():
    """Busca el archivo req_*.json más reciente en la carpeta IA_LOGS."""
    log_dir = Path("IA_LOGS")
    if not log_dir.exists():
        return None
    
    archivos = list(log_dir.glob("req_*.json"))
    if not archivos:
        return None
    
    # Ordenar por fecha de última modificación (el más nuevo primero)
    archivos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return archivos[0]

def ejecutar_homologacion():
    print("=" * 60)
    print("[HOMOLOGADOR] INICIANDO AUDITORIA Y CONTROL DE DATOS DE IA")
    print("=" * 60)
    
    # 1. Buscar último JSON generado por el decisor
    ultimo_json_path = buscar_ultimo_json_auditable()
    if ultimo_json_path:
        print(f"[*] Ultimo archivo JSON detectado: {ultimo_json_path}")
        print(f"[*] Fecha de modificacion: {datetime.fromtimestamp(ultimo_json_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("[WARN] No se detecto ningun archivo req_*.json en la carpeta IA_LOGS.")
        print("[!] Se realizara una simulacion de prompt en caliente en su lugar.\n")

    # 2. Conexión a Google Sheets
    print("[*] Conectando a Google Sheets...")
    sh = auth_google.conectar()
    if not sh:
        print("[FAIL] No se pudo conectar a Google Sheets.")
        return
    print("[OK] Conexion establecida con exito.\n")
    
    # 3. Cargar Hojas de Cálculo Reales en DataFrames
    print("[*] Leyendo datos vigentes en las hojas...")
    try:
        df_tecnico = pd.DataFrame(sh.worksheet(config.WS_ANALISIS_TECNICO).get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_tecnico.columns = [c.strip().upper() for c in df_tecnico.columns]
        
        # En la hoja VALORACION_PORTAFOLIO el nombre no está en config, definimos constante local limpia
        WS_VALORACION = "VALORACION_PORTAFOLIO"
        df_valoracion = pd.DataFrame(sh.worksheet(WS_VALORACION).get_all_records())
        df_valoracion.columns = [c.strip().upper() for c in df_valoracion.columns]
        
        raw_noticias = sh.worksheet(config.WS_NOTICIAS_SISTEMA).get_all_records()
        df_noticias = pd.DataFrame(raw_noticias)
        df_noticias.columns = [c.strip().upper() for c in df_noticias.columns]
        
        # Ordenamos las noticias cronológicamente por fecha igual que en la lógica de producción (ia_utils)
        df_noticias['FECHA'] = pd.to_datetime(df_noticias['FECHA'], errors='coerce')
        df_noticias = df_noticias.sort_values('FECHA')
        
        df_mercado = pd.DataFrame(sh.worksheet(config.WS_VARIABLES_MERCADO).get_all_records())
        df_mercado.columns = [c.strip().upper() for c in df_mercado.columns]
        
        df_caja = pd.DataFrame(sh.worksheet(config.WS_CAJA_LIQUIDEZ).get_all_records())
        df_caja.columns = [c.strip().upper() for c in df_caja.columns]
        
        df_usuarios = pd.DataFrame(sh.worksheet(config.WS_CONFIG_IA_USUARIO).get_all_records())
        df_usuarios.columns = [c.strip().upper() for c in df_usuarios.columns]
        
        print("[OK] Hojas leidas con exito.")
    except Exception as e:
        print(f"[FAIL] Error leyendo hojas de Sheets: {e}")
        return

    inconsistencias = 0
    verificaciones = 0

    # 4. Caso A: Auditar el último JSON real contra las tablas
    if ultimo_json_path:
        print("\n[*] Iniciando auditoria del ultimo JSON real...")
        try:
            with open(ultimo_json_path, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
                
            prompt_final = audit_data.get("prompt_final_enviado", {})
            ticker = prompt_final.get("contexto_activo", {}).get("ticker")
            
            if not ticker:
                print("[FAIL] El archivo JSON no tiene un ticker valido en 'contexto_activo'.")
                return
                
            print(f"[*] Auditando Ticker del JSON: {ticker}")
            
            # Buscar fila correspondiente en Sheets
            df_fila_ticker = df_tecnico[df_tecnico['TICKER_ID'] == str(ticker).upper()]
            if df_fila_ticker.empty:
                print(f"  [DISCREPANCIA] El Ticker '{ticker}' del JSON no existe en la hoja ANALISIS_TECNICO.")
                inconsistencias += 1
            else:
                row_sheet = df_fila_ticker.iloc[0]
                
                # 4.1 Validar Indicadores Técnicos
                prompt_tecnico = prompt_final.get("indicadores_tecnicos", {})
                for campo in ia_utils.CAMPO_TECNICO:
                    verificaciones += 1
                    val_sheet = str(row_sheet.get(campo, '')).strip()
                    val_json = str(prompt_tecnico.get(campo, '')).strip()
                    
                    if val_sheet != val_json:
                        print(f"  [DISCREPANCIA] Campo Tecnico '{campo}': Sheets '{val_sheet}' vs JSON '{val_json}'")
                        inconsistencias += 1
                        
                # 4.2 Validar Noticias Específicas
                prompt_noticias = prompt_final.get("contexto_noticias", {}).get("especificas", [])
                db_noticias_ticker = df_noticias[df_noticias['TICKER_ID'] == str(ticker).upper()].tail(5)
                
                if len(prompt_noticias) != len(db_noticias_ticker):
                    print(f"  [DISCREPANCIA] Cantidad de Noticias: Sheets {len(db_noticias_ticker)} vs JSON {len(prompt_noticias)}")
                    inconsistencias += 1
                else:
                    titulares_sheet = set(normalizar_texto(t) for t in db_noticias_ticker['TITULAR'])
                    titulares_json = set(normalizar_texto(n.get('TITULAR', '')) for n in prompt_noticias)
                    diff = titulares_sheet - titulares_json
                    if diff:
                        print(f"  [DISCREPANCIA] Noticias no coincidentes en JSON para {ticker}: {diff}")
                        inconsistencias += 1

                # 4.3 Validar Contexto Financiero
                prompt_val = prompt_final.get("contexto_financiero", {}).get("valoracion_cartera_propietarios", [])
                if len(prompt_val) != len(df_valoracion):
                    print(f"  [DISCREPANCIA] Registros de Valoracion en Cartera: Sheets {len(df_valoracion)} vs JSON {len(prompt_val)}")
                    inconsistencias += 1
                    
                prompt_caja = prompt_final.get("contexto_financiero", {}).get("saldos_caja_disponibles", [])
                if len(prompt_caja) != len(df_caja):
                    print(f"  [DISCREPANCIA] Registros de Saldos Caja: Sheets {len(df_caja)} vs JSON {len(prompt_caja)}")
                    inconsistencias += 1

        except Exception as ex:
            print(f"[FAIL] Error leyendo o procesando JSON de auditoria: {ex}")
            inconsistencias += 1

    # 5. Caso B: Simular mapeo completo en caliente para todos los activos
    else:
        print("\n[*] Iniciando simulacion completa en caliente para todos los tickers...")
        # Preparación de variables de control del decisor para simulación
        dolar_mep = 1.0
        if not df_mercado.empty:
            mask_mep = df_mercado['DATO'].astype(str).str.contains('MEP', case=False, na=False)
            if any(mask_mep):
                try:
                    dolar_mep = float(str(df_mercado[mask_mep]['VALOR_PROM'].iloc[0]).replace(',', '.'))
                except Exception:
                    dolar_mep = 1.0
                    
        contexto_financiero = {
            "variables_market": df_mercado.to_dict('records') if not df_mercado.empty else [],
            "saldos_caja_disponibles": df_caja.to_dict('records') if not df_caja.empty else [],
            "valoracion_cartera_propietarios": df_valoracion.to_dict('records') if not df_valoracion.empty else [],
            "referencia_dolar_mep": dolar_mep
        }
        
        perfiles = [str(u.get('Perfil_Riesgo', '')).strip() for u in df_usuarios.to_dict('records') if u.get('Perfil_Riesgo')]
        
        print(f"[*] Se simularan {len(df_tecnico)} tickers del analisis tecnico...")
        for idx, row in df_tecnico.iterrows():
            ticker = row.get('TICKER_ID')
            if not ticker:
                continue
                
            print(f"--- Evaluando Ticker: {ticker} ---")
            noticias_ctx = ia_utils.obtener_noticias_recientes(sh, ticker)
            cuerpo_json_str = ia_utils.crear_prompt(
                row,
                perfiles,
                "Instrucciones de prueba",
                noticias_contexto=noticias_ctx,
                financiero_contexto=contexto_financiero
            )
            
            try:
                prompt_data = json.loads(cuerpo_json_str)
            except Exception as ex:
                print(f"  [FAIL] JSON del prompt malformado para {ticker}: {ex}")
                inconsistencias += 1
                continue
                
            # Validar campos técnicos
            prompt_tecnico = prompt_data.get("indicadores_tecnicos", {})
            for campo in ia_utils.CAMPO_TECNICO:
                verificaciones += 1
                valor_sheet = row.get(campo, '')
                valor_prompt = prompt_tecnico.get(campo, '')
                
                if str(valor_sheet).strip() != str(valor_prompt).strip():
                    print(f"  [DISCREPANCIA] Campo Tecnico '{campo}': Sheets '{valor_sheet}' vs Prompt '{valor_prompt}'")
                    inconsistencias += 1

    print("\n" + "="*60)
    print("[RESULTADO] RESULTADO DE LA AUDITORIA DE HOMOLOGACION:")
    if ultimo_json_path:
        print(f"   - Archivo auditado: {ultimo_json_path.name}")
        print(f"   - Verificaciones realizadas: {verificaciones}")
    else:
        print(f"   - Verificaciones realizadas en simulacion: {verificaciones}")
        
    if inconsistencias == 0:
        print("   - [STATUS] EXCELENTE (Integridad 100%). Los datos coinciden perfectamente entre Sheets y el JSON/Prompt.")
    else:
        print(f"   - [STATUS] INCONSISTENTE. Se detectaron {inconsistencias} discrepancias de datos.")
        print("     Por favor revisa el log superior para corregir descalces o re-ejecutar el pipeline.")
    print("=" * 60)

if __name__ == "__main__":
    ejecutar_homologacion()
