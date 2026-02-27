import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"

# Buscar una URL de citación concreta
r = requests.get(f"{BASE}/comisiones/permanentes/caconstitucionales/reuniones/", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

# Encontrar links a citaciones
links = soup.find_all('a', href=True)
citaciones = [l['href'] for l in links if 'citacion' in l['href'].lower() or 'cit' in l['href'].lower()]
print("Links de citaciones encontrados:")
for l in citaciones[:10]:
    print(l)