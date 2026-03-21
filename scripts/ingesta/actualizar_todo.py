#!/usr/bin/env python3
"""
Script maestro de actualización de datos de Lobby
==================================================
Actualiza todas las fuentes de datos de forma incremental.

Uso:
    python scripts/ingesta/actualizar_todo.py [--full] [--source FUENTE]
    
Opciones:
    --full          Reingesta completa (borra y recarga)
    --source        Solo actualizar una fuente específica
    
Fuentes disponibles:
    votaciones, misiones, audiencias, personal, legisladores
"""

import os
import sys
import argparse
import requests
import pandas as pd
import re
from datetime import datetime
from io import StringIO
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Configuración de base de datos
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?sslmode=require'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def get_engine():
    return create_engine(DATABASE_URL)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ============================================
# ACTUALIZADORES POR FUENTE
# ============================================

def actualizar_misiones(engine, full=False):
    """Actualiza misiones oficiales desde datos.hcdn.gob.ar"""
    log("Actualizando misiones oficiales...")
    
    url = 'https://datos.hcdn.gob.ar/api/3/action/package_show?id=misiones-oficiales'
    r = requests.get(url, headers=HEADERS, timeout=30)
    data = r.json()
    
    if not data.get('success'):
        log("  Error obteniendo metadata")
        return 0
    
    resources = data['result'].get('resources', [])
    csv_resources = [r for r in resources if r.get('format', '').upper() == 'CSV']
    
    todos = []
    for res in csv_resources:
        try:
            csv_r = requests.get(res['url'], headers=HEADERS, timeout=60)
            if csv_r.status_code == 200:
                df = pd.read_csv(StringIO(csv_r.text), on_bad_lines='skip')
                todos.append(df)
        except:
            continue
    
    if not todos:
        log("  No se encontraron datos")
        return 0
    
    df = pd.concat(todos, ignore_index=True)
    
    # Normalizar columnas
    df_clean = pd.DataFrame()
    df_clean['fecha_inicio'] = df.get('fecha_inicio', df.get('FECHA INICIO', df.get('FECHA_INICIO', '')))
    df_clean['fecha_fin'] = df.get('fecha_fin', df.get('FECHA FIN', df.get('FECHA_FIN', '')))
    df_clean['motivo'] = df.get('motivo', df.get('MOTIVO', df.get('viaje_desc', '')))
    df_clean['institucion_invita'] = df.get('institucion_que_invita', df.get('INSTITUCION QUE INVITA', ''))
    df_clean['lugar'] = df.get('lugar', df.get('LUGAR', df.get('ciudad/pais', '')))
    df_clean['diputado'] = df.get('participa', df.get('PARTICIPA', df.get('diputado_nombre', '')))
    df_clean['viaticos'] = df.get('viaticos_otorgados', df.get('VIATICOS OTORGADOS', ''))
    df_clean = df_clean.fillna('')
    
    with engine.connect() as conn:
        if full:
            conn.execute(text("DELETE FROM misiones_oficiales"))
            conn.commit()
            df_clean.to_sql('misiones_oficiales', engine, if_exists='append', index=False)
            log(f"  {len(df_clean)} misiones ingresadas (full)")
            return len(df_clean)
        
        # Contar existentes
        result = conn.execute(text("SELECT COUNT(*) FROM misiones_oficiales"))
        existing_count = result.scalar()
    
    nuevos = len(df_clean) - existing_count
    if nuevos > 0:
        # Borrar y reingresar todo (es un dataset pequeño)
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM misiones_oficiales"))
            conn.commit()
        df_clean.to_sql('misiones_oficiales', engine, if_exists='append', index=False)
        log(f"  {nuevos} misiones nuevas (total: {len(df_clean)})")
    else:
        log("  Sin nuevas misiones")
    
    return max(0, nuevos)


def actualizar_personal_hcdn(engine, full=False):
    """Actualiza nómina de personal HCDN"""
    log("Actualizando personal HCDN...")
    
    url = 'https://datos.hcdn.gob.ar/api/3/action/package_show?id=nomina-de-personal'
    r = requests.get(url, headers=HEADERS, timeout=30)
    data = r.json()
    
    if not data.get('success'):
        log("  Error obteniendo metadata")
        return 0
    
    resources = data['result'].get('resources', [])
    csv_res = next((r for r in resources if r.get('format', '').upper() == 'CSV'), None)
    
    if not csv_res:
        log("  No se encontró CSV")
        return 0
    
    csv_r = requests.get(csv_res['url'], headers=HEADERS, timeout=60)
    df = pd.read_csv(StringIO(csv_r.text))
    
    with engine.connect() as conn:
        if full:
            conn.execute(text("DELETE FROM personal_hcdn"))
            conn.commit()
            df.to_sql('personal_hcdn', engine, if_exists='append', index=False)
            log(f"  {len(df)} empleados ingresados (full)")
            return len(df)
        
        # Comparar por legajo
        existing = pd.read_sql("SELECT legajo FROM personal_hcdn", conn)
    
    df_new = df[~df['legajo'].isin(existing['legajo'])]
    
    if len(df_new) > 0:
        df_new.to_sql('personal_hcdn', engine, if_exists='append', index=False)
        log(f"  {len(df_new)} empleados nuevos")
    else:
        log("  Sin cambios")
    
    return len(df_new)


def actualizar_audiencias_ejecutivo(engine, full=False):
    """Actualiza audiencias del Poder Ejecutivo desde datos.gob.ar"""
    log("Actualizando audiencias ejecutivo...")
    
    url = 'https://datos.gob.ar/api/3/action/package_show?id=interior-registro-unico-audiencias-gestion-intereses'
    r = requests.get(url, headers=HEADERS, timeout=30)
    data = r.json()
    
    if not data.get('success'):
        log("  Error obteniendo metadata")
        return 0
    
    resources = data['result'].get('resources', [])
    current_year = datetime.now().year
    
    # En modo incremental, solo el año actual
    if not full:
        years_to_check = [str(current_year)]
    else:
        years_to_check = None  # Todos
    
    todos = []
    for res in resources:
        name = res.get('name', '')
        fmt = res.get('format', '').upper()
        
        if fmt != 'CSV':
            continue
        
        # Filtrar por año si no es full
        if years_to_check and not any(y in name for y in years_to_check):
            continue
        
        try:
            csv_r = requests.get(res['url'], headers=HEADERS, timeout=60)
            if csv_r.status_code == 200:
                df = pd.read_csv(StringIO(csv_r.text), sep=';', encoding='latin-1', 
                               on_bad_lines='skip', low_memory=False)
                
                # Normalizar estructura
                df_clean = normalizar_audiencias(df, name)
                if df_clean is not None:
                    todos.append(df_clean)
                    log(f"    {name}: {len(df_clean)} registros")
        except Exception as e:
            log(f"    Error en {name}: {e}")
            continue
    
    if not todos:
        log("  No se encontraron datos nuevos")
        return 0
    
    df_all = pd.concat(todos, ignore_index=True)
    
    with engine.connect() as conn:
        if full:
            conn.execute(text("DELETE FROM audiencias_ejecutivo"))
            conn.commit()
        else:
            # Borrar solo el año actual para reemplazar
            conn.execute(text(f"DELETE FROM audiencias_ejecutivo WHERE anio = {current_year}"))
            conn.commit()
    
    df_all.to_sql('audiencias_ejecutivo', engine, if_exists='append', index=False, 
                  method='multi', chunksize=5000)
    log(f"  {len(df_all)} audiencias procesadas")
    
    return len(df_all)


def normalizar_audiencias(df, filename):
    """Normaliza estructura de audiencias (vieja o nueva)"""
    df_clean = pd.DataFrame()
    
    if 'apellido_sujeto_obligado' in df.columns:
        # Estructura vieja (2004-2016)
        df_clean['fecha'] = df.get('fecha_hora_audiencia', '')
        df_clean['sujeto_obligado_nombre'] = df['apellido_sujeto_obligado'].fillna('') + ', ' + df['nombre_sujeto_obligado'].fillna('')
        df_clean['sujeto_obligado_cargo'] = df.get('cargo_sujeto_obligado', '')
        df_clean['sujeto_obligado_dependencia'] = df.get('dependencia_sujeto_obligado', '')
        df_clean['solicitante_nombre'] = df['apellido_solicitante'].fillna('') + ', ' + df['nombre_solicitante'].fillna('')
        df_clean['solicitante_ocupacion'] = df.get('cargo_solicitante', '')
        df_clean['motivo'] = df.get('objeto_audiencia', '')
        df_clean['sintesis'] = df.get('sintesis_audiencia', '')
        df_clean['interes_invocado'] = df.get('interes_invocado', '')
        df_clean['lugar'] = df.get('lugar_audiencia', '')
    elif 'sujeto_obligado_nombre' in df.columns:
        # Estructura nueva (2017+)
        df_clean['fecha'] = df.get('fecha', '')
        df_clean['sujeto_obligado_nombre'] = df.get('sujeto_obligado_nombre', '')
        df_clean['sujeto_obligado_cargo'] = df.get('sujeto_obligado_cargo', '')
        df_clean['sujeto_obligado_dependencia'] = df.get('sujeto_obligado_dependencia', '')
        df_clean['solicitante_nombre'] = df.get('solicitante_nombre', '')
        df_clean['solicitante_ocupacion'] = df.get('solicitante_ocupacion', '')
        df_clean['motivo'] = df.get('motivo', '')
        df_clean['sintesis'] = df.get('sintesis', '')
        df_clean['interes_invocado'] = df.get('interes_invocado', '')
        df_clean['lugar'] = df.get('lugar', '')
    else:
        return None
    
    # Extraer año del nombre del archivo
    year_match = re.search(r'20\d{2}', filename)
    df_clean['anio'] = int(year_match.group()) if year_match else 0
    
    df_clean = df_clean.fillna('')
    
    # Truncar campos largos
    for col in ['motivo', 'sintesis', 'sujeto_obligado_dependencia']:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str[:500]
    
    return df_clean


def actualizar_votaciones(engine, full=False):
    """
    Verifica estado de votaciones HCDN.
    NOTA: El scraping se hace por separado (toma ~2.5 horas).
    """
    log("Verificando votaciones HCDN...")
    
    actas_file = 'data/votaciones_hcdn/actas_hcdn.csv'
    
    if not os.path.exists(actas_file):
        log("  Archivos no encontrados. Ejecutar: python scripts/scraping/scrapear_votaciones_hcdn.py")
        return 0
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(acta_id) FROM votaciones_hcdn"))
        max_acta_db = result.scalar() or 0
    
    df_actas = pd.read_csv(actas_file)
    max_acta_file = df_actas['acta_id'].max()
    
    if max_acta_file > max_acta_db:
        nuevas = max_acta_file - max_acta_db
        log(f"  Hay {nuevas} actas nuevas disponibles ({max_acta_db} -> {max_acta_file})")
        log("  Para actualizar DB, ejecutar script de ingesta de votaciones")
        return nuevas
    else:
        log(f"  Votaciones al día (última acta: {max_acta_db})")
    
    return 0


def actualizar_legisladores(engine, full=False):
    """Verifica estado de legisladores"""
    log("Verificando legisladores...")
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM legisladores"))
        count = result.scalar()
    
    log(f"  {count} legisladores en base")
    log("  Actualización manual requerida para cambios de mandato")
    
    return 0


def mostrar_resumen(engine):
    """Muestra resumen de la base de datos"""
    with engine.connect() as conn:
        tables = [
            ('votos_hcdn', 'Votos HCDN'),
            ('audiencias_ejecutivo', 'Audiencias Ejecutivo'),
            ('votaciones_hcdn', 'Actas votaciones'),
            ('personal_hcdn', 'Personal HCDN'),
            ('misiones_oficiales', 'Misiones oficiales'),
            ('ddjj_legisladores', 'DDJJ'),
            ('legisladores', 'Legisladores'),
        ]
        
        print("\n" + "=" * 50)
        print("ESTADO ACTUAL DE LA BASE")
        print("=" * 50)
        
        for table, desc in tables:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                print(f"  {desc}: {count:,}")
            except:
                pass


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description='Actualizar datos de Lobby')
    parser.add_argument('--full', action='store_true', help='Reingesta completa')
    parser.add_argument('--source', type=str, help='Solo actualizar una fuente')
    parser.add_argument('--status', action='store_true', help='Solo mostrar estado')
    args = parser.parse_args()
    
    print("=" * 60)
    print("ACTUALIZACION DE DATOS - LOBBY")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    engine = get_engine()
    
    if args.status:
        mostrar_resumen(engine)
        engine.dispose()
        return
    
    print(f"Modo: {'FULL' if args.full else 'INCREMENTAL'}")
    print()
    
    actualizadores = {
        'misiones': actualizar_misiones,
        'personal': actualizar_personal_hcdn,
        'audiencias': actualizar_audiencias_ejecutivo,
        'votaciones': actualizar_votaciones,
        'legisladores': actualizar_legisladores,
    }
    
    resultados = {}
    
    if args.source:
        if args.source in actualizadores:
            resultados[args.source] = actualizadores[args.source](engine, args.full)
        else:
            print(f"Fuente desconocida: {args.source}")
            print(f"Disponibles: {', '.join(actualizadores.keys())}")
            engine.dispose()
            return
    else:
        for nombre, func in actualizadores.items():
            try:
                resultados[nombre] = func(engine, args.full)
            except Exception as e:
                log(f"Error en {nombre}: {e}")
                resultados[nombre] = -1
    
    print()
    print("=" * 60)
    print("RESUMEN ACTUALIZACION")
    print("=" * 60)
    for nombre, count in resultados.items():
        status = f"{count:,} registros" if count >= 0 else "ERROR"
        print(f"  {nombre}: {status}")
    
    mostrar_resumen(engine)
    engine.dispose()
    
    print("\nCompletado!")


if __name__ == "__main__":
    main()