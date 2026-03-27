#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Actualiza integrantes de comisiones y fotos de legisladores desde HCDN
"""
import os
import re
import urllib.request
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?sslmode=require'


def scrape_comision(slug):
    """Scrapea integrantes de una comisión desde HCDN."""
    url = f"https://www.hcdn.gob.ar/comisiones/permanentes/{slug}/integrantes.html"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
        
        # Extraer nombre y foto
        pattern = r"alt='([^']+)'\s+src='([^']+)'"
        matches = re.findall(pattern, html)
        
        # Extraer cargos
        cargos_pattern = r"(PRESIDENTE|VICEPRESIDENTE \d+ª?|SECRETARIO|VOCAL)</td>"
        cargos = re.findall(cargos_pattern, html)
        
        integrantes = []
        for i, (nombre, foto) in enumerate(matches):
            cargo = cargos[i] if i < len(cargos) else 'VOCAL'
            integrantes.append({
                'nombre': nombre,
                'foto': foto,
                'cargo': cargo
            })
        
        return integrantes
    except Exception as e:
        print(f"  Error scrapeando {slug}: {e}")
        return []


def buscar_legislador(conn, nombre):
    """Busca un legislador por nombre."""
    nombre_parts = nombre.split(', ')
    apellido = nombre_parts[0] if nombre_parts else ''
    primer_nombre = nombre_parts[1].split()[0] if len(nombre_parts) > 1 else ''
    
    if not apellido or not primer_nombre:
        return None
    
    result = conn.execute(text('''
        SELECT id FROM legisladores 
        WHERE nombre_completo ILIKE :pat_ap
          AND nombre_completo ILIKE :pat_nom
          AND mandato_hasta >= CURRENT_DATE
        LIMIT 1
    '''), {'pat_ap': f'%{apellido}%', 'pat_nom': f'%{primer_nombre}%'})
    row = result.fetchone()
    return row[0] if row else None


def actualizar_comisiones():
    """Actualiza todas las comisiones."""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Obtener todas las comisiones
        result = conn.execute(text('SELECT id, slug, nombre FROM comisiones ORDER BY nombre'))
        comisiones = result.fetchall()
        
        print(f"Actualizando {len(comisiones)} comisiones...")
        
        # Limpiar integrantes existentes
        conn.execute(text('DELETE FROM comision_integrantes'))
        
        total_integrantes = 0
        fotos_actualizadas = 0
        
        for com_id, slug, nombre in comisiones:
            integrantes = scrape_comision(slug)
            
            if not integrantes:
                print(f"  {nombre}: sin datos")
                continue
            
            for integ in integrantes:
                leg_id = buscar_legislador(conn, integ['nombre'])
                
                conn.execute(text('''
                    INSERT INTO comision_integrantes (comision_id, legislador_id, nombre_raw, cargo, bloque)
                    VALUES (:com_id, :leg_id, :nombre, :cargo, '')
                '''), {
                    'com_id': com_id,
                    'leg_id': leg_id,
                    'nombre': integ['nombre'],
                    'cargo': integ['cargo']
                })
                total_integrantes += 1
                
                # Actualizar foto
                if leg_id and integ['foto']:
                    conn.execute(text('''
                        UPDATE legisladores SET foto_url = :foto WHERE id = :id
                    '''), {'foto': integ['foto'], 'id': leg_id})
                    fotos_actualizadas += 1
            
            print(f"  {nombre}: {len(integrantes)} integrantes")
        
        conn.commit()
        
        print(f"\n=== RESUMEN ===")
        print(f"Integrantes insertados: {total_integrantes}")
        print(f"Fotos actualizadas: {fotos_actualizadas}")
    
    engine.dispose()


if __name__ == '__main__':
    actualizar_comisiones()
