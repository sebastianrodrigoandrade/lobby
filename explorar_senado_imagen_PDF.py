import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"

# Buscar el ID más bajo disponible probando hacia atrás
for acta_id in [1, 100, 500, 1000, 1500, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2623]:
    r = requests.get(f"{BASE}/votaciones/detalleActa/{acta_id}", timeout=10, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')
    texto = soup.get_text(separator=' ', strip=True)
    tiene_datos = 'Senador' in texto or 'AFIRMATIVO' in texto or 'NEGATIVO' in texto
    print(f"ID {acta_id}: status={r.status_code} datos={tiene_datos}")