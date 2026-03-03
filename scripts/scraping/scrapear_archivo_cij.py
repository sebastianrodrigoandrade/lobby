"""
Scraper del Archivo CIJ - Corte Suprema
=======================================

Scrapea noticias de causas del archivo del Centro de Información Judicial
que ahora está en la Corte Suprema.

URL: https://www.csjn.gov.ar/archivo-cij/buscador.html

Tiene 18855 resultados en 755 páginas.

Requisitos:
    pip install selenium webdriver-manager pandas beautifulsoup4 python-dotenv

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


def buscar_en_archivo_cij(driver, palabra_clave, max_paginas=10):
    """
    Busca en el archivo CIJ por palabra clave
    Retorna lista de noticias/causas encontradas
    """
    resultados = []
    
    try:
        driver.get(BASE_URL)
        time.sleep(3)
        
        # Buscar campo de palabras clave
        campo_busqueda = None
        
        # Intentar varios selectores
        selectores = [
            "input[name*='palabras']",
            "input[name*='keyword']",
            "input[type='text']",
            "#palabras",
            ".search-input"
        ]
        
        for selector in selectores:
            try:
                campos = driver.find_elements(By.CSS_SELECTOR, selector)
                for campo in campos:
                    if campo.is_displayed():
                        campo_busqueda = campo
                        break
                if campo_busqueda:
                    break
            except:
                continue
        
        if campo_busqueda:
            campo_busqueda.clear()
            campo_busqueda.send_keys(palabra_clave)
            time.sleep(1)
            
            # Buscar botón
            botones = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
            for boton in botones:
                texto = boton.text or boton.get_attribute("value") or ""
                if boton.is_displayed() and ("Buscar" in texto or "buscar" in texto.lower()):
                    boton.click()
                    break
            
            time.sleep(3)
        
        # Scrapear resultados de todas las páginas
        for pagina in range(max_paginas):
            print(f"      Página {pagina + 1}...")
            
            # Parsear página actual
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Buscar tabla de resultados
            tabla = soup.find('table')
            if tabla:
                filas = tabla.find_all('tr')
                for fila in filas:
                    celdas = fila.find_all('td')
                    if len(celdas) >= 2:
                        link = fila.find('a')
                        fecha = celdas[0].get_text(strip=True) if celdas[0] else ''
                        titulo = ''
                        url = ''
                        
                        if link:
                            titulo = link.get_text(strip=True)
                            url = link.get('href', '')
                            if url and not url.startswith('http'):
                                url = "https://www.csjn.gov.ar/archivo-cij/" + url
                        else:
                            titulo = celdas[1].get_text(strip=True) if len(celdas) > 1 else ''
                        
                        if titulo and len(titulo) > 10:
                            resultados.append({
                                'fecha': fecha,
                                'titulo': titulo,
                                'url': url,
                                'palabra_clave': palabra_clave,
                                'fuente': 'archivo_cij'
                            })
            
            # Ir a siguiente página
            try:
                # Buscar link "Siguiente"
                sig = driver.find_element(By.XPATH, "//a[contains(text(), 'Siguiente')]")
                if sig.is_displayed():
                    sig.click()
                    time.sleep(2)
                else:
                    break
            except:
                # No hay más páginas
                break
        
    except Exception as e:
        print(f"      Error: {str(e)[:100]}")
    
    return resultados


def buscar_legisladores_en_noticias(noticias, legisladores):
    """
    Cruza noticias con nombres de legisladores
    """
    matches = []
    
    # Crear diccionario de apellidos para búsqueda rápida
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
    
    # Buscar apellidos en títulos de noticias
    for noticia in noticias:
        titulo = noticia['titulo'].upper()
        
        for apellido, legs in apellidos_leg.items():
            if apellido in titulo:
                for leg in legs:
                    matches.append({
                        'legislador_id': leg['id'],
                        'legislador_nombre': leg['nombre_completo'],
                        'bloque': leg['bloque'],
                        'camara': leg['camara'],
                        'noticia_titulo': noticia['titulo'],
                        'noticia_fecha': noticia['fecha'],
                        'noticia_url': noticia['url'],
                        'palabra_clave': noticia['palabra_clave']
                    })
    
    return matches


def guardar_resultados(noticias, matches, timestamp):
    """Guarda resultados"""
    
    # Noticias
    if noticias:
        df = pd.DataFrame(noticias)
        df.to_csv(f"{OUTPUT_DIR}/noticias_cij_{timestamp}.csv", index=False, encoding='utf-8-sig')
        print(f"   Guardadas {len(noticias)} noticias")
    
    # Matches
    if matches:
        df = pd.DataFrame(matches)
        df.to_csv(f"{OUTPUT_DIR}/matches_legisladores_{timestamp}.csv", index=False, encoding='utf-8-sig')
        print(f"   Guardados {len(matches)} matches con legisladores")
    
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
    
    # Palabras clave para buscar
    palabras_clave = [
        "corrupción",
        "procesamiento",
        "condena", 
        "imputado",
        "defraudación",
        "cohecho",
        "enriquecimiento ilícito",
        "lavado de activos",
        "administración fraudulenta"
    ]
    
    # Configurar driver
    print("\n2. Iniciando navegador...")
    driver = setup_driver(headless=True)
    
    todas_noticias = []
    
    try:
        print("\n3. Buscando en archivo CIJ...")
        
        for palabra in palabras_clave:
            print(f"\n   Buscando: '{palabra}'")
            noticias = buscar_en_archivo_cij(driver, palabra, max_paginas=5)
            print(f"      Encontradas: {len(noticias)}")
            todas_noticias.extend(noticias)
            time.sleep(2)
        
        # Eliminar duplicados por URL
        urls_vistas = set()
        noticias_unicas = []
        for n in todas_noticias:
            if n['url'] not in urls_vistas:
                urls_vistas.add(n['url'])
                noticias_unicas.append(n)
        
        print(f"\n   Total noticias únicas: {len(noticias_unicas)}")
        
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
        noticias_unicas = todas_noticias
    finally:
        driver.quit()
    
    # Cruzar con legisladores
    print("\n4. Cruzando con legisladores...")
    matches = buscar_legisladores_en_noticias(noticias_unicas, legisladores)
    print(f"   Matches encontrados: {len(matches)}")
    
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
    
    if matches:
        print("\nLegisladores encontrados:")
        nombres = set(m['legislador_nombre'] for m in matches)
        for nombre in list(nombres)[:10]:
            print(f"   - {nombre}")
        if len(nombres) > 10:
            print(f"   ... y {len(nombres) - 10} más")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
