# -*- coding: utf-8 -*-
"""
Descarga e ingesta DDJJ historicas desde datos.jus.gob.ar
"""
import pandas as pd
import requests
import zipfile
import io
import os
from sqlalchemy import text
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.database import SessionLocal

load_dotenv()

# URLs actualizadas (formato ZIP)
URLS_DDJJ = {
    2023: "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/15b9566d-f5b6-4bd1-a60b-fa9040fc0c2b/download/declaraciones-juradas-2023.zip",
    2022: "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/43c3cf87-b78f-4dd5-a821-686999d42231/download/declaraciones-juradas-2022.zip",
    2021: "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/eef25e9d-695b-4158-9bad-645a304efbec/download/declaraciones-juradas-2021.zip",
    2020: "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/b15c957b-f98c-4298-ac87-514af3f1d47f/download/declaraciones-juradas-2020.zip",
    2019: "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/34af5875-e7fa-47d7-82a3-c4eb68d4b60b/download/declaraciones-juradas-2019.zip",
}

def descargar_zip(url, anio):
    """Descarga ZIP y extrae el CSV principal."""
    print(f"Descargando DDJJ {anio}...")
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        
        # Abrir ZIP en memoria
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            # Listar archivos
            archivos = zf.namelist()
            print(f"  Archivos en ZIP: {archivos}")
            
            # Buscar el CSV principal (consolidado, no bienes/deudas/familiar)
            csv_principal = None
            for archivo in archivos:
                if archivo.endswith('.csv'):
                    nombre_lower = archivo.lower()
                    if 'bienes' not in nombre_lower and 'deudas' not in nombre_lower and 'familiar' not in nombre_lower:
                        csv_principal = archivo
                        break
            
            if not csv_principal:
                # Si no hay filtrado, tomar el primero
                csv_principal = [a for a in archivos if a.endswith('.csv')][0] if archivos else None
            
            if csv_principal:
                print(f"  Usando: {csv_principal}")
                with zf.open(csv_principal) as f:
                    # Intentar diferentes encodings
                    content = f.read()
                    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                        try:
                            df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                            print(f"  Registros: {len(df)}")
                            return df
                        except UnicodeDecodeError:
                            continue
                        except Exception as e:
                            print(f"  Error leyendo CSV: {e}")
                            continue
        return None
    except Exception as e:
        print(f"  Error descargando {anio}: {e}")
        return None

def filtrar_legisladores(df, anio):
    """Filtra solo legisladores (HCDN y Senado)."""
    df.columns = df.columns.str.lower().str.strip()
    
    # Buscar columna de organismo
    col_organismo = None
    for col in ['organismo', 'organismo_nombre', 'dependencia', 'organismo_pertenencia']:
        if col in df.columns:
            col_organismo = col
            break
    
    if not col_organismo:
        print(f"  Columnas disponibles: {list(df.columns)}")
        print(f"  No se encontro columna de organismo en {anio}")
        return pd.DataFrame()
    
    # Filtrar por HCDN y Senado
    mask = df[col_organismo].str.contains('DIPUTADOS|SENADO|H\\.? ?CONGRESO|HONORABLE CONGRESO', case=False, na=False, regex=True)
    df_leg = df[mask].copy()
    print(f"  Legisladores encontrados: {len(df_leg)}")
    
    return df_leg

def safe_float(val):
    """Convierte a float de forma segura."""
    try:
        if pd.isna(val):
            return None
        s = str(val).replace(',', '.').replace('$', '').replace(' ', '').strip()
        if s == '' or s == '-' or s.lower() == 'nan':
            return None
        return float(s)
    except:
        return None

def ingestar_ddjj(df, anio, db):
    """Ingesta DDJJ a la base de datos."""
    df.columns = df.columns.str.lower().str.strip()
    
    # Mapear columnas posibles
    def get_col(df, opciones):
        for col in opciones:
            if col in df.columns:
                return col
        return None
    
    col_cuit = get_col(df, ['cuit', 'cuit_funcionario', 'cuil'])
    col_nombre = get_col(df, ['apellido_nombre', 'funcionario_apellido_nombre', 'nombre_apellido', 'apellido_y_nombre'])
    col_organismo = get_col(df, ['organismo', 'organismo_nombre', 'dependencia', 'organismo_pertenencia'])
    col_cargo = get_col(df, ['cargo', 'cargo_nombre', 'funcion', 'cargo_funcion'])
    col_bienes = get_col(df, ['total_bienes', 'bienes_total', 'total_activo', 'totalbienes'])
    col_deudas = get_col(df, ['total_deudas', 'deudas_total', 'total_pasivo', 'totaldeudas'])
    col_patrimonio = get_col(df, ['patrimonio_neto', 'patrimonio', 'patrimonioneto'])
    col_ingresos = get_col(df, ['ingresos_neto_gastos', 'ingresos_totales', 'total_ingresos', 'ingresos', 'ingresosnetodegastos'])
    
    if not col_cuit:
        print(f"  No se encontro columna CUIT. Columnas: {list(df.columns)}")
        return 0, 0
    
    insertados = 0
    actualizados = 0
    
    for _, row in df.iterrows():
        try:
            cuit = str(row.get(col_cuit, '')).replace('-', '').replace('.', '').strip()
            if not cuit or cuit == 'nan' or len(cuit) < 8:
                continue
            
            # Buscar legislador por CUIT
            result = db.execute(text("SELECT id FROM legisladores WHERE dni_cuit = :cuit"), {'cuit': cuit})
            leg = result.fetchone()
            legislador_id = leg[0] if leg else None
            
            # Verificar si ya existe
            result = db.execute(text("SELECT id FROM ddjj_legisladores WHERE cuit = :cuit AND anio = :anio"), 
                              {'cuit': cuit, 'anio': anio})
            existe = result.fetchone()
            
            nombre = row.get(col_nombre) if col_nombre else None
            organismo = row.get(col_organismo) if col_organismo else None
            cargo = row.get(col_cargo) if col_cargo else None
            bienes = safe_float(row.get(col_bienes)) if col_bienes else None
            deudas = safe_float(row.get(col_deudas)) if col_deudas else None
            patrimonio = safe_float(row.get(col_patrimonio)) if col_patrimonio else None
            ingresos = safe_float(row.get(col_ingresos)) if col_ingresos else None
            
            # Si no hay patrimonio pero hay bienes y deudas, calcular
            if patrimonio is None and bienes is not None and deudas is not None:
                patrimonio = bienes - deudas
            
            if existe:
                db.execute(text("""
                    UPDATE ddjj_legisladores SET
                        legislador_id = COALESCE(:leg_id, legislador_id),
                        funcionario_apellido_nombre = COALESCE(:nombre, funcionario_apellido_nombre),
                        organismo = COALESCE(:organismo, organismo),
                        cargo = COALESCE(:cargo, cargo),
                        total_bienes = COALESCE(:bienes, total_bienes),
                        total_deudas = COALESCE(:deudas, total_deudas),
                        patrimonio_neto = COALESCE(:patrimonio, patrimonio_neto),
                        ingresos_neto_gastos = COALESCE(:ingresos, ingresos_neto_gastos)
                    WHERE cuit = :cuit AND anio = :anio
                """), {
                    'leg_id': legislador_id, 'nombre': nombre, 'organismo': organismo,
                    'cargo': cargo, 'bienes': bienes, 'deudas': deudas,
                    'patrimonio': patrimonio, 'ingresos': ingresos,
                    'cuit': cuit, 'anio': anio
                })
                actualizados += 1
            else:
                db.execute(text("""
                    INSERT INTO ddjj_legisladores 
                    (legislador_id, cuit, anio, funcionario_apellido_nombre, organismo, cargo,
                     total_bienes, total_deudas, patrimonio_neto, ingresos_neto_gastos)
                    VALUES (:leg_id, :cuit, :anio, :nombre, :organismo, :cargo,
                            :bienes, :deudas, :patrimonio, :ingresos)
                """), {
                    'leg_id': legislador_id, 'cuit': cuit, 'anio': anio,
                    'nombre': nombre, 'organismo': organismo, 'cargo': cargo,
                    'bienes': bienes, 'deudas': deudas,
                    'patrimonio': patrimonio, 'ingresos': ingresos,
                })
                insertados += 1
                
        except Exception as e:
            continue
    
    db.commit()
    return insertados, actualizados

def main():
    db = SessionLocal()
    
    print("=" * 60)
    print("INGESTA DE DDJJ HISTORICAS")
    print("=" * 60)
    
    for anio in sorted(URLS_DDJJ.keys()):
        url = URLS_DDJJ[anio]
        print(f"\n--- Procesando {anio} ---")
        
        df = descargar_zip(url, anio)
        if df is None or df.empty:
            print(f"  Saltando {anio} - sin datos")
            continue
        
        df_leg = filtrar_legisladores(df, anio)
        if df_leg.empty:
            print(f"  Saltando {anio} - sin legisladores")
            continue
        
        insertados, actualizados = ingestar_ddjj(df_leg, anio, db)
        print(f"  Resultado: {insertados} insertados, {actualizados} actualizados")
    
    # Estadisticas finales
    print("\n" + "=" * 60)
    print("DDJJ POR AÑO EN LA BASE:")
    result = db.execute(text("""
        SELECT anio, COUNT(*) FROM ddjj_legisladores GROUP BY anio ORDER BY anio
    """))
    for r in result:
        print(f"  {r[0]}: {r[1]} registros")
    
    db.close()
    print("\nProceso completado.")

if __name__ == "__main__":
    main()
