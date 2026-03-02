import requests
import pandas as pd
from io import StringIO
from sqlalchemy import text
from src.database import SessionLocal
import warnings
warnings.filterwarnings('ignore')

url_bienes = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/ffa28585-9adb-473e-9627-0ffe1938d288/download/declaraciones-juradas-bienes-2024-consolidado-al-20251222.csv"
url_main = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/a331ccb8-5c13-447f-9bd6-d8018a4b8a62/download/ddjj-2024-12-22.csv"

CARGOS_ELECTOS = {
    'DIPUTADO NACIONAL', 'DIPUTADA NACIONAL', 'SENADOR NACIONAL', 'SENADORA NACIONAL',
    'DIPUTADO DE LA NACION', 'DIPUTADA DE LA NACION',
    'DIPUTADA DE LA NACION ARGENTINA', 'DIPUTADO DE LA NACION ARGENTINA'
}

print("Descargando CSV principal...")
r2 = requests.get(url_main, timeout=60, verify=False)
df_main = pd.read_csv(StringIO(r2.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
df_main.columns = df_main.columns.str.strip().str.lstrip('\ufeff')
leg = df_main[df_main['cargo'].str.upper().str.strip().isin(CARGOS_ELECTOS)]
cuits_leg = set(leg['cuit'].astype(str).str.replace('.0','').str.strip())

print("Descargando CSV de bienes (182MB)...")
r = requests.get(url_bienes, timeout=180, verify=False)
df = pd.read_csv(StringIO(r.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
df.columns = df.columns.str.strip()
df['bien_importe'] = pd.to_numeric(df['bien_importe'], errors='coerce').fillna(0)
df['cuit_str'] = df['cuit'].astype(str).str.replace('.0','').str.strip()
df_leg = df[df['cuit_str'].isin(cuits_leg)].copy()
print(f"Bienes de legisladores: {len(df_leg)}")

db = SessionLocal()
try:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS ddjj_bienes (
            id SERIAL PRIMARY KEY,
            dj_id INTEGER,
            cuit VARCHAR,
            anio INTEGER,
            funcionario_apellido_nombre VARCHAR,
            bien_tipo VARCHAR,
            bien_descripcion TEXT,
            bien_origen_fondos VARCHAR,
            bien_titularidad VARCHAR,
            bien_importe NUMERIC,
            legislador_id INTEGER REFERENCES legisladores(id)
        )
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_bienes_cuit ON ddjj_bienes(cuit)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_bienes_legislador ON ddjj_bienes(legislador_id)"))
    db.execute(text("DELETE FROM ddjj_bienes WHERE anio = 2024"))
    db.commit()

    # Cruzar con legisladores por cuit
    result = db.execute(text("SELECT id, cuit FROM ddjj_legisladores WHERE cuit IS NOT NULL"))
    cuit_to_id = {str(row[1]).strip(): row[0] for row in result.fetchall()}

    insertados = 0
    batch = []
    for _, row in df_leg.iterrows():
        cuit = str(row.get('cuit','')).replace('.0','').strip()
        batch.append({
            'dj_id': int(row.get('dj_id', 0) or 0),
            'cuit': cuit,
            'anio': 2024,
            'nombre': str(row.get('funcionario_apellido_nombre','')).strip(),
            'tipo': str(row.get('bien_tipo','')).strip(),
            'desc': str(row.get('bien_descripcion','')).strip(),
            'origen': str(row.get('bien_origen_fondos','')).strip(),
            'titularidad': str(row.get('bien_titularidad','')).strip(),
            'importe': float(row['bien_importe']),
            'leg_id': cuit_to_id.get(cuit),
        })
        if len(batch) >= 500:
            db.execute(text("""
                INSERT INTO ddjj_bienes (dj_id, cuit, anio, funcionario_apellido_nombre,
                    bien_tipo, bien_descripcion, bien_origen_fondos, bien_titularidad,
                    bien_importe, legislador_id)
                VALUES (:dj_id, :cuit, :anio, :nombre, :tipo, :desc, :origen,
                    :titularidad, :importe, :leg_id)
            """), batch)
            db.commit()
            insertados += len(batch)
            batch = []
            print(f"  {insertados} insertados...")

    if batch:
        db.execute(text("""
            INSERT INTO ddjj_bienes (dj_id, cuit, anio, funcionario_apellido_nombre,
                bien_tipo, bien_descripcion, bien_origen_fondos, bien_titularidad,
                bien_importe, legislador_id)
            VALUES (:dj_id, :cuit, :anio, :nombre, :tipo, :desc, :origen,
                :titularidad, :importe, :leg_id)
        """), batch)
        db.commit()
        insertados += len(batch)

    print(f"\nTotal insertados: {insertados}")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()