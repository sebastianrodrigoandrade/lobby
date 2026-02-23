import requests
import warnings
warnings.filterwarnings('ignore')

BASE_URL = "https://datos.hcdn.gob.ar/api/3/action"

# Buscar datasets de senado en el portal HCDN
print("=== BUSCANDO DATASETS SENADO ===")
for termino in ["senado", "senadores", "votaciones_senado"]:
    r = requests.get(f"{BASE_URL}/package_search", 
                     params={"q": termino, "rows": 10}, 
                     verify=False, timeout=30)
    data = r.json()
    if data.get("success"):
        resultados = data["result"]["results"]
        if resultados:
            for ds in resultados:
                print(f"\nDataset: {ds['name']}")
                print(f"Título:  {ds['title']}")
                for res in ds.get('resources', []):
                    if '.csv' in res.get('url', '').lower():
                        print(f"  CSV: {res['name']}")
                        print(f"  URL: {res['url']}")

# También probar el portal del Senado directamente
print("\n=== PROBANDO PORTAL SENADO ===")
urls_senado = [
    "https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListaSenadores",
    "https://datos.senado.gob.ar/api/3/action/package_list",
    "https://www.senado.gob.ar/votaciones/actas",
]
for url in urls_senado:
    try:
        r = requests.get(url, timeout=10, verify=False)
        print(f"\n{url}")
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', '')}")
        if r.status_code == 200:
            print(f"Primeros 200 chars: {r.text[:200]}")
    except Exception as e:
        print(f"{url} -> Error: {e}")