import requests
import re
from io import BytesIO
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

BASE_URL = "https://www3.hcdn.gob.ar/dependencias/dtaquigrafos/diarios"

sesiones = [
    {'url': f"{BASE_URL}/periodo-141/diario_2024013112.pdf", 'fecha': '2024-01-31', 'reunion': 12, 'periodo': 141, 'periodo_id': 'HCDN141R12'},
    {'url': f"{BASE_URL}/periodo-141/diario_2024020113.pdf", 'fecha': '2024-02-01', 'reunion': 13, 'periodo': 141, 'periodo_id': 'HCDN141R13'},
    {'url': f"{BASE_URL}/periodo-141/diario_2024020214.pdf", 'fecha': '2024-02-02', 'reunion': 14, 'periodo': 141, 'periodo_id': 'HCDN141R14'},
    {'url': f"{BASE_URL}/periodo-141/diario_2024020615.pdf", 'fecha': '2024-02-06', 'reunion': 15, 'periodo': 141, 'periodo_id': 'HCDN141R15'},
    {'url': f"{BASE_URL}/periodo-142/diario_2025020621.pdf", 'fecha': '2025-02-06', 'reunion': 21, 'periodo': 142, 'periodo_id': 'HCDN142R21'},
    {'url': f"{BASE_URL}/periodo-142/diario_2025021222.pdf", 'fecha': '2025-02-12', 'reunion': 22, 'periodo': 142, 'periodo_id': 'HCDN142R22'},
]

def extraer_paginas(pdf_bytes, max_paginas=8):
    """Extrae texto página por página, devuelve lista de strings."""
    paginas = []
    for i, page_layout in enumerate(extract_pages(BytesIO(pdf_bytes))):
        if i >= max_paginas:
            break
        texto_pagina = []
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                texto_pagina.append(element.get_text())
        paginas.append('\n'.join(texto_pagina))
    return paginas

def encontrar_sumario(paginas):
    """
    Busca la página que contiene el sumario numerado.
    El sumario tiene líneas como "1. Apertura..." o "1. Proyecto de ley..."
    """
    patron_item = re.compile(r'^\s*\d+\.\s+\w', re.MULTILINE)
    
    for i, pagina in enumerate(paginas):
        matches = patron_item.findall(pagina)
        if len(matches) >= 3:  # página con al menos 3 items numerados = es el sumario
            return i, pagina
    return None, None

def parsear_sumario(texto):
    """Extrae items numerados del sumario."""
    patron = re.compile(
        r'(\d+)\.\s+'
        r'(.+?)'
        r'(?=\n\s*\d+\.\s+|\Z)',
        re.DOTALL
    )
    items = []
    for match in patron.finditer(texto):
        nro = match.group(1)
        contenido = ' '.join(match.group(2).split())
        if len(contenido) > 10:  # filtrar items vacíos
            items.append({'item': nro, 'descripcion': contenido[:500]})
    return items

resultados = []

for s in sesiones:
    print(f"\n{'='*60}")
    print(f"=== {s['fecha']} - Reunión {s['reunion']} ===")
    print(f"{'='*60}")
    try:
        r = requests.get(s['url'], timeout=60)
        r.raise_for_status()
        
        paginas = extraer_paginas(r.content, max_paginas=10)
        print(f"Paginas extraidas: {len(paginas)}")
        
        nro_pagina, pagina_sumario = encontrar_sumario(paginas)
        
        if pagina_sumario:
            print(f"Sumario encontrado en pagina {nro_pagina + 1}")
            items = parsear_sumario(pagina_sumario)
            print(f"Items: {len(items)}")
            for item in items[:8]:
                print(f"  {item['item']}. {item['descripcion'][:120]}")
            
            for item in items:
                resultados.append({
                    'periodo_id': s['periodo_id'],
                    'fecha': s['fecha'],
                    'reunion': s['reunion'],
                    'periodo': s['periodo'],
                    'item_nro': item['item'],
                    'descripcion': item['descripcion']
                })
        else:
            print("Sumario no encontrado - mostrando todas las paginas:")
            for i, p in enumerate(paginas):
                print(f"\n--- Pagina {i+1} ---")
                print(p[:500])

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if resultados:
    df = pd.DataFrame(resultados)
    df.to_csv('temario_extraordinarias.csv', index=False, encoding='utf-8-sig')
    print(f"\nExportado: temario_extraordinarias.csv ({len(resultados)} items)")

print("\n=== DONE ===")