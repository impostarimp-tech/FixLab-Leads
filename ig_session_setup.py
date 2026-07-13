"""
Crea la sesion de Instaloader importando las cookies de Chrome/Firefox.
Solo hay que estar logueado en instagram.com en el browser.
Correr una vez: python ig_session_setup.py
"""
import os
import sys
import instaloader
import browser_cookie3

IG_USERNAME = os.getenv("IG_USERNAME", "pepe.pepe1366")
SESSION_FILE = os.path.join(os.path.expanduser("~"), f".instaloader-session-{IG_USERNAME}")

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    save_metadata=False,
    quiet=True,
)

print(f"Buscando sesion de Instagram para @{IG_USERNAME} en el browser...")
print("(Asegurate de estar logueado en instagram.com en Chrome o Firefox)\n")

importado = False

# Intentar Chrome
try:
    cookiejar = browser_cookie3.chrome(domain_name='.instagram.com')
    cookies = {c.name: c.value for c in cookiejar}
    if 'sessionid' in cookies:
        L.context._session.cookies.update(cookiejar)
        L.context.username = IG_USERNAME
        L.save_session_to_file(SESSION_FILE)
        print(f"[OK] Sesion importada desde Chrome")
        print(f"[OK] Guardada en: {SESSION_FILE}")
        importado = True
    else:
        print("  Chrome: no se encontro sesion activa de Instagram")
except Exception as e:
    print(f"  Chrome: {e}")

# Intentar Firefox si Chrome no funciono
if not importado:
    try:
        cookiejar = browser_cookie3.firefox(domain_name='.instagram.com')
        cookies = {c.name: c.value for c in cookiejar}
        if 'sessionid' in cookies:
            L.context._session.cookies.update(cookiejar)
            L.context.username = IG_USERNAME
            L.save_session_to_file(SESSION_FILE)
            print(f"[OK] Sesion importada desde Firefox")
            print(f"[OK] Guardada en: {SESSION_FILE}")
            importado = True
        else:
            print("  Firefox: no se encontro sesion activa de Instagram")
    except Exception as e:
        print(f"  Firefox: {e}")

if not importado:
    print("\nERROR: No se pudo importar la sesion.")
    print("Pasos:")
    print("  1. Abri Chrome")
    print("  2. Andá a instagram.com y logueate con pepe.pepe1366")
    print("  3. Volvé a correr este script")
    sys.exit(1)

print("\nListo. Ya podes usar el scraper de seguidores desde la app.")
