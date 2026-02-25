import requests
import pandas as pd
from io import StringIO
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import warnings
warnings.filterwarnings('ignore')

URL_DDJJ = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/a331ccb8-5c13-447f-9bd6-d8018a4b8a62/download/ddjj-2024-12-22.csv"

CARGOS_ELECTOS = {
    'DIPUTADO NACIONAL', 'DIPUTADA NACIONAL', 'SENADOR NACIONAL', 'SENADORA NACIONAL',
    'DIPUTADO DE LA NACION', 'DIPUTADA DE LA NACION',
    'DIPUTADA DE LA NACION ARGENTINA', 'DIPUTADO DE LA NACION ARGENTINA'
}

def limpiar_monto(val):
    if pd.isna(val) or str(val).strip() in ['-00', '', '---']:
        return 0.0
    try:
        return float(str(val).strip().replace('-', '.'))
    except:
        return 0.0

def crear_tabla(session):
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS ddjj_legisladores (
            id SERIAL PRIMARY KEY,
            legislador_id INTEGER REFERENCES legisladores(id),
            cuit VARCHAR,
            anio INTEGER,
            funcionario_apellido_nombre VARCHAR,
            organismo VARCHAR,
            cargo VARCHAR,
            total_bienes NUMERIC,
            total_deudas NUMERIC,
            patrimonio_neto NUMERIC,
            ingresos_neto_gastos NUMERIC,
            proveedor_contratista VARCHAR,
            tipo_declaracion VARCHAR,
            rectificativa BOOLEAN,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_ddjj_legislador ON ddjj_legisladores(legislador_id)"))
    session.commit()
    logger.info("Tabla ddjj_legisladores creada/verificada")

def cruzar_legislador(session, apellido_nombre):
    """Cruzar por apellido con tabla legisladores."""
    # El formato es 'APELLIDO NOMBRE' — tomamos primera palabra como apellido
    partes = apellido_nombre.strip().split()
    if not partes:
        return None
    apellido = partes[0]
    
    result = session.execute(text("""
        SELECT id FROM legisladores 
        WHERE nombre_completo ILIKE :apellido
        LIMIT 1
    """), {"apellido": f"%{apellido}%"})
    row = result.fetchone()
    return row[0] if row else None

def main():
    logger.info("=== INGESTA DDJJ LEGISLADORES ===")
    
    logger.info("Descargando CSV...")
    r = requests.get(URL_DDJJ, timeout=120, verify=False)
    df = pd.read_csv(StringIO(r.text), sep=',', encoding='utf-8-sig', on_bad_lines='skip')
    logger.info(f"Total registros: {len(df)}")

    # Filtrar legisladores electos
    leg = df[df['organismo'].str.contains('DIPUTADOS|SENADO', case=False, na=False)]
    electos = leg[leg['cargo'].str.upper().str.strip().isin(CARGOS_ELECTOS)].copy()
    logger.info(f"Legisladores electos: {len(electos)}")

    # Limpiar montos
    for col in ['total_bienes_final', 'total_deudas_final', 'ingresos_neto_gastos']:
        electos[col] = electos[col].apply(limpiar_monto)
    electos['patrimonio_neto'] = electos['total_bienes_final'] - electos['total_deudas_final']

    session = SessionLocal()
    try:
        crear_tabla(session)
        
        # Limpiar datos previos del año
        session.execute(text("DELETE FROM ddjj_legisladores WHERE anio = 2024"))
        session.commit()

        insertados = 0
        sin_match = []

        for _, row in electos.iterrows():
            nombre = str(row['funcionario_apellido_nombre']).strip()
            leg_id = cruzar_legislador(session, nombre)
            
            if not leg_id:
                sin_match.append(nombre)

            session.execute(text("""
                INSERT INTO ddjj_legisladores (
                    legislador_id, cuit, anio, funcionario_apellido_nombre,
                    organismo, cargo, total_bienes, total_deudas,
                    patrimonio_neto, ingresos_neto_gastos,
                    proveedor_contratista, tipo_declaracion, rectificativa
                ) VALUES (
                    :leg_id, :cuit, :anio, :nombre,
                    :organismo, :cargo, :bienes, :deudas,
                    :patrimonio, :ingresos,
                    :proveedor, :tipo, :rectif
                )
            """), {
                'leg_id': leg_id,
                'cuit': str(row.get('cuit', '')),
                'anio': int(row.get('anio', 2024)),
                'nombre': nombre,
                'organismo': str(row.get('organismo', '')),
                'cargo': str(row.get('cargo', '')),
                'bienes': float(row['total_bienes_final']),
                'deudas': float(row['total_deudas_final']),
                'patrimonio': float(row['patrimonio_neto']),
                'ingresos': float(row.get('ingresos_neto_gastos', 0) or 0),
                'proveedor': str(row.get('proveedor_contratista', '')),
                'tipo': str(row.get('tipo_declaracion_jurada_descripcion', '')),
                'rectif': bool(row.get('rectificativa', 0)),
            })
            insertados += 1

        session.commit()
        logger.info(f"Insertados: {insertados}")
        logger.info(f"Sin match con legisladores ({len(sin_match)}): {sin_match[:10]}")

    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()