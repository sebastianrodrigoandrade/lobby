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
    if i >= 5:
        break
    texto = []
    for element in page_layout:
        if isinstance(element, LTTextContainer):
            texto.append(element.get_text())
    paginas.append('\n'.join(texto))

for i, p in enumerate(paginas[:3]):
    print(f"\n--- Página {i+1} ---")
    print(p[:800])