import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"

# Explorar una comisión específica
url = f"{BASE}/comisiones/permanentes/caconstitucionales"
r = requests.get(url, timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

print(f"Status: {r.status_code}")
print("\n--- Texto visible ---")
print(soup.get_text(separator='\n', strip=True)[:3000])

# Buscar links internos
links = soup.find_all('a', href=True)
print("\n--- Links ---")
for l in links[:30]:
    print(l['href'])