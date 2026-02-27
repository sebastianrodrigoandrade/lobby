import requests
import warnings
warnings.filterwarnings('ignore')

# Probar endpoints JSON del HCDN
urls = [
    "https://www.hcdn.gob.ar/comisiones/permanentes/caconstitucionales/reuniones/index.json",
    "https://datos.hcdn.gob.ar/api/3/action/package_search?q=reuniones+comision",
    "https://www.hcdn.gob.ar/comisiones/permanentes/caconstitucionales/reuniones/?format=json",
    "https://www.hcdn.gob.ar/comisiones/reuniones.json",
]

for url in urls:
    try:
        r = requests.get(url, timeout=10, verify=False)
        print(f"\n{url}")
        print(f"Status: {r.status_code} | Content-Type: {r.headers.get('content-type', '')}")
        if r.status_code == 200:
            print(r.text[:300])
    except Exception as e:
        print(f"{url} -> Error: {e}")