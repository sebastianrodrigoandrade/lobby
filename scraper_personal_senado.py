#!/usr/bin/env python3
"""
Scraper de Personal del Senado de la Nación Argentina
======================================================
Extrae la información de asesores/personal asignado a cada senador.

Fuentes:
- Lista de senadores: https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoSenadores/json
- Detalle por senador: https://www.senado.gob.ar/senadores/senador/{ID}

Uso:
    python scraper_personal_senado.py
    
Salida:
    - personal_senado.csv: CSV con todo el personal
    - senadores.csv: CSV con datos de senadores
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
from datetime import datetime
import re
import os

# Configuración
BASE_URL = "https://www.senado.gob.ar"
SENADORES_JSON = f"{BASE_URL}/micrositios/DatosAbiertos/ExportarListadoSenadores/json"
DELAY_BETWEEN_REQUESTS = 1  # segundos entre requests para no sobrecargar

def obtener_senadores():
    """Obtiene la lista de senadores desde el endpoint JSON oficial."""
    print("📥 Descargando lista de senadores...")
    
    try:
        response = requests.get(SENADORES_JSON, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        senadores = data.get('table', {}).get('rows', [])
        print(f"✅ {len(senadores)} senadores encontrados")
        return senadores
    
    except Exception as e:
        print(f"❌ Error obteniendo senadores: {e}")
        return []

def extraer_personal_senador(senador_id, nombre_senador):
    """Extrae el personal asignado a un senador desde su página."""
    url = f"{BASE_URL}/senadores/senador/{senador_id}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        personal = []
        
        # Buscar la sección de Personal
        # El personal está en una tabla después del título "# PERSONAL"
        tables = soup.find_all('table')
        
        for table in tables:
            # Buscar tablas que tengan "Nombre y Apellido" y "Categoría"
            headers = table.find_all('th')
            header_texts = [h.get_text(strip=True).lower() for h in headers]
            
            if 'nombre y apellido' in header_texts or 'categoría' in header_texts:
                rows = table.find_all('tr')
                
                for row in rows[1:]:  # Saltar header
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        nombre = cells[0].get_text(strip=True)
                        categoria = cells[1].get_text(strip=True)
                        
                        if nombre and nombre.lower() != 'nombre y apellido':
                            personal.append({
                                'senador_id': senador_id,
                                'senador_nombre': nombre_senador,
                                'empleado_nombre': nombre,
                                'categoria': categoria
                            })
        
        # Método alternativo: buscar por patrón en el HTML raw
        if not personal:
            # A veces la tabla está en formato diferente
            text = response.text
            
            # Buscar patrón de tabla de personal
            match = re.search(r'# PERSONAL.*?<table[^>]*>(.*?)</table>', text, re.DOTALL | re.IGNORECASE)
            if match:
                table_html = match.group(1)
                table_soup = BeautifulSoup(f"<table>{table_html}</table>", 'html.parser')
                
                rows = table_soup.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        nombre = cells[0].get_text(strip=True)
                        categoria = cells[1].get_text(strip=True)
                        
                        if nombre and categoria:
                            personal.append({
                                'senador_id': senador_id,
                                'senador_nombre': nombre_senador,
                                'empleado_nombre': nombre,
                                'categoria': categoria
                            })
        
        return personal
    
    except Exception as e:
        print(f"  ⚠️ Error procesando senador {senador_id}: {e}")
        return []

def main():
    print("=" * 60)
    print("🏛️  SCRAPER PERSONAL DEL SENADO DE LA NACIÓN")
    print("=" * 60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Obtener lista de senadores
    senadores = obtener_senadores()
    
    if not senadores:
        print("❌ No se pudieron obtener los senadores. Abortando.")
        return
    
    # 2. Guardar senadores
    df_senadores = pd.DataFrame(senadores)
    df_senadores.to_csv('senadores.csv', index=False, encoding='utf-8-sig')
    print(f"💾 Guardado: senadores.csv ({len(df_senadores)} registros)")
    
    # 3. Scrapear personal de cada senador
    print()
    print("🔍 Extrayendo personal de cada senador...")
    print("-" * 40)
    
    todo_el_personal = []
    errores = []
    
    for i, senador in enumerate(senadores, 1):
        senador_id = senador.get('ID')
        nombre = f"{senador.get('NOMBRE', '')} {senador.get('APELLIDO', '')}".strip()
        provincia = senador.get('PROVINCIA', '')
        bloque = senador.get('BLOQUE', '')
        
        print(f"[{i:02d}/{len(senadores)}] {nombre} ({provincia}) - {bloque}...", end=" ", flush=True)
        
        personal = extraer_personal_senador(senador_id, nombre)
        
        if personal:
            # Agregar info del senador a cada empleado
            for emp in personal:
                emp['provincia'] = provincia
                emp['bloque'] = bloque
                emp['partido'] = senador.get('PARTIDO O ALIANZA', '')
            
            todo_el_personal.extend(personal)
            print(f"✅ {len(personal)} empleados")
        else:
            print("⚠️ Sin personal o error")
            errores.append({'senador_id': senador_id, 'nombre': nombre})
        
        # Delay para no sobrecargar el servidor
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # 4. Guardar resultados
    print()
    print("=" * 60)
    print("📊 RESULTADOS")
    print("=" * 60)
    
    if todo_el_personal:
        df_personal = pd.DataFrame(todo_el_personal)
        
        # Reordenar columnas
        columnas = [
            'empleado_nombre', 'categoria', 'senador_nombre', 'senador_id',
            'provincia', 'bloque', 'partido'
        ]
        df_personal = df_personal[[c for c in columnas if c in df_personal.columns]]
        
        df_personal.to_csv('personal_senado.csv', index=False, encoding='utf-8-sig')
        
        print(f"✅ Total empleados encontrados: {len(todo_el_personal)}")
        print(f"💾 Guardado: personal_senado.csv")
        
        # Estadísticas
        print()
        print("📈 Estadísticas por bloque:")
        stats = df_personal.groupby('bloque').size().sort_values(ascending=False)
        for bloque, count in stats.head(10).items():
            print(f"   • {bloque}: {count} empleados")
        
        print()
        print("📈 Distribución por categoría:")
        cat_stats = df_personal.groupby('categoria').size().sort_values(ascending=False)
        for cat, count in cat_stats.items():
            print(f"   • {cat}: {count} empleados")
    else:
        print("❌ No se encontró personal")
    
    if errores:
        print()
        print(f"⚠️ Senadores sin datos de personal: {len(errores)}")
        df_errores = pd.DataFrame(errores)
        df_errores.to_csv('senadores_sin_personal.csv', index=False, encoding='utf-8-sig')
    
    print()
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
