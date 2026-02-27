import requests
from io import BytesIO
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"
URL = f"{BASE}/parlamentario/sesiones/11-02-2026/13/downloadTac"

r = requests.get(URL, timeout=30, verify=False)
paginas = []
for i, page_layout in enumerate(extract_pages(BytesIO(r.content))):
    texto = []
    for element in page_layout:
        if isinstance(element, LTTextContainer):
            texto.append(element.get_text())
    paginas.append('\n'.join(texto))

# Buscar páginas con "ACTA" o "VOTACIÓN" en el apéndice
for i, p in enumerate(paginas):
    if any(word in p.upper() for word in ['ACTA DE VOTACIÓN', 'ACTA N°', 'AFIRMATIVO\n', 'NEGATIVO\n']):
        print(f"\n--- Página {i+1} ---")
        print(p[:1500])