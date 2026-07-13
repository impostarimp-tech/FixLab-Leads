"""
Crea la sesion de Instaloader a partir del sessionid de Instagram.
Como obtenerlo:
  1. Chrome -> instagram.com (logueado como pepe.pepe1366)
  2. F12 -> Application -> Cookies -> https://www.instagram.com
  3. Copiá el valor de la fila "sessionid"
"""
import os
import sys
import instaloader

IG_USERNAME  = "pepe.pepe1366"
SESSION_FILE = os.path.join(os.path.expanduser("~"), f".instaloader-session-{IG_USERNAME}")

print("=" * 50)
print("  FixLab - Renovar sesion Instagram")
print("=" * 50)
print()
print("Chrome -> instagram.com -> F12 -> Application")
print("-> Cookies -> sessionid -> copiar Value")
print()

session_id = input("Pega el sessionid y presiona Enter: ").strip()

if len(session_id) < 20:
    print("ERROR: sessionid muy corto, verificá que copiaste bien.")
    sys.exit(1)

L = instaloader.Instaloader(download_pictures=False, download_videos=False,
                             save_metadata=False, quiet=True)
L.context._session.cookies.set("sessionid", session_id, domain=".instagram.com")
L.context.username = IG_USERNAME

try:
    L.save_session_to_file(SESSION_FILE)
    print(f"\n[OK] Sesion guardada. Lista para usar.")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
