import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

r = requests.get("https://www.hcdn.gob.ar/sesiones/sesion.html?id=3576&numVid=0&reunion=1&periodo=144", timeout=15, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

# Ver título y datos básicos
print(soup.title.text if soup.title else "sin título")
print()

# Buscar datos de la sesión
for tag in soup.find_all(['h1','h2','h3','p','span'], limit=30):
    text = tag.get_text(strip=True)
    if text and len(text) > 5:
        print(text[:150])