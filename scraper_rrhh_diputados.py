#!/usr/bin/env python3
"""
Scraper de RRHH de la Cámara de Diputados de la Nación Argentina
=================================================================
Descarga la nómina completa de personal de la Cámara de Diputados
desde el portal de datos abiertos y la página de transparencia.

Fuentes:
- Datos abiertos: https://datos.hcdn.gob.ar/dataset (personal)
- Transparencia: https://www.diputados.gov.ar/institucional/transparencia/rrhh/

Uso:
    python scraper_rrhh_diputados.py
    
Salida:
    - rrhh_diputados.csv: Nómina completa del personal
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re

# URLs conocidas
URLS_DATOS_ABIERTOS = [
    "https://datos.hcdn.gob.ar/dataset/nomina-de-personal",
    "https://datos.hcdn.gob.ar/api/3/action/package_show?id=nomina-de-personal",
]

TRANSPARENCIA_URL = "https://www.diputados.gov.ar/institucional/transparencia/rrhh/index.html"

def buscar_csv_en_datos_abiertos():
    """Intenta encontrar y descargar el CSV de personal desde datos abiertos."""
    print("📥 Buscando dataset de personal en datos.hcdn.gob.ar...")
    
    # Intentar la API de CKAN
    try:
        api_url = "https://datos.hcdn.gob.ar/api/3/action/package_list"
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                datasets = data.get('result', [])
                print(f"  📋 {len(datasets)} datasets disponibles")
                
                # Buscar dataset de personal
                for ds in datasets:
                    if 'personal' in ds.lower() or 'nomina' in ds.lower() or 'empleado' in ds.lower():
                        print(f"  🔍 Encontrado: {ds}")
                        
                        # Obtener detalles del dataset
                        detail_url = f"https://datos.hcdn.gob.ar/api/3/action/package_show?id={ds}"
                        detail_resp = requests.get(detail_url, timeout=30)
                        
                        if detail_resp.status_code == 200:
                            detail_data = detail_resp.json()
                            if detail_data.get('success'):
                                resources = detail_data.get('result', {}).get('resources', [])
                                
                                for res in resources:
                                    if res.get('format', '').upper() in ['CSV', 'JSON']:
                                        resource_url = res.get('url')
                                        print(f"  ✅ Recurso encontrado: {resource_url}")
                                        return resource_url
    except Exception as e:
        print(f"  ⚠️ Error en API: {e}")
    
    return None

def descargar_desde_transparencia():
    """Intenta obtener datos desde la página de transparencia."""
    print("📥 Buscando en página de transparencia...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(TRANSPARENCIA_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar links a archivos de datos
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            text = link.get_text(strip=True).lower()
            
            # Buscar links a CSVs o Excel
            if any(ext in href.lower() for ext in ['.csv', '.xlsx', '.xls', 'excel', 'download']):
                if any(term in text for term in ['personal', 'nómina', 'nomina', 'planta', 'empleado']):
                    full_url = href if href.startswith('http') else f"https://www.diputados.gov.ar{href}"
                    print(f"  ✅ Encontrado: {full_url}")
                    return full_url
            
            # También buscar links a datos abiertos
            if 'datos.hcdn.gob.ar' in href:
                print(f"  🔗 Link a datos abiertos: {href}")
                return href
        
        print("  ⚠️ No se encontraron links directos a datos")
        return None
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def descargar_recurso(url):
    """Descarga un recurso CSV o JSON."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '')
        
        if 'json' in content_type or url.endswith('.json'):
            data = response.json()
            # Intentar extraer registros
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                if 'result' in data:
                    return pd.DataFrame(data['result'])
                elif 'data' in data:
                    return pd.DataFrame(data['data'])
                elif 'rows' in data:
                    return pd.DataFrame(data['rows'])
        else:
            # Asumir CSV
            from io import StringIO
            return pd.read_csv(StringIO(response.text))
        
        return None
    except Exception as e:
        print(f"  ❌ Error descargando: {e}")
        return None

def main():
    print("=" * 60)
    print("🏛️  SCRAPER RRHH CÁMARA DE DIPUTADOS")
    print("=" * 60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    df = None
    
    # 1. Intentar datos abiertos
    csv_url = buscar_csv_en_datos_abiertos()
    
    if csv_url:
        print()
        print("📥 Descargando datos...")
        df = descargar_recurso(csv_url)
    
    # 2. Si no funciona, intentar transparencia
    if df is None or df.empty:
        print()
        transparencia_url = descargar_desde_transparencia()
        
        if transparencia_url:
            df = descargar_recurso(transparencia_url)
    
    # 3. Guardar resultados
    if df is not None and not df.empty:
        df.to_csv('rrhh_diputados.csv', index=False, encoding='utf-8-sig')
        
        print()
        print("=" * 60)
        print("📊 RESULTADOS")
        print("=" * 60)
        print(f"✅ Total registros: {len(df)}")
        print(f"💾 Guardado: rrhh_diputados.csv")
        print()
        print("📈 Columnas disponibles:")
        for col in df.columns:
            print(f"   • {col}")
    else:
        print()
        print("=" * 60)
        print("⚠️ DATOS NO DISPONIBLES AUTOMÁTICAMENTE")
        print("=" * 60)
        print()
        print("Los datos de personal de Diputados pueden descargarse manualmente desde:")
        print()
        print("1. Portal de Datos Abiertos:")
        print("   https://datos.hcdn.gob.ar/dataset")
        print("   → Buscar 'Nómina de Personal'")
        print()
        print("2. Página de Transparencia:")
        print("   https://www.diputados.gov.ar/institucional/transparencia/rrhh/")
        print()
        print("3. Alternativamente, el scraper de diputados (scraper_diputados.py)")
        print("   puede extraer información de cada diputado incluyendo su personal.")
    
    print()
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
