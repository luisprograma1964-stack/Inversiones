import sys
sys.path.append('C:\\Para mi\\Inversiones')
import auth_google, config
sh = auth_google.conectar()
ws = sh.worksheet(config.WS_MAESTRO_USUARIOS)
print(ws.get_all_records())
