import auth_google
import config
import pandas as pd

def reparar():
    sh = auth_google.conectar()
    if not sh:
        print("Error: No se pudo conectar a Sheets.")
        return
        
    ws = sh.worksheet("CAJA_LIQUIDEZ")
    raw_data = ws.get_all_values()
    print("Cabeceras:", raw_data[0])
    
    # Vamos a leer la matriz, limpiar y re-escribir todo con USER_ENTERED
    ws.clear()
    ws.update(values=raw_data, range_name="A1", value_input_option="USER_ENTERED")
    print("Hoja CAJA_LIQUIDEZ re-escrita con USER_ENTERED exitosamente.")

if __name__ == "__main__":
    reparar()
