import sys
import os
import pandas as pd
import logging
from datetime import datetime
import math

# Configurar logging (terminal)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoTraderIA")

# Importar configuraciones locales
import config
import auth_google
import procesamiento

def log_to_sheets(sh, level, msg):
    try:
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        procesamiento.registrar_log(ws_log, level, msg, origen="AutoTrader")
    except Exception as e:
        logger.error(f"No se pudo registrar log en Sheets: {e}")

def limpiar_numero(val):
    try:
        if isinstance(val, str):
            val = val.replace('.', '').replace(',', '.')
        return float(val)
    except:
        return 0.0

def ejecutar_auto_trader():
    logger.info("--- INICIANDO AUTO-TRADER IA ---")
    sh = auth_google.conectar()
    if not sh:
        logger.critical("No se pudo conectar a Google Sheets.")
        return False
        
    try:
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Auto-Trader simulando operaciones...", nombre_proceso="auto_trader_ia")
        
        log_to_sheets(sh, "INFO", "Iniciando Auto-Trader IA para carteras de simulación...")
        
        # 1. Leer Datos
        df_carteras = pd.DataFrame(sh.worksheet(config.WS_CARTERAS).get_all_records())
        df_matriz = pd.DataFrame(sh.worksheet(config.WS_MATRIZ_RECOMENDACIONES).get_all_records())
        df_tecnico = pd.DataFrame(sh.worksheet(config.WS_ANALISIS_TECNICO).get_all_records())
        df_caja = pd.DataFrame(sh.worksheet("CAJA_LIQUIDEZ").get_all_records())
        
        try:
            df_val = pd.DataFrame(sh.worksheet("VALORACION_PORTAFOLIO").get_all_records())
        except:
            df_val = pd.DataFrame()
            
        # 2. Filtrar Carteras de Simulacion
        fondos_ia = df_carteras[df_carteras['TIPO_CARTERA'].astype(str).str.upper() == 'SIMULACION'].to_dict('records')
        
        if not fondos_ia:
            log_to_sheets(sh, "INFO", "No se encontraron carteras de simulación para operar.")
            return True
            
        # Extraer precios actuales
        precios_actuales = {}
        if not df_tecnico.empty:
            for _, row in df_tecnico.iterrows():
                tk = str(row.get('TICKER_ID', '')).strip().upper()
                px = limpiar_numero(row.get('PRECIO_ACTUAL', 0))
                if tk and px > 0:
                    precios_actuales[tk] = px
                    
        nuevas_transacciones = []
        nuevos_movimientos_caja = []
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. Iterar por cada Fondo IA
        for fondo in fondos_ia:
            cartera_id = str(fondo.get('CARTERA_ID', '')).strip().upper()
            perfil = str(fondo.get('PERFIL_RIESGO', '')).strip().upper()
            comision_pct = float(fondo.get('COMISION_BROKER', 0.0)) / 100.0
            liq_target = float(fondo.get('PORCENTAJE_LIQUIDEZ', 0.10))
            
            # Obtener saldo de caja (ars)
            df_mi_caja = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'ARS')]
            saldo_caja = df_mi_caja['SALDO'].apply(limpiar_numero).sum() if not df_mi_caja.empty else 0.0
            
            # Obtener valuacion activos para sacar Patrimonio Total
            mi_val = 0.0
            mis_activos = {}
            if not df_val.empty:
                df_mi_val = df_val[df_val['PROPIETARIO'].astype(str).str.upper() == cartera_id]
                for _, r in df_mi_val.iterrows():
                    tk = str(r.get('TICKER', '')).strip().upper()
                    if tk not in ["-TOTAL-", "-CASH-"]:
                        qty = limpiar_numero(r.get('CANTIDAD', 0))
                        val = limpiar_numero(r.get('VALOR_ACTUAL', 0))
                        if qty > 0:
                            mis_activos[tk] = qty
                            mi_val += val
                            
            patrimonio_total = saldo_caja + mi_val
            caja_minima = patrimonio_total * liq_target
            
            # Filtrar matriz para este perfil
            señales = df_matriz[df_matriz['PERFIL'].astype(str).str.upper() == perfil]
            
            compras = señales[señales['VEREDICTO_IA'].astype(str).str.upper() == 'COMPRAR']['TICKER'].tolist()
            ventas = señales[señales['VEREDICTO_IA'].astype(str).str.upper() == 'VENDER']['TICKER'].tolist()
            
            log_to_sheets(sh, "INFO", f"Fondo {cartera_id}: Saldo=${saldo_caja:,.2f} | Caja Mín=${caja_minima:,.2f} | Compras={len(compras)} | Ventas={len(ventas)}")
            
            # --- EJECUTAR VENTAS ---
            for tk in ventas:
                tk = str(tk).strip().upper()
                if tk in mis_activos and mis_activos[tk] > 0:
                    qty = mis_activos[tk]
                    px = precios_actuales.get(tk, 0)
                    if px > 0:
                        bruto = qty * px
                        comision = bruto * comision_pct
                        neto = bruto - comision
                        
                        nuevas_transacciones.append({
                            'FECHA': hoy,
                            'PROPIETARIO': cartera_id,
                            'BROKER_CUENTA': 'AUTO_TRADER_IA',
                            'ACTIVO': tk,
                            'ESPECIE': 'CEDEAR/ACCION',
                            'OPERACIÓN': 'VENTA',
                            'CANTIDAD': qty,
                            'PRECIO_UNITARIO': px,
                            'MONEDA': 'ARS',
                            'COMISIÓN_TOTAL': comision,
                            'OBSERVACIONES': 'Venta dictaminada por IA',
                            'TOTAL_NETO': neto,
                            'PRECIO_MERCADO_REF': px
                        })
                        saldo_caja += neto
                        log_to_sheets(sh, "INFO", f"[{cartera_id}] VENTA EJECUTADA: {qty} {tk} a ${px}. Neto: ${neto:,.2f}")
                        
            # --- EJECUTAR COMPRAS ---
            efectivo_libre = saldo_caja - caja_minima
            if efectivo_libre > 0 and compras:
                compras_validas = [tk for tk in compras if precios_actuales.get(str(tk).strip().upper(), 0) > 0]
                if compras_validas:
                    cash_per_asset = efectivo_libre / len(compras_validas)
                    
                    for tk in compras_validas:
                        tk = str(tk).strip().upper()
                        px = precios_actuales[tk]
                        
                        px_con_comision = px * (1 + comision_pct)
                        qty = math.floor(cash_per_asset / px_con_comision)
                        
                        if qty > 0:
                            bruto = qty * px
                            comision = bruto * comision_pct
                            neto = bruto + comision 
                            
                            nuevas_transacciones.append({
                                'FECHA': hoy,
                                'PROPIETARIO': cartera_id,
                                'BROKER_CUENTA': 'AUTO_TRADER_IA',
                                'ACTIVO': tk,
                                'ESPECIE': 'CEDEAR/ACCION',
                                'OPERACIÓN': 'COMPRA',
                                'CANTIDAD': qty,
                                'PRECIO_UNITARIO': px,
                                'MONEDA': 'ARS',
                                'COMISIÓN_TOTAL': comision,
                                'OBSERVACIONES': 'Compra dictaminada por IA',
                                'TOTAL_NETO': neto,
                                'PRECIO_MERCADO_REF': px
                            })
                            saldo_caja -= neto
                            log_to_sheets(sh, "INFO", f"[{cartera_id}] COMPRA EJECUTADA: {qty} {tk} a ${px}. Costo Total: ${neto:,.2f}")
            elif compras:
                log_to_sheets(sh, "INFO", f"[{cartera_id}] OMITIENDO COMPRAS: Efectivo libre insuficiente (Caja Mínima Protegida).")
                
            nuevos_movimientos_caja.append({
                'PROPIETARIO': cartera_id,
                'MONEDA': 'ARS',
                'TIPO_CUENTA': 'Comitente',
                'SALDO': saldo_caja,
                'ULTIMA_ACTUALIZACION': hoy
            })
            
        # 4. GUARDAR EN SHEETS
        if nuevas_transacciones:
            ws_trans = sh.worksheet("TRANSACCIONES")
            trans_data = ws_trans.get_all_records()
            df_trans = pd.DataFrame(trans_data)
            
            last_id = 0
            if not df_trans.empty and 'ID' in df_trans.columns:
                try:
                    last_id = int(df_trans['ID'].max())
                except:
                    pass
            for t in nuevas_transacciones:
                last_id += 1
                t['ID'] = last_id
                
            cols_trans = ['ID', 'FECHA', 'PROPIETARIO', 'BROKER_CUENTA', 'ACTIVO', 'ESPECIE', 'OPERACIÓN', 'CANTIDAD', 'PRECIO_UNITARIO', 'MONEDA', 'COMISIÓN_TOTAL', 'OBSERVACIONES', 'TOTAL_NETO', 'PRECIO_MERCADO_REF']
            df_nuevas_trans = pd.DataFrame(nuevas_transacciones)
            for c in cols_trans:
                if c not in df_nuevas_trans.columns:
                    df_nuevas_trans[c] = ""
            df_nuevas_trans = df_nuevas_trans[cols_trans]
            
            if df_trans.empty:
                df_final_trans = df_nuevas_trans
            else:
                df_final_trans = pd.concat([df_trans, df_nuevas_trans], ignore_index=True)
                
            ws_trans.clear()
            ws_trans.update([df_final_trans.columns.values.tolist()] + df_final_trans.values.tolist())
            log_to_sheets(sh, "INFO", f"Auto-Trader: {len(nuevas_transacciones)} transacciones guardadas.")
            
        if nuevos_movimientos_caja:
            ws_caja = sh.worksheet("CAJA_LIQUIDEZ")
            df_caja_old = pd.DataFrame(ws_caja.get_all_records())
            df_nuevos_caja = pd.DataFrame(nuevos_movimientos_caja)
            
            if not df_caja_old.empty:
                for _, row in df_nuevos_caja.iterrows():
                    prop = row['PROPIETARIO']
                    mon = row['MONEDA']
                    idx = df_caja_old.index[(df_caja_old['PROPIETARIO'].astype(str).str.upper() == str(prop).upper()) & (df_caja_old['MONEDA'].astype(str).str.upper() == str(mon).upper())]
                    if not idx.empty:
                        df_caja_old.loc[idx, 'SALDO'] = row['SALDO']
                        df_caja_old.loc[idx, 'ULTIMA_ACTUALIZACION'] = row['ULTIMA_ACTUALIZACION']
                    else:
                        df_caja_old = pd.concat([df_caja_old, pd.DataFrame([row])], ignore_index=True)
                df_final_caja = df_caja_old
            else:
                df_final_caja = df_nuevos_caja
                
            ws_caja.clear()
            ws_caja.update([df_final_caja.columns.values.tolist()] + df_final_caja.values.tolist())
            
        procesamiento.actualizar_estado_proceso(ws_status, "COMPLETADO", f"Operaciones simuladas ejecutadas exitosamente.", nombre_proceso="auto_trader_ia")
        log_to_sheets(sh, "INFO", "Auto-Trader finalizó exitosamente.")
        return True
        
    except Exception as e:
        logger.error(f"Error en Auto-Trader: {e}")
        try:
            ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", f"Fallo Auto-Trader: {str(e)[:100]}", nombre_proceso="auto_trader_ia")
            log_to_sheets(sh, "ERROR", f"Fallo crítico en Auto-Trader: {e}")
        except: pass
        return False

if __name__ == '__main__':
    ejecutar_auto_trader()
