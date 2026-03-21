#!/usr/bin/env python3
"""
Scraper de Diputados Nacionales de Argentina
=============================================
Extrae la información de los 257 diputados nacionales desde la página oficial
de la Cámara de Diputados de la Nación.

Fuentes:
- Lista de diputados: https://www.diputados.gov.ar/diputados/
- Detalle por diputado: https://www.diputados.gov.ar/diputados/{slug}/
- Datos abiertos: https://datos.hcdn.gob.ar/dataset

Uso:
    python scraper_diputados.py
    
Salida:
    - diputados.csv: Datos de los 257 diputados
    - personal_diputados.csv: Personal asignado a cada diputado (si disponible)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime

# Configuración
BASE_URL = "https://www.diputados.gov.ar"
LISTA_DIPUTADOS_URL = f"{BASE_URL}/diputados/"
DELAY_BETWEEN_REQUESTS = 0.5  # segundos entre requests

def obtener_lista_diputados():
    """Obtiene la lista de diputados desde la página principal."""
    print("📥 Descargando lista de diputados...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(LISTA_DIPUTADOS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        diputados = []
        
        # Buscar la tabla de diputados
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Saltar header
                cells = row.find_all('td')
                
                if len(cells) >= 7:
                    # Extraer link al perfil
                    link_tag = cells[1].find('a')
                    perfil_url = link_tag['href'] if link_tag else ''
                    nombre = link_tag.get_text(strip=True) if link_tag else cells[1].get_text(strip=True)
                    
                    # Extraer slug del URL
                    slug = ''
                    if perfil_url:
                        match = re.search(r'/diputados/([^/]+)/?', perfil_url)
                        if match:
                            slug = match.group(1)
                    
                    diputado = {
                        'nombre': nombre,
                        'distrito': cells[2].get_text(strip=True),
                        'bloque': cells[3].get_text(strip=True),
                        'mandato': cells[4].get_text(strip=True),
                        'inicio_mandato': cells[5].get_text(strip=True),
                        'fin_mandato': cells[6].get_text(strip=True),
                        'fecha_nacimiento': cells[7].get_text(strip=True) if len(cells) > 7 else '',
                        'perfil_url': f"{BASE_URL}{perfil_url}" if perfil_url and not perfil_url.startswith('http') else perfil_url,
                        'slug': slug
                    }
                    
                    diputados.append(diputado)
        
        print(f"✅ {len(diputados)} diputados encontrados")
        return diputados
    
    except Exception as e:
        print(f"❌ Error obteniendo lista: {e}")
        return []

def extraer_detalle_diputado(slug, nombre):
    """Extrae información adicional del perfil de un diputado."""
    if not slug:
        return {}
    
    url = f"{BASE_URL}/diputados/{slug}/"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        detalle = {
            'email': '',
            'telefono': '',
            'comisiones': [],
            'personal': []
        }
        
        # Buscar email
        email_link = soup.find('a', href=re.compile(r'^mailto:'))
        if email_link:
            detalle['email'] = email_link['href'].replace('mailto:', '')
        
        # Buscar teléfono
        tel_pattern = re.compile(r'\(\d+\)\s*\d+[-\s]*\d+')
        tel_match = tel_pattern.search(response.text)
        if tel_match:
            detalle['telefono'] = tel_match.group()
        
        # Buscar comisiones
        comisiones_section = soup.find('h2', string=re.compile(r'Comisiones', re.I))
        if comisiones_section:
            comisiones_list = comisiones_section.find_next('ul')
            if comisiones_list:
                for li in comisiones_list.find_all('li'):
                    detalle['comisiones'].append(li.get_text(strip=True))
        
        # Buscar personal (si existe sección)
        personal_section = soup.find('h2', string=re.compile(r'Personal|Asesores|Colaboradores', re.I))
        if personal_section:
            personal_table = personal_section.find_next('table')
            if personal_table:
                for row in personal_table.find_all('tr')[1:]:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        detalle['personal'].append({
                            'nombre': cells[0].get_text(strip=True),
                            'cargo': cells[1].get_text(strip=True) if len(cells) > 1 else ''
                        })
        
        return detalle
    
    except Exception as e:
        return {}

def descargar_csv_oficial():
    """Intenta descargar el CSV oficial si está disponible."""
    print("📥 Intentando descargar CSV oficial...")
    
    # El botón "csv diputados" en la página sugiere que hay un endpoint
    posibles_urls = [
        "https://www.diputados.gov.ar/diputados/listado.csv",
        "https://www.diputados.gov.ar/diputados/diputados.csv",
        "https://datos.hcdn.gob.ar/dataset/diputados/resource/diputados.csv",
    ]
    
    for url in posibles_urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200 and 'text/csv' in response.headers.get('Content-Type', ''):
                print(f"  ✅ CSV encontrado en {url}")
                return response.text
        except:
            continue
    
    print("  ⚠️ CSV oficial no disponible, usando scraping")
    return None

def main():
    print("=" * 60)
    print("🏛️  SCRAPER DIPUTADOS NACIONALES DE ARGENTINA")
    print("=" * 60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Obtener lista de diputados
    diputados = obtener_lista_diputados()
    
    if not diputados:
        print("❌ No se pudieron obtener los diputados. Abortando.")
        return
    
    # 2. Guardar lista básica
    df_diputados = pd.DataFrame(diputados)
    df_diputados.to_csv('diputados.csv', index=False, encoding='utf-8-sig')
    print(f"💾 Guardado: diputados.csv ({len(df_diputados)} registros)")
    
    # 3. Opcionalmente, extraer detalles de cada diputado
    print()
    print("🔍 ¿Extraer detalles adicionales de cada diputado? (toma ~2-3 minutos)")
    print("   Esto incluye: email, teléfono, comisiones, personal")
    
    # Por defecto no extraemos detalles para que sea rápido
    # Descomentar las siguientes líneas para extraer detalles:
    
    # print()
    # print("🔍 Extrayendo detalles de cada diputado...")
    # print("-" * 40)
    # 
    # todo_el_personal = []
    # 
    # for i, dip in enumerate(diputados, 1):
    #     print(f"[{i:03d}/{len(diputados)}] {dip['nombre']}...", end=" ", flush=True)
    #     
    #     detalle = extraer_detalle_diputado(dip['slug'], dip['nombre'])
    #     
    #     if detalle:
    #         dip['email'] = detalle.get('email', '')
    #         dip['telefono'] = detalle.get('telefono', '')
    #         dip['comisiones'] = '; '.join(detalle.get('comisiones', []))
    #         
    #         # Agregar personal
    #         for emp in detalle.get('personal', []):
    #             todo_el_personal.append({
    #                 'diputado_nombre': dip['nombre'],
    #                 'diputado_distrito': dip['distrito'],
    #                 'diputado_bloque': dip['bloque'],
    #                 'empleado_nombre': emp['nombre'],
    #                 'cargo': emp['cargo']
    #             })
    #         
    #         print(f"✅")
    #     else:
    #         print(f"⚠️")
    #     
    #     time.sleep(DELAY_BETWEEN_REQUESTS)
    # 
    # # Guardar con detalles
    # df_diputados = pd.DataFrame(diputados)
    # df_diputados.to_csv('diputados_detalle.csv', index=False, encoding='utf-8-sig')
    # 
    # if todo_el_personal:
    #     df_personal = pd.DataFrame(todo_el_personal)
    #     df_personal.to_csv('personal_diputados.csv', index=False, encoding='utf-8-sig')
    #     print(f"💾 Guardado: personal_diputados.csv ({len(df_personal)} registros)")
    
    # 4. Estadísticas
    print()
    print("=" * 60)
    print("📊 ESTADÍSTICAS")
    print("=" * 60)
    
    print(f"✅ Total diputados: {len(df_diputados)}")
    
    print()
    print("📈 Por bloque:")
    bloque_stats = df_diputados.groupby('bloque').size().sort_values(ascending=False)
    for bloque, count in bloque_stats.head(10).items():
        print(f"   • {bloque}: {count}")
    
    print()
    print("📈 Por distrito:")
    distrito_stats = df_diputados.groupby('distrito').size().sort_values(ascending=False)
    for distrito, count in distrito_stats.head(10).items():
        print(f"   • {distrito}: {count}")
    
    print()
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
