#!/usr/bin/env python3
"""
Scraper de Nómina Completa de RRHH del Senado de la Nación Argentina
=====================================================================
Descarga la nómina completa de personal del Senado (planta permanente y transitoria)
desde los endpoints de datos abiertos oficiales.

Fuentes:
- Planta Permanente: https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoAgentes/Excel?TIPO=1
- Planta Transitoria: https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoAgentes/Excel?TIPO=2
- Página HTML: https://www.senado.gob.ar/recursos-humanos/agente/composicion

Uso:
    python scraper_rrhh_senado.py
    
Salida:
    - rrhh_senado_permanente.csv: Personal de planta permanente
    - rrhh_senado_transitoria.csv: Personal de planta transitoria
    - rrhh_senado_completo.csv: Ambas plantas combinadas
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO
import json

# Configuración
BASE_URL = "https://www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoAgentes"

# Usar Excel que es más confiable que JSON
ENDPOINTS = {
    'permanente': f"{BASE_URL}/Excel?TIPO=1",
    'transitoria': f"{BASE_URL}/Excel?TIPO=2"
}

# Fallback: scrapear HTML
HTML_URL = "https://www.senado.gob.ar/recursos-humanos/agente/composicion"

def descargar_nomina_excel(tipo, url):
    """Descarga la nómina desde Excel."""
    print(f"📥 Descargando planta {tipo} (Excel)...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        # Verificar que sea Excel
        content_type = response.headers.get('Content-Type', '')
        
        if 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type:
            df = pd.read_excel(BytesIO(response.content))
            registros = df.to_dict('records')
            print(f"  ✅ {len(registros)} registros encontrados")
            return registros
        else:
            print(f"  ⚠️ Respuesta no es Excel: {content_type[:50]}")
            return []
    
    except Exception as e:
        print(f"  ❌ Error descargando Excel {tipo}: {e}")
        return []

def descargar_nomina_html():
    """Scrapea la nómina desde la página HTML como fallback."""
    print("📥 Scrapeando desde página HTML...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(HTML_URL, headers=headers, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        resultados = {'permanente': [], 'transitoria': []}
        
        # Buscar tablas
        tables = soup.find_all('table')
        
        current_tipo = None
        
        for table in tables:
            # Detectar tipo por el encabezado anterior
            prev = table.find_previous(['h4', 'h3', 'h2'])
            if prev:
                prev_text = prev.get_text(strip=True).lower()
                if 'transitoria' in prev_text:
                    current_tipo = 'transitoria'
                elif 'permanente' in prev_text:
                    current_tipo = 'permanente'
            
            if not current_tipo:
                # Intentar detectar por contenido de la tabla
                rows = table.find_all('tr')
                if len(rows) > 100:  # Las tablas grandes son de personal
                    current_tipo = 'transitoria' if len(resultados['transitoria']) == 0 else 'permanente'
            
            if current_tipo:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Saltar header
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        legajo = cells[0].get_text(strip=True)
                        nombre = cells[1].get_text(strip=True)
                        
                        if legajo and nombre and legajo.isdigit():
                            resultados[current_tipo].append({
                                'legajo': legajo,
                                'apellido_nombre': nombre
                            })
        
        print(f"  ✅ Permanente: {len(resultados['permanente'])} | Transitoria: {len(resultados['transitoria'])}")
        return resultados
    
    except Exception as e:
        print(f"  ❌ Error scrapeando HTML: {e}")
        return {'permanente': [], 'transitoria': []}

def main():
    print("=" * 60)
    print("🏛️  SCRAPER RRHH COMPLETO DEL SENADO DE LA NACIÓN")
    print("=" * 60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    todos_los_registros = []
    
    # Intentar primero con Excel
    for tipo, url in ENDPOINTS.items():
        registros = descargar_nomina_excel(tipo, url)
        
        if registros:
            # Agregar columna de tipo de planta
            for reg in registros:
                reg['tipo_planta'] = tipo
            
            # Guardar archivo individual
            df = pd.DataFrame(registros)
            filename = f"rrhh_senado_{tipo}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"  💾 Guardado: {filename}")
            
            todos_los_registros.extend(registros)
        
        print()
    
    # Si no funcionó Excel, intentar HTML
    if not todos_los_registros:
        print("⚠️ Excel no disponible, intentando scraping HTML...")
        print()
        
        html_data = descargar_nomina_html()
        
        for tipo, registros in html_data.items():
            if registros:
                for reg in registros:
                    reg['tipo_planta'] = tipo
                
                df = pd.DataFrame(registros)
                filename = f"rrhh_senado_{tipo}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                print(f"  💾 Guardado: {filename}")
                
                todos_los_registros.extend(registros)
    
    # Guardar archivo combinado
    if todos_los_registros:
        df_completo = pd.DataFrame(todos_los_registros)
        df_completo.to_csv('rrhh_senado_completo.csv', index=False, encoding='utf-8-sig')
        
        print()
        print("=" * 60)
        print("📊 RESUMEN")
        print("=" * 60)
        print(f"✅ Total de empleados: {len(todos_los_registros)}")
        print(f"💾 Guardado: rrhh_senado_completo.csv")
        
        # Estadísticas por tipo de planta
        print()
        print("📈 Por tipo de planta:")
        stats = df_completo.groupby('tipo_planta').size()
        for planta, count in stats.items():
            print(f"   • {planta.title()}: {count:,} empleados")
    else:
        print()
        print("=" * 60)
        print("⚠️ DATOS NO DISPONIBLES")
        print("=" * 60)
        print()
        print("Los endpoints no están respondiendo. Podés descargar manualmente:")
        print()
        print("Excel Permanente:")
        print(f"  {ENDPOINTS['permanente']}")
        print()
        print("Excel Transitoria:")
        print(f"  {ENDPOINTS['transitoria']}")
        print()
        print("O visitar la página:")
        print(f"  {HTML_URL}")
    
    print()
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
