import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

URLS = {
    "datos_abiertos": "https://www.senado.gob.ar/micrositios/DatosAbiertos/",
    "senadores_bloques": "https://www.senado.gob.ar/senadores/listados/agrupados-por-bloques",
    "votaciones": "https://www.senado.gob.ar/votaciones/actas",
    "sesiones": "https://www.senado.gob.ar/parlamentario/sesiones/busquedaTac",
    "ddjj": "https://www.senado.gob.ar/administrativo/ddjj/",
    "historico": "https://www.senado.gob.ar/senadores/Historico/Introduccion",
}

for nombre, url in URLS.items():
    print(f"\n{'='*60}")
    print(f"=== {nombre} ===")
    print(f"URL: {url}")
    try:
        r = requests.get(url, timeout=15, verify=False)
        print(f"Status: {r.status_code}")
        soup = BeautifulSoup(r.text, 'html.parser')

        # Buscar links a CSVs o APIs
        links = soup.find_all('a', href=True)
        csv_links = [l['href'] for l in links if '.csv' in l['href'].lower() or 'api' in l['href'].lower() or 'download' in l['href'].lower()]
        if csv_links:
            print(f"CSV/API links encontrados:")
            for l in csv_links[:10]:
                print(f"  {l}")
        
        # Mostrar texto visible resumido
        texto = soup.get_text(separator=' ', strip=True)
        print(f"Texto (primeros 400 chars): {texto[:400]}")

    except Exception as e:
        print(f"Error: {e}")

print("\n=== DONE ===")

