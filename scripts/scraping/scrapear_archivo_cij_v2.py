"""
Scraper del Archivo CIJ - Corte Suprema (CORREGIDO)
====================================================

Scrapea noticias de causas del archivo del Centro de Información Judicial.

URL: https://www.csjn.gov.ar/archivo-cij/buscador.html

Formulario:
- form id="notas"
- input id="search" name="search" (palabras clave)
- button onclick="fsearch('search');"

Uso:
    python scrapear_archivo_cij.py
"""

import os
import re
import json
import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Configuración
OUTPUT_DIR = "data/archivo_cij"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.csjn.gov.ar/archivo-cij/buscador.html"


def setup_driver(headless=True):
    """Configura el driver de Selenium"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    return driver


def cargar_legisladores():
    """Carga legisladores de la base de datos"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: No se encontró DATABASE_URL")
        return []
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, nombre_completo, bloque, camara 
            FROM legisladores ORDER BY nombre_completo
        """))
        return [dict(row._mapping) for row in result]


def parsear_resultados(driver):
    """Extrae noticias de la página actual"""
    resultados = []
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Buscar la tabla de resultados
    # La estructura es una tabla con filas que tienen fecha y título con link
    tablas = soup.find_all('table')
    
    for tabla in tablas:
        filas = tabla.find_all('tr')
        for fila in filas:
            celdas = fila.find_all('td')
            if len(celdas) >= 1:
                # Buscar link en la fila
                link = fila.find('a')
                if link:
                    titulo = link.get_text(strip=True)
                    url = link.get('href', '')
                    
                    # Completar URL si es relativa
                    if url and not url.startswith('http'):
                        url = "https://www.csjn.gov.ar/archivo-cij/" + url
                    
                    # Buscar fecha (suele estar antes del link)
                    fecha = ''
                    texto_fila = fila.get_text()
                    # Buscar patrón de fecha DD de Mes de AAAA
                    fecha_match = re.search(r'(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', texto_fila)
                    if fecha_match:
                        fecha = fecha_match.group(1)
                    
                    if titulo and len(titulo) > 15:
                        resultados.append({
                            'fecha': fecha,
                            'titulo': titulo,
                            'url': url
                        })
    
    # También buscar en divs con estructura de lista
    items = soup.find_all(['div', 'li'], class_=re.compile(r'item|result|nota', re.I))
    for item in items:
        link = item.find('a')
        if link:
            titulo = link.get_text(strip=True)
            url = link.get('href', '')
            if url and not url.startswith('http'):
                url = "https://www.csjn.gov.ar/archivo-cij/" + url
            
            if titulo and len(titulo) > 15 and url not in [r['url'] for r in resultados]:
                resultados.append({
                    'fecha': '',
                    'titulo': titulo,
                    'url': url
                })
    
    return resultados


def buscar_en_archivo_cij(driver, palabra_clave, max_paginas=5):
    """
    Busca en el archivo CIJ por palabra clave
    """
    todas_noticias = []
    
    try:
        # Cargar página
        driver.get(BASE_URL)
        time.sleep(3)
        
        # Buscar el campo de búsqueda con id="search"
        campo_busqueda = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
        
        # Limpiar y escribir palabra clave
        campo_busqueda.clear()
        campo_busqueda.send_keys(palabra_clave)
        time.sleep(1)
        
        # Buscar y clickear el botón de buscar
        # El botón tiene onclick="fsearch('search');"
        boton = driver.find_element(By.CSS_SELECTOR, "button.submit")
        boton.click()
        
        time.sleep(4)  # Esperar resultados
        
        # Scrapear página actual
        noticias = parsear_resultados(driver)
        for n in noticias:
            n['palabra_clave'] = palabra_clave
            n['fuente'] = 'archivo_cij'
        todas_noticias.extend(noticias)
        
        print(f"      Página 1: {len(noticias)} resultados")
        
        # Navegar páginas siguientes
        for pagina in range(2, max_paginas + 1):
            try:
                # Buscar link de página siguiente o número de página
                # El paginador usa javascript:irPagina(N)
                siguiente = driver.find_element(By.XPATH, f"//a[contains(@href, 'irPagina({pagina-1})')]")
                if siguiente:
                    siguiente.click()
                    time.sleep(3)
                    
                    noticias = parsear_resultados(driver)
                    for n in noticias:
                        n['palabra_clave'] = palabra_clave
                        n['fuente'] = 'archivo_cij'
                    todas_noticias.extend(noticias)
                    
                    print(f"      Página {pagina}: {len(noticias)} resultados")
                else:
                    break
            except Exception as e:
                # No hay más páginas
                break
        
    except Exception as e:
        print(f"      Error: {str(e)[:150]}")
    
    return todas_noticias


def buscar_legisladores_en_noticias(noticias, legisladores):
    """
    Cruza noticias con nombres de legisladores
    """
    matches = []
    
    # Crear diccionario de apellidos
    apellidos_leg = {}
    for leg in legisladores:
        nombre = leg['nombre_completo']
        if ',' in nombre:
            apellido = nombre.split(',')[0].strip().upper()
        else:
            apellido = nombre.split()[0].upper() if nombre.split() else ''
        
        if apellido and len(apellido) > 2:
            if apellido not in apellidos_leg:
                apellidos_leg[apellido] = []
            apellidos_leg[apellido].append(leg)
    
    # Buscar apellidos en títulos
    for noticia in noticias:
        titulo_upper = noticia['titulo'].upper()
        
        for apellido, legs in apellidos_leg.items():
            # Buscar apellido como palabra completa
            if re.search(r'\b' + re.escape(apellido) + r'\b', titulo_upper):
                for leg in legs:
                    matches.append({
                        'legislador_id': leg['id'],
                        'legislador_nombre': leg['nombre_completo'],
                        'bloque': leg.get('bloque', ''),
                        'camara': leg.get('camara', ''),
                        'noticia_titulo': noticia['titulo'],
                        'noticia_fecha': noticia['fecha'],
                        'noticia_url': noticia['url'],
                        'palabra_clave': noticia.get('palabra_clave', '')
                    })
    
    return matches


def guardar_resultados(noticias, matches, timestamp):
    """Guarda resultados"""
    
    if noticias:
        df = pd.DataFrame(noticias)
        df.to_csv(f"{OUTPUT_DIR}/noticias_cij_{timestamp}.csv", index=False, encoding='utf-8-sig')
        print(f"   Guardadas {len(noticias)} noticias en CSV")
    
    if matches:
        df = pd.DataFrame(matches)
        df.to_csv(f"{OUTPUT_DIR}/matches_legisladores_{timestamp}.csv", index=False, encoding='utf-8-sig')
        print(f"   Guardados {len(matches)} matches en CSV")
    
    # JSON completo
    data = {
        'timestamp': timestamp,
        'total_noticias': len(noticias),
        'total_matches': len(matches),
        'noticias': noticias,
        'matches': matches
    }
    with open(f"{OUTPUT_DIR}/archivo_cij_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("SCRAPER ARCHIVO CIJ - CORTE SUPREMA")
    print("=" * 60)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Cargar legisladores
    print("\n1. Cargando legisladores...")
    legisladores = cargar_legisladores()
    print(f"   Cargados: {len(legisladores)}")
    
    # Palabras clave para buscar causas de corrupción
    palabras_clave = [
        "corrupción",
        "procesado",
        "condena",
        "imputado",
        "Kirchner",
        "De Vido",
        "Macri",
        "defraudación",
        "cohecho",
        "lavado"
    ]
    
    # Configurar driver
    print("\n2. Iniciando navegador...")
    driver = setup_driver(headless=True)
    
    todas_noticias = []
    
    try:
        print("\n3. Buscando en archivo CIJ...")
        
        for palabra in palabras_clave:
            print(f"\n   Buscando: '{palabra}'")
            noticias = buscar_en_archivo_cij(driver, palabra, max_paginas=3)
            todas_noticias.extend(noticias)
            time.sleep(2)
        
        # Eliminar duplicados por URL
        urls_vistas = set()
        noticias_unicas = []
        for n in todas_noticias:
            if n['url'] and n['url'] not in urls_vistas:
                urls_vistas.add(n['url'])
                noticias_unicas.append(n)
        
        print(f"\n   Total noticias únicas: {len(noticias_unicas)}")
        
    except KeyboardInterrupt:
        print("\n\nInterrumpido")
        noticias_unicas = todas_noticias
    finally:
        driver.quit()
    
    # Cruzar con legisladores
    print("\n4. Cruzando con legisladores...")
    matches = buscar_legisladores_en_noticias(noticias_unicas, legisladores)
    print(f"   Matches encontrados: {len(matches)}")
    
    # Mostrar algunos matches
    if matches:
        print("\n   Primeros matches:")
        nombres_vistos = set()
        for m in matches[:15]:
            if m['legislador_nombre'] not in nombres_vistos:
                print(f"      - {m['legislador_nombre']}: {m['noticia_titulo'][:60]}...")
                nombres_vistos.add(m['legislador_nombre'])
    
    # Guardar
    print("\n5. Guardando resultados...")
    guardar_resultados(noticias_unicas, matches, timestamp)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Noticias scrapeadas: {len(noticias_unicas)}")
    print(f"Matches con legisladores: {len(matches)}")
    print(f"Archivos en: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
