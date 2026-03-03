"""
Ingesta de Causas de Corrupción a PostgreSQL
=============================================

Este script crea las tablas necesarias e ingesta los datos
scrapeados de causas de corrupción.

Uso:
    python ingestar_causas.py
"""

import os
import json
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


def crear_tablas():
    """Crea las tablas para causas judiciales"""
    
    sql = """
    -- Tabla principal de causas de corrupción
    CREATE TABLE IF NOT EXISTS causas_corrupcion (
        id SERIAL PRIMARY KEY,
        expediente VARCHAR(100),
        caratula TEXT,
        delitos TEXT,
        estado VARCHAR(100),
        juzgado VARCHAR(300),
        fiscal VARCHAR(300),
        fecha_inicio DATE,
        fecha_ultimo_movimiento DATE,
        url TEXT,
        fuente VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabla de personas involucradas en causas
    CREATE TABLE IF NOT EXISTS causas_personas (
        id SERIAL PRIMARY KEY,
        causa_id INT REFERENCES causas_corrupcion(id),
        nombre_raw TEXT,
        rol VARCHAR(50),  -- imputado, denunciante, querellante, etc.
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabla de cruce causas-legisladores
    CREATE TABLE IF NOT EXISTS causas_legisladores (
        id SERIAL PRIMARY KEY,
        legislador_id INT REFERENCES legisladores(id),
        causa_id INT REFERENCES causas_corrupcion(id),
        nombre_en_causa TEXT,
        rol VARCHAR(50),
        match_score FLOAT,
        verificado BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(legislador_id, causa_id)
    );
    
    -- Tabla de causas civiles/comerciales (del SCW)
    CREATE TABLE IF NOT EXISTS causas_civiles (
        id SERIAL PRIMARY KEY,
        expediente VARCHAR(100),
        caratula TEXT,
        juzgado VARCHAR(300),
        fecha DATE,
        jurisdiccion VARCHAR(100),
        fuente VARCHAR(50) DEFAULT 'scw_pjn',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Cruce causas civiles con legisladores
    CREATE TABLE IF NOT EXISTS causas_civiles_legisladores (
        id SERIAL PRIMARY KEY,
        legislador_id INT REFERENCES legisladores(id),
        causa_id INT REFERENCES causas_civiles(id),
        rol VARCHAR(50),  -- actor, demandado, tercero
        match_score FLOAT,
        verificado BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(legislador_id, causa_id)
    );
    
    -- Índices
    CREATE INDEX IF NOT EXISTS idx_causas_corrupcion_expediente ON causas_corrupcion(expediente);
    CREATE INDEX IF NOT EXISTS idx_causas_legisladores_leg ON causas_legisladores(legislador_id);
    CREATE INDEX IF NOT EXISTS idx_causas_civiles_exp ON causas_civiles(expediente);
    """
    
    with engine.connect() as conn:
        for statement in sql.split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
    
    print("✓ Tablas creadas correctamente")


def ingestar_desde_json(filepath):
    """Ingesta causas desde un archivo JSON"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    causas = data.get('causas', [])
    matches = data.get('matches', [])
    
    print(f"Procesando {len(causas)} causas y {len(matches)} matches...")
    
    with engine.connect() as conn:
        # Ingestar causas
        for causa in causas:
            if causa.get('fuente') == 'archivo_cij':
                sql = """
                INSERT INTO causas_corrupcion (expediente, caratula, url, fuente)
                VALUES (:expediente, :caratula, :url, :fuente)
                ON CONFLICT DO NOTHING
                """
                conn.execute(text(sql), {
                    'expediente': causa.get('expediente', ''),
                    'caratula': causa.get('caratula', ''),
                    'url': causa.get('url', ''),
                    'fuente': 'archivo_cij'
                })
            
            elif causa.get('fuente') == 'scw_pjn':
                sql = """
                INSERT INTO causas_civiles (expediente, caratula, juzgado, jurisdiccion)
                VALUES (:expediente, :caratula, :juzgado, :jurisdiccion)
                ON CONFLICT DO NOTHING
                """
                conn.execute(text(sql), {
                    'expediente': causa.get('expediente', ''),
                    'caratula': causa.get('caratula', ''),
                    'juzgado': causa.get('juzgado', ''),
                    'jurisdiccion': causa.get('jurisdiccion', '')
                })
        
        # Ingestar matches
        for match in matches:
            sql = """
            INSERT INTO causas_legisladores (
                legislador_id, nombre_en_causa, match_score
            )
            SELECT :leg_id, :nombre_causa, :score
            WHERE EXISTS (SELECT 1 FROM legisladores WHERE id = :leg_id)
            ON CONFLICT DO NOTHING
            """
            conn.execute(text(sql), {
                'leg_id': match.get('legislador_id'),
                'nombre_causa': match.get('nombre_en_causa', ''),
                'score': match.get('match_score', 0)
            })
        
        conn.commit()
    
    print(f"✓ Ingesta completada")


def ingestar_desde_csv(filepath):
    """Ingesta causas desde un archivo CSV"""
    
    df = pd.read_csv(filepath)
    print(f"Procesando {len(df)} registros...")
    
    with engine.connect() as conn:
        for _, row in df.iterrows():
            sql = """
            INSERT INTO causas_corrupcion (
                expediente, caratula, delitos, estado, juzgado, fiscal, fuente
            )
            VALUES (:expediente, :caratula, :delitos, :estado, :juzgado, :fiscal, :fuente)
            ON CONFLICT DO NOTHING
            """
            conn.execute(text(sql), {
                'expediente': row.get('expediente', ''),
                'caratula': row.get('caratula', ''),
                'delitos': row.get('delitos', ''),
                'estado': row.get('estado', ''),
                'juzgado': row.get('juzgado', ''),
                'fiscal': row.get('fiscal', ''),
                'fuente': row.get('fuente', 'manual')
            })
        
        conn.commit()
    
    print(f"✓ Ingesta completada")


def insertar_causas_conocidas():
    """
    Inserta manualmente las causas más conocidas de legisladores
    mientras conseguimos la base completa
    """
    
    causas_conocidas = [
        {
            'expediente': 'CFP 5048/2016',
            'caratula': 'KIRCHNER, CRISTINA ELISABET Y OTROS S/ LAVADO DE ACTIVOS',
            'delitos': 'LAVADO DE ACTIVOS',
            'estado': 'EN TRAMITE',
            'juzgado': 'JUZGADO CRIMINAL Y CORRECCIONAL FEDERAL 10',
            'personas': ['KIRCHNER, CRISTINA ELISABET']
        },
        {
            'expediente': 'CFP 9608/2018',
            'caratula': 'KIRCHNER, CRISTINA ELISABET Y OTROS S/ COHECHO Y TRAFICO DE INFLUENCIAS',
            'delitos': 'COHECHO, TRAFICO DE INFLUENCIAS',
            'estado': 'CONDENA',
            'juzgado': 'TRIBUNAL ORAL FEDERAL 2',
            'personas': ['KIRCHNER, CRISTINA ELISABET', 'DE VIDO, JULIO MIGUEL']
        },
        {
            'expediente': 'CFP 5896/2014',
            'caratula': 'DE VIDO, JULIO MIGUEL Y OTROS S/ DEFRAUDACION CONTRA LA ADMINISTRACION PUBLICA',
            'delitos': 'DEFRAUDACION CONTRA LA ADMINISTRACION PUBLICA',
            'estado': 'CONDENA',
            'juzgado': 'TRIBUNAL ORAL FEDERAL',
            'personas': ['DE VIDO, JULIO MIGUEL', 'JAIME, RICARDO RAUL']
        },
        {
            'expediente': 'CFP 4943/2016',
            'caratula': 'MACRI, MAURICIO Y OTROS S/ DEFRAUDACION',
            'delitos': 'DEFRAUDACION',
            'estado': 'EN TRAMITE',
            'juzgado': 'JUZGADO CRIMINAL Y CORRECCIONAL FEDERAL',
            'personas': ['MACRI, MAURICIO']
        },
        {
            'expediente': 'CFP 3017/2013',
            'caratula': 'BOUDOU, AMADO Y OTROS S/ COHECHO',
            'delitos': 'COHECHO, NEGOCIACIONES INCOMPATIBLES',
            'estado': 'CONDENA FIRME',
            'juzgado': 'TRIBUNAL ORAL FEDERAL 4',
            'personas': ['BOUDOU, AMADO']
        },
        {
            'expediente': 'FSM 17102/2018',
            'caratula': 'BAEZ, LAZARO Y OTROS S/ LAVADO DE ACTIVOS',
            'delitos': 'LAVADO DE ACTIVOS',
            'estado': 'CONDENA',
            'juzgado': 'TRIBUNAL ORAL FEDERAL',
            'personas': ['BAEZ, LAZARO ANTONIO']
        },
    ]
    
    with engine.connect() as conn:
        for causa in causas_conocidas:
            # Insertar causa
            sql = """
            INSERT INTO causas_corrupcion (
                expediente, caratula, delitos, estado, juzgado, fuente
            )
            VALUES (:expediente, :caratula, :delitos, :estado, :juzgado, 'manual')
            ON CONFLICT DO NOTHING
            RETURNING id
            """
            result = conn.execute(text(sql), {
                'expediente': causa['expediente'],
                'caratula': causa['caratula'],
                'delitos': causa['delitos'],
                'estado': causa['estado'],
                'juzgado': causa['juzgado']
            })
            
            # Obtener ID de la causa
            row = result.fetchone()
            if row:
                causa_id = row[0]
                
                # Insertar personas
                for persona in causa['personas']:
                    sql_persona = """
                    INSERT INTO causas_personas (causa_id, nombre_raw, rol)
                    VALUES (:causa_id, :nombre, 'imputado')
                    ON CONFLICT DO NOTHING
                    """
                    conn.execute(text(sql_persona), {
                        'causa_id': causa_id,
                        'nombre': persona
                    })
        
        conn.commit()
    
    print(f"✓ Insertadas {len(causas_conocidas)} causas conocidas")


def main():
    print("=" * 60)
    print("INGESTA DE CAUSAS JUDICIALES")
    print("=" * 60)
    
    # Crear tablas
    print("\n1. Creando tablas...")
    crear_tablas()
    
    # Insertar causas conocidas
    print("\n2. Insertando causas conocidas manualmente...")
    insertar_causas_conocidas()
    
    # Buscar archivos JSON para ingestar
    print("\n3. Buscando archivos de scraping...")
    data_dir = "data/causas_corrupcion"
    
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            filepath = os.path.join(data_dir, filename)
            
            if filename.endswith('.json'):
                print(f"   Procesando: {filename}")
                ingestar_desde_json(filepath)
            
            elif filename.endswith('.csv') and 'causas' in filename:
                print(f"   Procesando: {filename}")
                ingestar_desde_csv(filepath)
    else:
        print(f"   No existe el directorio {data_dir}")
        print("   Ejecutar primero: python scrapear_causas_corrupcion.py")
    
    print("\n" + "=" * 60)
    print("INGESTA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
