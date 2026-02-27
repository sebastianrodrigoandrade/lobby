import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"

urls = {
    "listado_comisiones": f"{BASE}/comisiones/permanentes/",
    "api_comisiones": "https://datos.hcdn.gob.ar/api/3/action/package_search?q=comisiones",
    "reuniones": f"{BASE}/comisiones/reuniones/",
}

for nombre, url in urls.items():
    print(f"\n{'='*60}")
    print(f"=== {nombre} ===")
    try:
        r = requests.get(url, timeout=15, verify=False)
        print(f"Status: {r.status_code}")
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Buscar links relevantes
        links = soup.find_all('a', href=True)
        relevantes = [l['href'] for l in links if any(x in l['href'].lower() for x in ['comision', 'comisión', 'reunion', 'miembro', 'integrante'])]
        if relevantes:
            print("Links relevantes:")
            for l in relevantes[:10]:
                print(f"  {l}")
        
        print(f"Texto: {soup.get_text(separator=' ', strip=True)[:300]}")
    except Exception as e:
        print(f"Error: {e}")