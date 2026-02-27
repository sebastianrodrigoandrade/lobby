import requests
import pandas as pd
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

# Buscar en el histórico consolidado 2012-2023
url = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/a331ccb8-5c13-447f-9bd6-d8018a4b8a62/download/ddjj-2024-12-22.csv"

# Buscar en TODOS los registros del CSV (no solo electos)
r = requests.get(url, timeout=60, verify=False)
df = pd.read_csv(StringIO(r.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
df.columns = df.columns.str.strip().str.lstrip('\ufeff')

for nombre in ['BREGMAN', 'GRABOIS', 'LEMOINE', 'BULLRICH PATRICIA']:
    found = df[df['funcionario_apellido_nombre'].str.contains(nombre, case=False, na=False)]
    print(f"\n{nombre} ({len(found)} registros):")
    if len(found):
        print(found[['funcionario_apellido_nombre', 'organismo', 'cargo', 'anio']].drop_duplicates().to_string())