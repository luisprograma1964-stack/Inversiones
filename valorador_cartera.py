"""
Paso 3.8: Valuador de Cartera y Rentabilidad Real.
Lee transacciones de activos y logs de caja, calcula tenencias netas,
costos promedios y valoriza el portafolio actual de cada propietario
escribiendo el consolidado en la hoja VALORACION_PORTAFOLIO.
"""
import time
from datetime import datetime
import pandas as pd
import config
import auth_google
import procesamiento
import logging_config

logger = logging_config.get_logger(__name__)

def ejecutar_valoracion():
    logger.info("="*60)
    logger.info(f"VALUACIÓN DE CARTERA | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("="*60)
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets.")
        return False
        
    try:
        ws_trans = sh.worksheet(config.WS_TRANSACCIONES)
        ws_tecnico = sh.worksheet(config.WS_ANALISIS_TECNICO)
        ws_caja = sh.worksheet(config.WS_CAJA_LIQUIDEZ)
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
        
        # Intentamos obtener la hoja de movimientos de caja
        try:
            ws_movs = sh.worksheet("MOVIMIENTOS_CAJA")
            df_movs = pd.DataFrame(ws_movs.get_all_records())
            df_movs.columns = [c.strip().upper() for c in df_movs.columns]
        except Exception:
            df_movs = pd.DataFrame()
            logger.warning("No se pudo cargar la hoja MOVIMIENTOS_CAJA.")

        # 1. Leer y limpiar datos
        df_trans = pd.DataFrame(ws_trans.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_trans.columns = [c.strip().upper() for c in df_trans.columns]
        
        df_tecnico = pd.DataFrame(ws_tecnico.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_tecnico.columns = [c.strip().upper() for c in df_tecnico.columns]
        
        df_caja = pd.DataFrame(ws_caja.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_caja.columns = [c.strip().upper() for c in df_caja.columns]

        # Normalizar y limpiar numéricos
        def clean_num(val):
            if pd.isna(val) or str(val).strip() == '': return 0.0
            val_str = str(val).strip()
            if val_str.startswith('='): return 0.0
            try:
                return float(val_str.replace(',', '.'))
            except Exception:
                return 0.0

        def fmt_sheets(val):
            if pd.isna(val) or str(val).strip() == "": return ""
            try:
                if isinstance(val, float):
                    return f"{val:.2f}".replace('.', ',')
                return str(val).replace('.', ',')
            except:
                return str(val)

        if not df_trans.empty:
            df_trans['CANTIDAD'] = df_trans['CANTIDAD'].apply(clean_num)
            df_trans['PRECIO_UNITARIO'] = df_trans['PRECIO_UNITARIO'].apply(clean_num)
            df_trans['COMISIÓN_TOTAL'] = df_trans['COMISIÓN_TOTAL'].apply(clean_num)
            df_trans['TOTAL_NETO'] = df_trans['TOTAL_NETO'].apply(clean_num)
            df_trans['PROPIETARIO'] = df_trans['PROPIETARIO'].astype(str).str.strip()
            df_trans['ACTIVO'] = df_trans['ACTIVO'].astype(str).str.strip().str.upper()
            df_trans['OPERACIÓN'] = df_trans['OPERACIÓN'].astype(str).str.strip().str.upper()
            df_trans['MONEDA'] = df_trans['MONEDA'].astype(str).str.strip().str.upper()
            df_trans['MONEDA'] = df_trans['MONEDA'].replace({'': 'ARS', 'PESOS': 'ARS', 'PESO': 'ARS', 'DOLARES': 'USD', 'DOLAR': 'USD'})

            # Calcular TOTAL_NETO programáticamente si está en 0 o contiene fórmula
            for idx, r in df_trans.iterrows():
                cant = r['CANTIDAD']
                precio = r['PRECIO_UNITARIO']
                comision = r['COMISIÓN_TOTAL']
                op = r['OPERACIÓN']
                tot_net = r['TOTAL_NETO']
                
                if tot_net == 0.0 or pd.isna(tot_net):
                    if 'COMPR' in op:
                        df_trans.at[idx, 'TOTAL_NETO'] = (cant * precio) + comision
                    elif 'VENT' in op:
                        df_trans.at[idx, 'TOTAL_NETO'] = (cant * precio) - comision
                    else:
                        df_trans.at[idx, 'TOTAL_NETO'] = 0.0

        # Limpiar precios del análisis técnico
        precios_actuales = {}
        ccl_prom = 1500.0
        if not df_tecnico.empty:
            df_tecnico['PRECIO_ACTUAL'] = df_tecnico['PRECIO_ACTUAL'].apply(clean_num)
            df_tecnico['TICKER_ID'] = df_tecnico['TICKER_ID'].astype(str).str.strip().str.upper()
            precios_actuales = df_tecnico.set_index('TICKER_ID')['PRECIO_ACTUAL'].to_dict()
            if 'CCL_IMPLICITO' in df_tecnico.columns:
                ccls = df_tecnico['CCL_IMPLICITO'].apply(clean_num)
                ccls = ccls[ccls > 500]
                if not ccls.empty:
                    ccl_prom = ccls.mean()

        # Limpiar saldos de caja
        saldos_caja = {}
        if not df_caja.empty:
            df_caja['SALDO'] = df_caja['SALDO'].apply(clean_num)
            df_caja['PROPIETARIO'] = df_caja['PROPIETARIO'].astype(str).str.strip()
            df_caja['MONEDA'] = df_caja['MONEDA'].astype(str).str.strip().str.upper()
            # Agrupar saldos de caja por (Propietario, Moneda)
            for _, r in df_caja.iterrows():
                prop = r['PROPIETARIO']
                mon = r['MONEDA']
                if mon in ['PESOS', 'PESO']: mon = 'ARS'
                elif mon in ['DOLARES', 'DOLAR']: mon = 'USD'
                saldo = r['SALDO']
                key = (prop, mon)
                saldos_caja[key] = saldos_caja.get(key, 0.0) + saldo

        # Limpiar movimientos de caja para aportes netos
        aportes_netos = {}
        if not df_movs.empty:
            df_movs['MONTO'] = df_movs['MONTO'].apply(clean_num)
            df_movs['PROPIETARIO'] = df_movs['PROPIETARIO'].astype(str).str.strip()
            df_movs['MONEDA'] = df_movs['MONEDA'].astype(str).str.strip().str.upper()
            df_movs['MONEDA'] = df_movs['MONEDA'].replace({'PESOS': 'ARS', 'PESO': 'ARS', 'DOLARES': 'USD', 'DOLAR': 'USD'})
            df_movs['MOVIMIENTO'] = df_movs['MOVIMIENTO'].astype(str).str.strip().str.upper()
            
            for _, r in df_movs.iterrows():
                prop = r['PROPIETARIO']
                mon = r['MONEDA']
                monto = r['MONTO']
                mov = r['MOVIMIENTO']
                key = (prop, mon)
                
                if mov in ['INGRESO', 'APORTE', '1', '1.0']:
                    aportes_netos[key] = aportes_netos.get(key, 0.0) + monto
                elif mov in ['EGRESO', 'RETIRO', '-1', '-1.0']:
                    aportes_netos[key] = aportes_netos.get(key, 0.0) - monto

        # 2. PROCESAR PORTAFOLIO POR PROPIETARIO
        filas_valoracion = []
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not df_trans.empty:
            # Agrupamos transacciones por Propietario y Moneda para evaluar
            propietarios = df_trans['PROPIETARIO'].unique()
            
            for prop in propietarios:
                df_prop = df_trans[df_trans['PROPIETARIO'] == prop]
                monedas = df_prop['MONEDA'].unique()
                
                for mon in monedas:
                    df_prop_mon = df_prop[df_prop['MONEDA'] == mon]
                    tickers = df_prop_mon['ACTIVO'].unique()
                    
                    valor_activos_total = 0.0
                    
                    # Evaluar cada ticker individual
                    for t in sorted(tickers):
                        # Ignorar nombres técnicos o vacíos
                        if not t or t == 'NAN' or t == 'CAJA':
                            continue
                            
                        df_t = df_prop_mon[df_prop_mon['ACTIVO'] == t]
                        
                        # Calcular cantidad neta
                        compras = df_t[df_t['OPERACIÓN'].str.contains('COMPR', na=False)]
                        ventas = df_t[df_t['OPERACIÓN'].str.contains('VENT', na=False)]
                        
                        cant_compras = compras['CANTIDAD'].sum()
                        cant_ventas = ventas['CANTIDAD'].sum()
                        cant_neta = cant_compras - cant_ventas
                        
                        if cant_neta <= 0:
                            continue  # No tiene posición actual
                            
                        # Costo Promedio Ponderado de las compras
                        total_gastado = compras['TOTAL_NETO'].sum()
                        costo_promedio = round(total_gastado / cant_compras, 2) if cant_compras > 0 else 0.0
                        
                        # Buscar precio actual en análisis técnico (viene en USD para activos extranjeros)
                        precio_actual_bruto = precios_actuales.get(t, 0.0)
                        
                        ratios = {"AAPL": 10, "TSLA": 15, "SPY": 20, "QQQ": 20, "MSFT": 30, "AMZN": 144, "GOOGL": 58, "META": 24, "AMD": 10, "NVDA": 24, "KO": 5, "MCD": 12, "DIS": 12, "MELI": 60}
                        ratio = ratios.get(t, 10) if precio_actual_bruto < 5000 else 1
                        
                        # El precio del Cedear en USD
                        precio_cedear_usd = precio_actual_bruto / ratio
                        
                        if mon == 'ARS':
                            precio_actual = (precio_actual_bruto * ccl_prom) / ratio if precio_actual_bruto < 5000 else precio_actual_bruto
                        else:
                            precio_actual = precio_cedear_usd
                            
                        if precio_actual == 0.0:
                            # Fallback al último precio registrado de transacciones
                            if not df_t.empty:
                                precio_actual = df_t.iloc[-1]['PRECIO_UNITARIO']
                                
                        valor_actual = cant_neta * precio_actual
                        valor_activos_total += valor_actual
                        
                        rent_nom = valor_actual - (cant_neta * costo_promedio)
                        rent_porc = (rent_nom / (cant_neta * costo_promedio)) * 100 if costo_promedio > 0 else 0.0
                        
                        filas_valoracion.append([
                            prop, t, fmt_sheets(cant_neta), fmt_sheets(round(costo_promedio, 2)), fmt_sheets(round(valor_actual, 2)),
                            "", fmt_sheets(round(rent_nom, 2)), f"{round(rent_porc, 2)}%".replace('.', ','), mon, ahora_str
                        ])
                        
                    # Añadir la fila -CASH- (efectivo actual)
                    efectivo_disp = saldos_caja.get((prop, mon), 0.0)
                    aportes_n = aportes_netos.get((prop, mon), 0.0)
                    
                    filas_valoracion.append([
                        prop, "-CASH-", "1", "1", fmt_sheets(round(efectivo_disp, 2)),
                        fmt_sheets(round(aportes_n, 2)), "0", "0,0%", mon, ahora_str
                    ])
                    
                    # Añadir la fila -TOTAL- (Portafolio Consolidado)
                    valor_total_portafolio = valor_activos_total + efectivo_disp
                    # Si no hay aportes netos registrados, asumimos que los aportes equivalen al efectivo actual para evitar errores
                    aportes_ref = aportes_n if aportes_n != 0.0 else valor_total_portafolio
                    
                    rent_total_nom = valor_total_portafolio - aportes_ref
                    rent_total_porc = (rent_total_nom / aportes_ref) * 100 if aportes_ref != 0.0 else 0.0
                    
                    filas_valoracion.append([
                        prop, "-TOTAL-", "", "", fmt_sheets(round(valor_total_portafolio, 2)),
                        fmt_sheets(round(aportes_ref, 2)), fmt_sheets(round(rent_total_nom, 2)), f"{round(rent_total_porc, 2)}%".replace('.', ','), mon, ahora_str
                    ])

        # 3. Guardar en la hoja VALORACION_PORTAFOLIO
        if filas_valoracion:
            ws_val = sh.worksheet("VALORACION_PORTAFOLIO")
            ws_val.clear()
            headers_val = ['PROPIETARIO', 'TICKER', 'CANTIDAD', 'COSTO_PROMEDIO', 'VALOR_ACTUAL', 'APORTES_NETOS', 'RENTABILIDAD_NOMINAL', 'RENTABILIDAD_PORCENTAJE', 'MONEDA', 'ULTIMA_ACTUALIZACION']
            ws_val.update(range_name='A1', values=[headers_val] + filas_valoracion, value_input_option='USER_ENTERED')
            
            resumen = f"Valuación completada. Se grabaron {len(filas_valoracion)} registros de cartera."
            logger.info(resumen)
            procesamiento.registrar_log(ws_log, "INFO", resumen, "valorador_cartera")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen, nombre_proceso="valorador_cartera", tiempo_ejecucion=duracion)
            print(f"[OK] {resumen}")
            return True
        else:
            logger.warning("No se encontraron transacciones activas para valorizar.")
            return True
            
    except Exception as e:
        error_msg = f"Error en valorador de cartera: {e}"
        logger.exception(error_msg)
        try:
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min" if 't_inicio' in locals() else ""
            procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "ERROR", error_msg, "valorador_cartera")
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], nombre_proceso="valorador_cartera", tiempo_ejecucion=duracion)
        except:
            pass
        print(f"[ERROR] {error_msg}")
        return False

if __name__ == "__main__":
    ejecutar_valoracion()
