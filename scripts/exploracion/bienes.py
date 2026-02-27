import requests
import pandas as pd
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

url = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/ffa28585-9adb-473e-9627-0ffe1938d288/download/declaraciones-juradas-bienes-2024-consolidado-al-20251222.csv"

print("Descargando CSV de bienes (182MB)...")
r = requests.get(url, timeout=120, verify=False)

df = pd.read_csv(StringIO(r.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
df.columns = df.columns.str.strip()
print(f"Total filas: {len(df)}")

# Limpiar importe
df['bien_importe'] = pd.to_numeric(df['bien_importe'], errors='coerce').fillna(0)

# CUITs de nuestros legisladores (los que tenemos en ddjj_legisladores)
# Los obtenemos del CSV principal que ya procesamos antes
url_main = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/a331ccb8-5c13-447f-9bd6-d8018a4b8a62/download/ddjj-2024-12-22.csv"
r2 = requests.get(url_main, timeout=60, verify=False)
df_main = pd.read_csv(StringIO(r2.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
df_main.columns = df_main.columns.str.strip().str.lstrip('\ufeff')

CARGOS_ELECTOS = {
    'DIPUTADO NACIONAL', 'DIPUTADA NACIONAL', 'SENADOR NACIONAL', 'SENADORA NACIONAL',
    'DIPUTADO DE LA NACION', 'DIPUTADA DE LA NACION',
    'DIPUTADA DE LA NACION ARGENTINA', 'DIPUTADO DE LA NACION ARGENTINA'
}
leg = df_main[df_main['cargo'].str.upper().str.strip().isin(CARGOS_ELECTOS)]
cuits_leg = set(leg['cuit'].astype(str).str.replace('.0','').str.strip())
print(f"CUITs de legisladores: {len(cuits_leg)}")

# Filtrar bienes solo de legisladores
df['cuit_str'] = df['cuit'].astype(str).str.replace('.0','').str.strip()
df_leg = df[df['cuit_str'].isin(cuits_leg)].copy()
print(f"Bienes de legisladores: {len(df_leg)}")

# Top 3 bienes por legislador
df_leg_sorted = df_leg.sort_values(['funcionario_apellido_nombre', 'bien_importe'], ascending=[True, False])
top3 = df_leg_sorted.groupby('funcionario_apellido_nombre').head(3)
print(f"\nEjemplo Kirchner:")
kirchner = top3[top3['funcionario_apellido_nombre'].str.contains('KIRCHNER', case=False, na=False)]
print(kirchner[['funcionario_apellido_nombre', 'bien_tipo', 'bien_descripcion', 'bien_importe']].to_string())