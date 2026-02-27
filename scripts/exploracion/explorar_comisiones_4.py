import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"
r = requests.get(f"{BASE}/comisiones/permanentes/", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

links = soup.find_all('a', href=True)
comisiones = [l['href'] for l in links if '/comisiones/permanentes/' in l['href'] and l['href'] != '/comisiones/permanentes/']
print(f"Total comisiones: {len(comisiones)}")
for c in comisiones:
    print(c)