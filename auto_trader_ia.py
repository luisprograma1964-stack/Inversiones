import sys
import os
import pandas as pd
import logging
from datetime import datetime
import math
import time

# Configurar logging (terminal)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoTraderIA")

# Importar configuraciones locales
import config
import auth_google
import procesamiento
import notificador_telegram

def limpiar_numero(val):
    try:
        if isinstance(val, str):
            val = val.replace('.', '').replace(',', '.')
        return float(val)
    except:
        return 0.0

def ejecutar_auto_trader():
    t_inicio = time.time()
    logger.info("--- INICIANDO AUTO-TRADER IA ---")
    sh = auth_google.conectar()
    if not sh:
        logger.critical("No se pudo conectar a Google Sheets.")
        return False
        
    resumen_telegram = ["🤖 *Reporte Auto-Trader IA*"]
    
    try:
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Auto-Trader simulando operaciones...", nombre_proceso="auto_trader_ia")
        
        # 1. Leer Datos
        df_carteras = pd.DataFrame(sh.worksheet(config.WS_CARTERAS).get_all_records())
        df_matriz = pd.DataFrame(sh.worksheet(config.WS_MATRIZ_RECOMENDACIONES).get_all_records())
        df_tecnico = pd.DataFrame(sh.worksheet(config.WS_ANALISIS_TECNICO).get_all_records())
        df_caja = pd.DataFrame(sh.worksheet("CAJA_LIQUIDEZ").get_all_records())
        
        try:
            df_maestro = pd.DataFrame(sh.worksheet(config.WS_MAESTRO_ACTIVOS).get_all_records())
        except:
            df_maestro = pd.DataFrame()
            
        try:
            df_historial = pd.DataFrame(sh.worksheet("HISTORIAL_VEREDICTOS").get_all_records())
            df_historial.columns = [c.strip().upper() for c in df_historial.columns]
        except:
            df_historial = pd.DataFrame()
        
        try:
            df_val = pd.DataFrame(sh.worksheet("VALORACION_PORTAFOLIO").get_all_records())
        except:
            df_val = pd.DataFrame()
            
        # Calcular CCL Promedio para evaluar Brecha
        if 'CCL_IMPLICITO' in df_tecnico.columns:
            # Reemplazar vacíos con 0 y forzar a numérico
            ccls = pd.to_numeric(df_tecnico['CCL_IMPLICITO'], errors='coerce').fillna(0)
            ccls_validos = ccls[ccls > 0]
            ccl_promedio = ccls_validos.mean() if not ccls_validos.empty else 1500.0
        else:
            ccl_promedio = 1500.0
            
        # 2. Filtrar Carteras de Simulacion
        fondos_ia = df_carteras[(df_carteras['TIPO_CARTERA'].astype(str).str.upper() == 'SIMULACION') & (df_carteras['CARTERA_ID'].astype(str).str.upper().str.startswith('FONDO_IA_'))].to_dict('records')
        
        if not fondos_ia:
            resumen_telegram.append("⚠️ No se encontraron carteras de simulación activas.")
            notificador_telegram.enviar_mensaje_telegram("\n".join(resumen_telegram))
            return True
            
        # Extraer precios e informacion actual
        info_activos = {}
        if not df_tecnico.empty:
            for _, row in df_tecnico.iterrows():
                tk = str(row.get('TICKER_ID', '')).strip().upper()
                px = limpiar_numero(row.get('PRECIO_ACTUAL', 0))
                ccl = limpiar_numero(row.get('CCL_IMPLICITO', 1500))
                if ccl == 0: ccl = 1500
                if tk and px > 0:
                    moneda = 'ARS'
                    if not df_maestro.empty:
                        m_row = df_maestro[df_maestro['TICKER_ID'].astype(str).str.upper() == tk]
                        if not m_row.empty:
                            moneda = str(m_row.iloc[0].get('MONEDA_COTIZACION', 'ARS')).strip().upper()
                    
                    razon = ""
                    if not df_historial.empty and 'TICKER' in df_historial.columns:
                        h_row = df_historial[df_historial['TICKER'].astype(str).str.upper() == tk]
                        if not h_row.empty:
                            razon = str(h_row.iloc[-1].get('RECOMENDACION_DETALLE', '')).strip()
                            if not razon:
                                razon = str(h_row.iloc[-1].get('SENTIMIENTO_IA', '')).strip()
                            razon = razon.replace('<', '').replace('>', '').replace('&', 'and')
                            if len(razon) > 100:
                                razon = razon[:97] + "..."
                                
                    info_activos[tk] = {'precio': px, 'ccl': ccl, 'moneda': moneda, 'razon': razon}
                    
        nuevas_transacciones = []
        nuevos_movimientos_caja = []
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        total_compras = 0
        total_ventas = 0
        
        # 3. Iterar por cada Fondo IA
        for fondo in fondos_ia:
            cartera_id = str(fondo.get('CARTERA_ID', '')).strip().upper()
            perfil = str(fondo.get('PERFIL_RIESGO', '')).strip().upper()
            comision_pct = float(fondo.get('COMISION_BROKER', 0.0)) / 100.0
            liq_target = float(fondo.get('PORCENTAJE_LIQUIDEZ', 0.10))
            
            resumen_fondo = [f"\n💼 *{cartera_id}* ({perfil})"]
            
            # Obtener saldo de caja (ars y usd)
            df_mi_caja_ars = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'ARS')]
            saldo_caja_ars = df_mi_caja_ars['SALDO'].apply(limpiar_numero).sum() if not df_mi_caja_ars.empty else 0.0
            
            df_mi_caja_usd = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'USD')]
            saldo_caja_usd = df_mi_caja_usd['SALDO'].apply(limpiar_numero).sum() if not df_mi_caja_usd.empty else 0.0
            
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
                            
            patrimonio_total = saldo_caja_ars + (saldo_caja_usd * 1500) + mi_val
            caja_minima = patrimonio_total * liq_target
            
            # Filtrar matriz para este perfil
            señales = df_matriz[df_matriz['PERFIL'].astype(str).str.upper() == perfil]
            compras = señales[señales['VEREDICTO_IA'].astype(str).str.upper() == 'COMPRAR']['TICKER'].tolist()
            ventas = señales[señales['VEREDICTO_IA'].astype(str).str.upper() == 'VENDER']['TICKER'].tolist()
            
            op_ejecutadas = 0
            
            # --- EJECUTAR VENTAS ---
            for tk in ventas:
                tk = str(tk).strip().upper()
                if tk in mis_activos and mis_activos[tk] > 0:
                    qty = mis_activos[tk]
                    info = info_activos.get(tk, {})
                    if info:
                        px_usd_underlying = info['precio']
                        ccl = info['ccl']
                        razon = info['razon']
                        
                        ratios = {"AAPL": 10, "TSLA": 15, "SPY": 20, "QQQ": 20, "MSFT": 30, "AMZN": 144, "GOOGL": 58, "META": 24, "AMD": 10, "NVDA": 24, "KO": 5, "MCD": 12, "DIS": 12, "MELI": 60}
                        ratio = ratios.get(tk, 10) if px_usd_underlying < 5000 else 1
                        
                        # Decidir moneda de venta (vendemos en ARS por defecto para liquidez local, a menos que el usuario quiera USD)
                        # Vamos a vender en la moneda de cotización original (USD) si es extranjero
                        if px_usd_underlying < 5000:
                            mon = 'USD'
                            px_venta = px_usd_underlying / ratio
                        else:
                            mon = 'ARS'
                            px_venta = (px_usd_underlying * ccl) / ratio if px_usd_underlying < 5000 else px_usd_underlying
                        
                        bruto = qty * px_venta
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
                            'PRECIO_UNITARIO': round(px_venta, 2),
                            'MONEDA': mon,
                            'COMISIÓN_TOTAL': round(comision, 2),
                            'OBSERVACIONES': f'Venta IA: {razon[:50]}...',
                            'TOTAL_NETO': neto,
                            'PRECIO_MERCADO_REF': px_usd_underlying
                        })
                        
                        if mon == 'USD':
                            saldo_caja_usd += neto
                        else:
                            saldo_caja_ars += neto
                            
                        total_ventas += 1
                        op_ejecutadas += 1
                        resumen_fondo.append(f"  🔴 VENDIÓ {qty} {tk} a ${px_venta:,.2f} {mon}. Motivo: {razon}")
                        
            # --- EJECUTAR COMPRAS ---
            efectivo_libre_ars = saldo_caja_ars - caja_minima
            efectivo_libre_usd = saldo_caja_usd
            
            import re
            compras_validas = []
            for tk in compras:
                if tk in info_activos:
                    if tk == 'USDARS':
                        resumen_fondo.append(f"  ⏭️ OMITIDO: La IA recomendó dolarizar ({tk}), pero la compra de divisas está inhabilitada por seguridad.")
                        continue
                        
                    razon_text = info_activos[tk]['razon']
                    score_match = re.search(r"SCORE:\s*(\d+)", razon_text)
                    if score_match:
                        score_val = int(score_match.group(1))
                        if score_val < 6:
                            resumen_fondo.append(f"  ⏭️ OMITIDO: {tk} descartado por bajo puntaje de convicción ({score_val}/10).")
                            continue
                            
                    compras_validas.append(tk)
                    
            if compras_validas:
                cash_ars_per_asset = max(0, efectivo_libre_ars) / len(compras_validas)
                cash_usd_per_asset = max(0, efectivo_libre_usd) / len(compras_validas)
                
                for tk in compras_validas:
                    info = info_activos[tk]
                    px = info['precio']
                    mon = info['moneda']
                    ccl = info['ccl']
                    razon = info['razon']
                    
                    px_usd_underlying = px
                    
                    ratios = {"AAPL": 10, "TSLA": 15, "SPY": 20, "QQQ": 20, "MSFT": 30, "AMZN": 144, "GOOGL": 58, "META": 24, "AMD": 10, "NVDA": 24, "KO": 5, "MCD": 12, "DIS": 12, "MELI": 60}
                    ratio = ratios.get(tk, 10) if px_usd_underlying < 5000 else 1  # Si es < 5000 asumimos que es USD underlying
                    
                    px_cedear_usd = px_usd_underlying / ratio
                    px_cedear_ars = (px_usd_underlying * ccl) / ratio
                    
                    px_con_comision_usd = px_cedear_usd * (1 + comision_pct)
                    px_con_comision_ars = px_cedear_ars * (1 + comision_pct)
                    
                    qty = 0
                    moneda_pago = 'ARS'
                    px_pago = px_cedear_ars
                    
                    # Decisión Financiera: Comparar brecha de CCL
                    if px_usd_underlying < 5000:
                        if ccl > ccl_promedio:
                            # El CCL del ticker es MAYOR al promedio -> Caro en pesos -> Comprar en USD si hay
                            qty = math.floor(cash_usd_per_asset / px_con_comision_usd)
                            if qty > 0:
                                moneda_pago = 'USD'
                                px_pago = px_cedear_usd
                                efectivo_libre_usd -= (qty * px_con_comision_usd)
                            else:
                                # Fallback a ARS
                                qty = math.floor(cash_ars_per_asset / px_con_comision_ars)
                                if qty > 0:
                                    moneda_pago = 'ARS'
                                    px_pago = px_cedear_ars
                                    efectivo_libre_ars -= (qty * px_con_comision_ars)
                        else:
                            # El CCL del ticker es MENOR al promedio -> Barato en pesos -> Comprar en ARS si hay
                            qty = math.floor(cash_ars_per_asset / px_con_comision_ars)
                            if qty > 0:
                                moneda_pago = 'ARS'
                                px_pago = px_cedear_ars
                                efectivo_libre_ars -= (qty * px_con_comision_ars)
                            else:
                                # Fallback a USD
                                qty = math.floor(cash_usd_per_asset / px_con_comision_usd)
                                if qty > 0:
                                    moneda_pago = 'USD'
                                    px_pago = px_cedear_usd
                                    efectivo_libre_usd -= (qty * px_con_comision_usd)
                    else:
                        # Activo puramente local (precio > 5000)
                        qty = math.floor(cash_ars_per_asset / px_con_comision_ars)
                        if qty > 0:
                            moneda_pago = 'ARS'
                            px_pago = px_cedear_ars
                            efectivo_libre_ars -= (qty * px_con_comision_ars)
                            
                    if qty > 0:
                        bruto = round(qty * px_pago, 2)
                        comision = round(bruto * comision_pct, 2)
                        neto = round(bruto + comision, 2)
                        px_pago_rounded = round(px_pago, 2)
                        
                        nuevas_transacciones.append({
                            'FECHA': hoy,
                            'PROPIETARIO': cartera_id,
                            'BROKER_CUENTA': 'AUTO_TRADER_IA',
                            'ACTIVO': tk,
                            'ESPECIE': 'CEDEAR/ACCION',
                            'OPERACIÓN': 'COMPRA',
                            'CANTIDAD': qty,
                            'PRECIO_UNITARIO': px_pago_rounded,
                            'MONEDA': moneda_pago,
                            'COMISIÓN_TOTAL': comision,
                            'OBSERVACIONES': f'Compra IA: {razon[:50]}...',
                            'TOTAL_NETO': neto,
                            'PRECIO_MERCADO_REF': round(px, 2),
                            'FECHA_ACTUALIZACION': hoy
                        })
                        
                        nuevos_movimientos_caja.append({
                            'FECHA': hoy,
                            'PROPIETARIO': cartera_id,
                            'MOVIMIENTO': 'EGRESO',
                            'MONTO': neto,
                            'MONEDA': moneda_pago,
                            'CONCEPTO': f'Operación Compra - {qty}x {tk}',
                            'FECHA_ACTUALIZACION': hoy
                        })
                        
                        if moneda_pago == 'USD':
                            saldo_caja_usd -= neto
                        else:
                            saldo_caja_ars -= neto
                            
                        total_compras += 1
                        op_ejecutadas += 1
                        extra = "" if moneda_pago == mon else " (vía CCL)"
                        resumen_fondo.append(f"  🟢 COMPRÓ {qty} {tk} a ${px_pago:,.2f} {moneda_pago}{extra}. Motivo: {razon}")
                    else:
                        resumen_fondo.append(f"  ⚠️ OMITIÓ comprar {tk}. Sin liquidez libre. Sugerido por: {razon}")
            
            if op_ejecutadas == 0 and not compras:
                resumen_fondo.append("  💤 Sin señales de operación hoy.")
                
            resumen_telegram.extend(resumen_fondo)
            
            # Asegurar que SALDO sea float para evitar TypeError de Pandas
            df_caja['SALDO'] = df_caja['SALDO'].astype(float)
            
            # Actualizar dataframe de CAJA_LIQUIDEZ en memoria
            idx_ars = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'ARS')].index
            if not idx_ars.empty:
                df_caja.loc[idx_ars, 'SALDO'] = float(saldo_caja_ars)
                df_caja.loc[idx_ars, 'ULTIMA_ACTUALIZACION'] = hoy
                
            idx_usd = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'USD')].index
            if not idx_usd.empty:
                df_caja.loc[idx_usd, 'SALDO'] = float(saldo_caja_usd)
                df_caja.loc[idx_usd, 'ULTIMA_ACTUALIZACION'] = hoy
            
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
                
            df_final_trans = df_final_trans.fillna("")
                
            ws_trans.clear()
            ws_trans.update([df_final_trans.columns.values.tolist()] + df_final_trans.values.tolist())
            
        if nuevos_movimientos_caja:
            ws_caja = sh.worksheet("MOVIMIENTOS_CAJA")
            caja_data = ws_caja.get_all_records()
            df_caja_old = pd.DataFrame(caja_data)
            df_nuevos_caja = pd.DataFrame(nuevos_movimientos_caja)
            
            cols_caja = ['FECHA', 'PROPIETARIO', 'MOVIMIENTO', 'MONTO', 'MONEDA', 'CONCEPTO', 'FECHA_ACTUALIZACION']
            for c in cols_caja:
                if c not in df_nuevos_caja.columns:
                    df_nuevos_caja[c] = ""
            df_nuevos_caja = df_nuevos_caja[cols_caja]
            
            if df_caja_old.empty:
                df_final_caja = df_nuevos_caja
            else:
                df_final_caja = pd.concat([df_caja_old, df_nuevos_caja], ignore_index=True)
                
            df_final_caja = df_final_caja.fillna("")
                
            ws_caja.clear()
            ws_caja.update([df_final_caja.columns.values.tolist()] + df_final_caja.values.tolist())
            
            # Grabar la "foto" de la billetera actualizada en CAJA_LIQUIDEZ
            ws_caja_liq = sh.worksheet("CAJA_LIQUIDEZ")
            df_caja = df_caja.fillna("")
            ws_caja_liq.clear()
            ws_caja_liq.update([df_caja.columns.values.tolist()] + df_caja.values.tolist())
            
            # Recalcular valoraciones automáticamente tras asentar los movimientos
            import valorador_cartera
            valorador_cartera.ejecutar_valoracion()
            
        duracion = f"{(time.time() - t_inicio) / 60:.2f} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", f"AutoTrader ejecutado.", nombre_proceso="auto_trader_ia", tiempo_ejecucion=duracion)
        
        
        # Enviar resumen a Telegram
        resumen_telegram.append(f"\n📊 *Total operaciones:* {total_compras} compras, {total_ventas} ventas. (Tiempo: {duracion})")
        notificador_telegram.enviar_mensaje_telegram("\n".join(resumen_telegram))
        
        return True
        
    except Exception as e:
        logger.error(f"Error en Auto-Trader: {e}", exc_info=True)
        try:
            notificador_telegram.enviar_mensaje_telegram(f"🚨 *Error en Auto-Trader IA:* {e}")
        except:
            pass
        return False

if __name__ == '__main__':
    ejecutar_auto_trader()
