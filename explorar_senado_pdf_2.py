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

print(f"Total páginas: {len(paginas)}")

# Buscar páginas que contengan votos
for i, p in enumerate(paginas):
    if any(word in p.upper() for word in ['AFIRMATIVO', 'NEGATIVO', 'ABSTENCIÓN', 'AUSENTE', 'VOTACIÓN']):
        print(f"\n--- Página {i+1} ---")
        print(p[:1000])
        if i > 20:  # mostrar hasta 5 páginas con votos
            break