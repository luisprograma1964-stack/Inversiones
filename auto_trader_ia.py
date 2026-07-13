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
            df_val = pd.DataFrame(sh.worksheet("VALORACION_PORTAFOLIO").get_all_records())
        except:
            df_val = pd.DataFrame()
            
        # 2. Filtrar Carteras de Simulacion
        fondos_ia = df_carteras[df_carteras['TIPO_CARTERA'].astype(str).str.upper() == 'SIMULACION'].to_dict('records')
        
        if not fondos_ia:
            resumen_telegram.append("⚠️ No se encontraron carteras de simulación activas.")
            notificador_telegram.enviar_mensaje_telegram("\n".join(resumen_telegram))
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
        
        total_compras = 0
        total_ventas = 0
        
        # 3. Iterar por cada Fondo IA
        for fondo in fondos_ia:
            cartera_id = str(fondo.get('CARTERA_ID', '')).strip().upper()
            perfil = str(fondo.get('PERFIL_RIESGO', '')).strip().upper()
            comision_pct = float(fondo.get('COMISION_BROKER', 0.0)) / 100.0
            liq_target = float(fondo.get('PORCENTAJE_LIQUIDEZ', 0.10))
            
            resumen_fondo = [f"\n💼 *{cartera_id}* ({perfil})"]
            
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
            
            op_ejecutadas = 0
            
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
                        total_ventas += 1
                        op_ejecutadas += 1
                        resumen_fondo.append(f"  🔴 VENDIÓ {qty} {tk} a ${px}")
                        
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
                                'FECHA': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'PROPIETARIO': cartera_id,
                                'BROKER_CUENTA': 'AUTO_TRADER_IA',
                                'ACTIVO': tk,
                                'ESPECIE': 'CEDEAR/ACCION',
                                'OPERACIÓN': 'Compra',
                                'OPERACION': 'Compra',
                                'CANTIDAD': qty,
                                'PRECIO_UNITARIO': px,
                                'MONEDA': 'ARS',
                                'COMISIÓN_TOTAL': comision,
                                'COMISION_TOTAL': comision,
                                'OBSERVACIONES': 'Compra dictaminada por IA',
                                'TOTAL_NETO': neto,
                                'PRECIO_MERCADO_REF': px,
                                'FECHA_ACTUALIZACION': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            nuevos_movimientos_caja.append({
                                'FECHA': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'PROPIETARIO': cartera_id,
                                'MOVIMIENTO': 'EGRESO',
                                'MONTO': neto,
                                'MONEDA': 'ARS',
                                'CONCEPTO': f'Operación Compra - {qty}x {tk}',
                                'FECHA_ACTUALIZACION': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            saldo_caja -= neto
                            total_compras += 1
                            op_ejecutadas += 1
                            resumen_fondo.append(f"  🟢 COMPRÓ {qty} {tk} a ${px}")
            elif compras:
                resumen_fondo.append(f"  ⚠️ OMITIÓ {len(compras)} compras (Caja libre insuficiente: ${max(0, efectivo_libre):,.2f})")
                

            
            if op_ejecutadas == 0 and not compras:
                resumen_fondo.append("  💤 Sin señales de operación hoy.")
                
            resumen_telegram.extend(resumen_fondo)
            
            # Actualizar dataframe de CAJA_LIQUIDEZ en memoria
            idx = df_caja[(df_caja['PROPIETARIO'].astype(str).str.upper() == cartera_id) & (df_caja['MONEDA'] == 'ARS')].index
            if not idx.empty:
                df_caja.loc[idx, 'SALDO'] = saldo_caja
                df_caja.loc[idx, 'ULTIMA_ACTUALIZACION'] = hoy
            
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
        import notificador_telegram
        notificador_telegram.enviar_mensaje_telegram("\n".join(resumen_telegram))
        
        return True
        
    except Exception as e:
        logger.error(f"Error en Auto-Trader: {e}")
        try:
            ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", f"Fallo Auto-Trader: {str(e)[:100]}", nombre_proceso="auto_trader_ia")
        except: pass
        notificador_telegram.enviar_mensaje_telegram(f"❌ *Error en Auto-Trader IA:* {e}")
        return False

if __name__ == '__main__':
    ejecutar_auto_trader()
