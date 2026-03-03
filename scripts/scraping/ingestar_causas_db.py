"""
Ingesta de Causas Judiciales a PostgreSQL
=========================================

Crea las tablas e ingesta los matches verificados del scraping.

Uso:
    python ingestar_causas_db.py
"""

import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

DATA_DIR = "data/archivo_cij"


def crear_tablas():
    """Crea las tablas para causas judiciales"""
    
    sql = """
    -- Tabla de noticias judiciales scrapeadas
    CREATE TABLE IF NOT EXISTS noticias_judiciales (
        id SERIAL PRIMARY KEY,
        titulo TEXT NOT NULL,
        fecha VARCHAR(100),
        url TEXT,
        palabra_clave VARCHAR(100),
        fuente VARCHAR(50) DEFAULT 'archivo_cij',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(url)
    );
    
    -- Tabla de causas vinculadas a legisladores
    CREATE TABLE IF NOT EXISTS causas_legisladores (
        id SERIAL PRIMARY KEY,
        legislador_id INT REFERENCES legisladores(id),
        noticia_id INT REFERENCES noticias_judiciales(id),
        razon_match VARCHAR(100),
        verificado BOOLEAN DEFAULT FALSE,
        es_imputado BOOLEAN DEFAULT NULL,
        notas TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(legislador_id, noticia_id)
    );
    
    -- Índices
    CREATE INDEX IF NOT EXISTS idx_noticias_fecha ON noticias_judiciales(fecha);
    CREATE INDEX IF NOT EXISTS idx_causas_leg_id ON causas_legisladores(legislador_id);
    CREATE INDEX IF NOT EXISTS idx_causas_verificado ON causas_legisladores(verificado);
    """
    
    with engine.connect() as conn:
        for statement in sql.split(';'):
            if statement.strip():
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    print(f"   Advertencia: {str(e)[:50]}")
        conn.commit()
    
    print("✓ Tablas creadas")


def ingestar_noticias(filepath):
    """Ingesta noticias desde CSV"""
    
    df = pd.read_csv(filepath)
    print(f"   Procesando {len(df)} noticias...")
    
    insertadas = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            try:
                sql = """
                INSERT INTO noticias_judiciales (titulo, fecha, url, palabra_clave, fuente)
                VALUES (:titulo, :fecha, :url, :palabra_clave, :fuente)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
                """
                result = conn.execute(text(sql), {
                    'titulo': row.get('titulo', ''),
                    'fecha': row.get('fecha', ''),
                    'url': row.get('url', ''),
                    'palabra_clave': row.get('palabra_clave', ''),
                    'fuente': row.get('fuente', 'archivo_cij')
                })
                if result.fetchone():
                    insertadas += 1
            except Exception as e:
                pass
        
        conn.commit()
    
    print(f"   ✓ {insertadas} noticias insertadas")
    return insertadas


def ingestar_matches(filepath):
    """Ingesta matches verificados desde CSV"""
    
    df = pd.read_csv(filepath)
    
    # Filtrar solo válidos si existe la columna
    if 'match_valido' in df.columns:
        df = df[df['match_valido'] == True]
    
    print(f"   Procesando {len(df)} matches...")
    
    insertados = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            try:
                # Primero obtener el ID de la noticia por URL
                result = conn.execute(text("""
                    SELECT id FROM noticias_judiciales WHERE url = :url
                """), {'url': row.get('noticia_url', '')})
                
                noticia_row = result.fetchone()
                if not noticia_row:
                    continue
                
                noticia_id = noticia_row[0]
                legislador_id = row.get('legislador_id')
                
                # Insertar match
                sql = """
                INSERT INTO causas_legisladores (legislador_id, noticia_id, razon_match)
                VALUES (:leg_id, :noticia_id, :razon)
                ON CONFLICT (legislador_id, noticia_id) DO NOTHING
                """
                conn.execute(text(sql), {
                    'leg_id': legislador_id,
                    'noticia_id': noticia_id,
                    'razon': row.get('razon_match', 'scraping')
                })
                insertados += 1
                
            except Exception as e:
                pass
        
        conn.commit()
    
    print(f"   ✓ {insertados} matches insertados")
    return insertados


def mostrar_estadisticas():
    """Muestra estadísticas de las causas"""
    
    with engine.connect() as conn:
        # Total noticias
        result = conn.execute(text("SELECT COUNT(*) FROM noticias_judiciales"))
        total_noticias = result.scalar()
        
        # Total matches
        result = conn.execute(text("SELECT COUNT(*) FROM causas_legisladores"))
        total_matches = result.scalar()
        
        # Legisladores con causas
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT legislador_id) FROM causas_legisladores
        """))
        total_legisladores = result.scalar()
        
        # Top legisladores
        result = conn.execute(text("""
            SELECT l.nombre_completo, l.bloque, COUNT(*) as cantidad
            FROM causas_legisladores cl
            JOIN legisladores l ON cl.legislador_id = l.id
            GROUP BY l.id, l.nombre_completo, l.bloque
            ORDER BY cantidad DESC
            LIMIT 15
        """))
        top = result.fetchall()
    
    print("\n" + "=" * 60)
    print("ESTADÍSTICAS DE CAUSAS JUDICIALES")
    print("=" * 60)
    print(f"Total noticias judiciales: {total_noticias}")
    print(f"Total matches con legisladores: {total_matches}")
    print(f"Legisladores con menciones: {total_legisladores}")
    
    print("\nTop 15 legisladores más mencionados:")
    print("-" * 60)
    for row in top:
        print(f"  {row[0][:40]:<42} | {row[2]:>3} menciones")
    print("=" * 60)


def main():
    print("=" * 60)
    print("INGESTA DE CAUSAS JUDICIALES")
    print("=" * 60)
    
    # Crear tablas
    print("\n1. Creando tablas...")
    crear_tablas()
    
    # Buscar archivos
    print("\n2. Buscando archivos de datos...")
    
    # Noticias
    noticias_files = [f for f in os.listdir(DATA_DIR) if f.startswith('noticias_cij_') and f.endswith('.csv')]
    if noticias_files:
        noticias_files.sort(reverse=True)
        filepath = os.path.join(DATA_DIR, noticias_files[0])
        print(f"\n3. Ingresando noticias desde: {noticias_files[0]}")
        ingestar_noticias(filepath)
    
    # Matches (preferir el limpio)
    matches_files = [f for f in os.listdir(DATA_DIR) if 'matches_legisladores_' in f and '_limpio.csv' in f]
    if not matches_files:
        matches_files = [f for f in os.listdir(DATA_DIR) if f.startswith('matches_legisladores_') and f.endswith('.csv') and '_con_flag' not in f]
    
    if matches_files:
        matches_files.sort(reverse=True)
        filepath = os.path.join(DATA_DIR, matches_files[0])
        print(f"\n4. Ingresando matches desde: {matches_files[0]}")
        ingestar_matches(filepath)
    
    # Estadísticas
    mostrar_estadisticas()
    
    print("\n✓ INGESTA COMPLETADA")


if __name__ == "__main__":
    main()
