"""Debug: muestra todas las cookies de Instagram encontradas en Chrome."""
import os, sys, shutil, sqlite3, tempfile, json, base64

CHROME_USER_DATA = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
LOCAL_STATE      = os.path.join(CHROME_USER_DATA, "Local State")
DB_PATH          = os.path.join(CHROME_USER_DATA, "Default", "Network", "Cookies")

def get_key():
    with open(LOCAL_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)
    enc = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
    import win32crypt
    return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1]

def decrypt(key, val):
    try:
        if val[:3] in (b"v10", b"v11"):
            from Crypto.Cipher import AES
            nonce = val[3:15]; ct = val[15:-16]; tag = val[-16:]
            return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag).decode()
        else:
            import win32crypt
            return win32crypt.CryptUnprotectData(val, None, None, None, 0)[1].decode()
    except Exception as e:
        return f"<ERROR: {e}>"

print(f"Leyendo: {DB_PATH}")
tmp = tempfile.mktemp(suffix=".db")
shutil.copy2(DB_PATH, tmp)

try:
    key = get_key()
    conn = sqlite3.connect(tmp)
    cur = conn.cursor()
    # Mostrar TODOS los host_key que contienen "instagram"
    cur.execute("SELECT DISTINCT host_key FROM cookies WHERE host_key LIKE '%instagram%'")
    hosts = [r[0] for r in cur.fetchall()]
    print(f"Host keys encontrados: {hosts}")

    cur.execute("SELECT name, host_key, encrypted_value FROM cookies WHERE host_key LIKE '%instagram%'")
    rows = cur.fetchall()
    conn.close()
    print(f"Total cookies Instagram: {len(rows)}")
    for name, host, enc in rows:
        val = decrypt(key, enc)
        print(f"  [{host}] {name} = {val[:40]}...")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    os.remove(tmp)
