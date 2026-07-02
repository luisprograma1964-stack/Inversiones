import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd
from datetime import datetime, timedelta

def main():
    print("[*] Iniciando purga y carga de datos simulados coherentes...")
    sh = auth_google.conectar()
    if not sh:
        print("[FAIL] No se pudo conectar a Google Sheets")
        return

    # 1. Hojas operativas a limpiar
    ws_caja = sh.worksheet("MOVIMIENTOS_CAJA")
    ws_trans = sh.worksheet("TRANSACCIONES")
    ws_usuarios = sh.worksheet("CONFIG_IA_USUARIO")
    ws_liquidez = sh.worksheet("CAJA_LIQUIDEZ")

    # Obtener encabezados
    headers_caja = [h.strip().upper() for h in ws_caja.row_values(1)]
    headers_trans = [h.strip().upper() for h in ws_trans.row_values(1)]
    headers_usuarios = [h.strip().upper() for h in ws_usuarios.row_values(1)]
    headers_liquidez = [h.strip().upper() for h in ws_liquidez.row_values(1)]

    print(f"[*] Encabezados Caja: {headers_caja}")
    print(f"[*] Encabezados Transacciones: {headers_trans}")
    print(f"[*] Encabezados Usuarios: {headers_usuarios}")
    print(f"[*] Encabezados Liquidez: {headers_liquidez}")

    # Limpiar hojas
    ws_caja.clear()
    ws_caja.update(values=[headers_caja], range_name="A1")
    
    ws_trans.clear()
    ws_trans.update(values=[headers_trans], range_name="A1")

    ws_liquidez.clear()
    ws_liquidez.update(values=[headers_liquidez], range_name="A1")

    # 2. Configurar perfiles de prueba en CONFIG_IA_USUARIO
    rows_usuarios = [
        {"PROPIETARIO": "LUIS", "PERFIL_INVERSOR": "AGRESIVO", "DESCRIPCION": "Perfil dinámico enfocado en alto crecimiento", "ACTIVO": "SI"},
        {"PROPIETARIO": "LUIS_MODERADO", "PERFIL_INVERSOR": "MODERADO", "DESCRIPCION": "Perfil balanceado Cedears y renta fija", "ACTIVO": "SI"},
        {"PROPIETARIO": "VICKY", "PERFIL_INVERSOR": "MODERADO", "DESCRIPCION": "Perfil conservador Cedears blue-chips", "ACTIVO": "SI"},
        {"PROPIETARIO": "ANTO", "PERFIL_INVERSOR": "MODERADO", "DESCRIPCION": "Perfil balanceado a largo plazo", "ACTIVO": "SI"}
    ]
    
    # Escribir usuarios
    rows_to_write_users = []
    for u in rows_usuarios:
        row = []
        for h in headers_usuarios:
            row.append(u.get(h, ""))
        rows_to_write_users.append(row)
        
    ws_usuarios.clear()
    ws_usuarios.update(values=[headers_usuarios] + rows_to_write_users, range_name="A1")
    print("[OK] Perfiles de usuario cargados in CONFIG_IA_USUARIO.")

    # 2.5 Cargar datos de CAJA_LIQUIDEZ calculados exactamente
    # LUIS: ARS 10.048.000, USD 7.590
    # LUIS_MODERADO: ARS 4.933.000, USD 5.000
    # VICKY: ARS 4.317.100, USD 8.000
    # ANTO: ARS 4.876.400, USD 3.135
    saldos_iniciales_liquidez = [
        {"PROPIETARIO": "LUIS", "MONEDA": "ARS", "SALDO": "10048000,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Nación LUIS", "TIPO": "Familiar"},
        {"PROPIETARIO": "LUIS", "MONEDA": "USD", "SALDO": "7590,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Nación LUIS", "TIPO": "Familiar"},
        
        {"PROPIETARIO": "LUIS_MODERADO", "MONEDA": "ARS", "SALDO": "4933000,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Nación LUIS_MOD", "TIPO": "Familiar"},
        {"PROPIETARIO": "LUIS_MODERADO", "MONEDA": "USD", "SALDO": "5000,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Nación LUIS_MOD", "TIPO": "Familiar"},
        
        {"PROPIETARIO": "VICKY", "MONEDA": "ARS", "SALDO": "4317100,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Cocos VICKY", "TIPO": "Familiar"},
        {"PROPIETARIO": "VICKY", "MONEDA": "USD", "SALDO": "8000,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Cocos VICKY", "TIPO": "Familiar"},
        
        {"PROPIETARIO": "ANTO", "MONEDA": "ARS", "SALDO": "4876400,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Cocos ANTO", "TIPO": "Familiar"},
        {"PROPIETARIO": "ANTO", "MONEDA": "USD", "SALDO": "3135,00", "ULTIMA_ACTUALIZACION": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUENTA": "Cocos ANTO", "TIPO": "Familiar"}
    ]

    rows_to_write_liquidez = []
    for s in saldos_iniciales_liquidez:
        row = []
        for h in headers_liquidez:
            row.append(s.get(h, ""))
        rows_to_write_liquidez.append(row)
        
    ws_liquidez.update(values=[headers_liquidez] + rows_to_write_liquidez, range_name="A1")
    print("[OK] Saldos de caja inicializados en CAJA_LIQUIDEZ.")

    # 3. Registrar Movimientos de Caja (Ingresos/Aportes iniciales para tener saldo)
    ahora_dt = datetime.now()
    fecha_aporte = (ahora_dt - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    aportes_caja = [
        # LUIS
        {"FECHA": fecha_aporte, "PROPIETARIO": "LUIS", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "15000000,00", "MONEDA": "ARS", "DETALLE": "Aporte inicial ARS"},
        {"FECHA": fecha_aporte, "PROPIETARIO": "LUIS", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "10000,00", "MONEDA": "USD", "DETALLE": "Aporte inicial USD"},
        # LUIS_MODERADO
        {"FECHA": fecha_aporte, "PROPIETARIO": "LUIS_MODERADO", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "8000000,00", "MONEDA": "ARS", "DETALLE": "Aporte inicial ARS"},
        {"FECHA": fecha_aporte, "PROPIETARIO": "LUIS_MODERADO", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "5000,00", "MONEDA": "USD", "DETALLE": "Aporte inicial USD"},
        # VICKY
        {"FECHA": fecha_aporte, "PROPIETARIO": "VICKY", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "10000000,00", "MONEDA": "ARS", "DETALLE": "Aporte inicial ARS"},
        {"FECHA": fecha_aporte, "PROPIETARIO": "VICKY", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "8000,00", "MONEDA": "USD", "DETALLE": "Aporte inicial USD"},
        # ANTO
        {"FECHA": fecha_aporte, "PROPIETARIO": "ANTO", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "12000000,00", "MONEDA": "ARS", "DETALLE": "Aporte inicial ARS"},
        {"FECHA": fecha_aporte, "PROPIETARIO": "ANTO", "TIPO": "INGRESO", "TIPO_MOVIMIENTO": "INGRESO", "MONTO": "6000,00", "MONEDA": "USD", "DETALLE": "Aporte inicial USD"}
    ]

    rows_to_write_caja = []
    for a in aportes_caja:
        row = []
        for h in headers_caja:
            row.append(a.get(h, ""))
        rows_to_write_caja.append(row)
        
    ws_caja.append_rows(rows_to_write_caja, value_input_option="USER_ENTERED")
    print(f"[OK] {len(aportes_caja)} aportes registrados en MOVIMIENTOS_CAJA.")

    # 4. Registrar Transacciones de Compra Coherentes
    # Usaremos activos del maestro como AAPL, TSLA, KO, AMZN, META
    fecha_compra_1 = (ahora_dt - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    fecha_compra_2 = (ahora_dt - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    
    compras = [
        # LUIS
        {"FECHA": fecha_compra_1, "PROPIETARIO": "LUIS", "ACTIVO": "AAPL", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "300,00", "PRECIO_UNITARIO": "12500,00", "COMISION_TOTAL": "1500,00", "COMISIÓN_TOTAL": "1500,00", "MONEDA": "ARS", "TOTAL_NETO": "3751500,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "LUIS", "ACTIVO": "TSLA", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "50,00", "PRECIO_UNITARIO": "24000,00", "COMISION_TOTAL": "500,00", "COMISIÓN_TOTAL": "500,00", "MONEDA": "ARS", "TOTAL_NETO": "1200500,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "LUIS", "ACTIVO": "META", "OPERacion": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "20,00", "PRECIO_UNITARIO": "120,00", "COMISION_TOTAL": "10,00", "COMISIÓN_TOTAL": "10,00", "MONEDA": "USD", "TOTAL_NETO": "2410,00"},
        
        # LUIS_MODERADO
        {"FECHA": fecha_compra_1, "PROPIETARIO": "LUIS_MODERADO", "ACTIVO": "KO", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "200,00", "PRECIO_UNITARIO": "8200,00", "COMISION_TOTAL": "800,00", "COMISIÓN_TOTAL": "800,00", "MONEDA": "ARS", "TOTAL_NETO": "1640800,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "LUIS_MODERADO", "ACTIVO": "AMZN", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "150,00", "PRECIO_UNITARIO": "9500,00", "COMISION_TOTAL": "1200,00", "COMISIÓN_TOTAL": "1200,00", "MONEDA": "ARS", "TOTAL_NETO": "1426200,00"},
        
        # VICKY
        {"FECHA": fecha_compra_1, "PROPIETARIO": "VICKY", "ACTIVO": "AMD", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "400,00", "PRECIO_UNITARIO": "11000,00", "COMISION_TOTAL": "2000,00", "COMISIÓN_TOTAL": "2000,00", "MONEDA": "ARS", "TOTAL_NETO": "4402000,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "VICKY", "ACTIVO": "AAPL", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "100,00", "PRECIO_UNITARIO": "12800,00", "COMISION_TOTAL": "900,00", "COMISIÓN_TOTAL": "900,00", "MONEDA": "ARS", "TOTAL_NETO": "1280900,00"},
        
        # ANTO
        {"FECHA": fecha_compra_1, "PROPIETARIO": "ANTO", "ACTIVO": "TSLA", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "250,00", "PRECIO_UNITARIO": "23500,00", "COMISION_TOTAL": "3000,00", "COMISIÓN_TOTAL": "3000,00", "MONEDA": "ARS", "TOTAL_NETO": "5878000,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "ANTO", "ACTIVO": "KO", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "150,00", "PRECIO_UNITARIO": "8300,00", "COMISION_TOTAL": "600,00", "COMISIÓN_TOTAL": "600,00", "MONEDA": "ARS", "TOTAL_NETO": "1245600,00"},
        {"FECHA": fecha_compra_2, "PROPIETARIO": "ANTO", "ACTIVO": "AMZN", "OPERACION": "Compra", "OPERACIÓN": "Compra", "CANTIDAD": "30,00", "PRECIO_UNITARIO": "95,00", "COMISION_TOTAL": "15,00", "COMISIÓN_TOTAL": "15,00", "MONEDA": "USD", "TOTAL_NETO": "2865,00"}
    ]

    rows_to_write_trans = []
    for c in compras:
        row = []
        for h in headers_trans:
            # Asegurar compatibilidad de minúsculas
            h_clean = h.strip().upper()
            val = c.get(h_clean) or c.get(h_clean.replace('Ó', 'O')) or c.get(h_clean.lower()) or ""
            row.append(val)
        rows_to_write_trans.append(row)
        
    ws_trans.append_rows(rows_to_write_trans, value_input_option="USER_ENTERED")
    print(f"[OK] {len(compras)} compras iniciales registradas en TRANSACCIONES.")
    print("[OK] Carga finalizada con éxito.")

if __name__ == "__main__":
    main()
