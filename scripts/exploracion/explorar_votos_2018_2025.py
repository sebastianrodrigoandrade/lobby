import requests
from pdfminer.high_level import extract_text
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

url = "https://www3.hcdn.gob.ar/dependencias/dtaquigrafos/diarios/periodo-143/diario_2026021922.pdf"
r = requests.get(url, timeout=60, verify=False)
texto = extract_text(BytesIO(r.content))

# Ver los últimos 5000 chars
print("=== FINAL DEL PDF ===")
print(texto[-5000:])