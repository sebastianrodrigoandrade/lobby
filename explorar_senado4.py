import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"
r = requests.get(f"{BASE}/parlamentario/sesiones/busquedaTac", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

links = soup.find_all('a', href=True)
tac_links = [l['href'] for l in links if 'downloadTac' in l['href']]

print(f"Total links encontrados: {len(tac_links)}")
for l in tac_links:
    print(l)