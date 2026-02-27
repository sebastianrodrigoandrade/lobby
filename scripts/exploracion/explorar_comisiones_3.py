import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"

# Integrantes
r = requests.get(f"{BASE}/comisiones/permanentes/caconstitucionales/integrantes.html", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
print("=== INTEGRANTES ===")
print(soup.get_text(separator='\n', strip=True)[:2000])

# Reuniones
r2 = requests.get(f"{BASE}/comisiones/permanentes/caconstitucionales/reuniones/", timeout=15, verify=False)
soup2 = BeautifulSoup(r2.text, 'html.parser')
print("\n=== REUNIONES ===")
print(soup2.get_text(separator='\n', strip=True)[:2000])