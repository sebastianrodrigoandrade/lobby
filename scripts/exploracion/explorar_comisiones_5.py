import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.hcdn.gob.ar"

# Comisión que dio 0 integrantes
r = requests.get(f"{BASE}/comisiones/permanentes/ceducacion/integrantes.html", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
print("=== INTEGRANTES EDUCACION ===")
print(soup.get_text(separator='\n', strip=True)[500:2500])

# Reuniones que dio 0
r2 = requests.get(f"{BASE}/comisiones/permanentes/caconstitucionales/reuniones/", timeout=15, verify=False)
soup2 = BeautifulSoup(r2.text, 'html.parser')
# Ver HTML crudo de la sección de reuniones
contenido = soup2.find('div', class_=lambda x: x and 'reuni' in x.lower()) or soup2.find('section') or soup2.find('main')
if contenido:
    print("\n=== HTML REUNIONES ===")
    print(str(contenido)[:3000])
else:
    print("\n=== BODY COMPLETO ===")
    print(str(soup2.body)[:3000])