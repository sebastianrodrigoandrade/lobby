"""
Scraper de Causas de Corrupción - Archivo CIJ / Corte Suprema
==============================================================

Este script scrapea la base de causas de corrupción que estaba en el CIJ
y ahora está en el archivo de la Corte Suprema.

Fuente: https://www.csjn.gov.ar/archivo-cij/buscador.html

Requisitos:
    pip install selenium webdriver-manager pandas beautifulsoup4 requests

Uso:
    python scrapear_causas_corrupcion.py
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
import requests

# Configuración
OUTPUT_DIR = "data/causas_corrupcion"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def setup_driver():
    """Configura el driver de Selenium"""
    options = Options()
    options.add_argument("--headless")  # Sin interfaz gráfica
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def scrapear_pagina_cij(driver, url):
    """Scrapea una página del buscador del archivo CIJ"""
    driver.get(url)
    time.sleep(3)  # Esperar a que cargue
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    causas = []
    
    # Buscar las filas de causas (ajustar selectores según la estructura real)
    tabla = soup.find('table')
    if tabla:
        filas = tabla.find_all('tr')[1:]  # Saltar header
        for fila in filas:
            celdas = fila.find_all('td')
            if len(celdas) >= 3:
                causa = {
                    'fecha': celdas[0].get_text(strip=True) if celdas[0] else '',
                    'titulo': celdas[1].get_text(strip=True) if celdas[1] else '',
                    'link': celdas[1].find('a')['href'] if celdas[1].find('a') else ''
                }
                causas.append(causa)
    
    return causas


def scrapear_scw_por_nombre(nombre, apellido):
    """
    Busca causas en el Sistema de Consulta Web del PJN por nombre
    https://scw.pjn.gov.ar/scw/home.seam
    
    NOTA: Las causas PENALES están bloqueadas en la consulta pública.
    Solo se pueden encontrar causas civiles, comerciales, contencioso, etc.
    """
    url = "https://scw.pjn.gov.ar/scw/home.seam"
    
    driver = setup_driver()
    causas = []
    
    try:
        driver.get(url)
        time.sleep(3)
        
        # Buscar el campo de búsqueda por partes
        # Esto depende de la estructura exacta del formulario
        # Hay que seleccionar "Por Parte" y luego ingresar apellido, nombre
        
        # Intentar buscar el tab de "Por Parte"
        try:
            tab_parte = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Por Parte')]"))
            )
            tab_parte.click()
            time.sleep(2)
        except:
            print("No se encontró el tab 'Por Parte'")
        
        # Buscar campos de apellido y nombre
        try:
            campo_apellido = driver.find_element(By.ID, "formPublica:apellido")
            campo_apellido.clear()
            campo_apellido.send_keys(apellido)
            
            campo_nombre = driver.find_element(By.ID, "formPublica:nombre") 
            campo_nombre.clear()
            campo_nombre.send_keys(nombre)
            
            # Click en buscar
            btn_buscar = driver.find_element(By.ID, "formPublica:buscarButton")
            btn_buscar.click()
            time.sleep(5)
            
            # Parsear resultados
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            resultados = soup.find_all('tr', class_='rich-table-row')
            
            for fila in resultados:
                celdas = fila.find_all('td')
                if len(celdas) >= 4:
                    causa = {
                        'expediente': celdas[0].get_text(strip=True),
                        'caratula': celdas[1].get_text(strip=True),
                        'juzgado': celdas[2].get_text(strip=True),
                        'fecha': celdas[3].get_text(strip=True),
                        'persona_buscada': f"{apellido}, {nombre}"
                    }
                    causas.append(causa)
                    
        except Exception as e:
            print(f"Error buscando {apellido}, {nombre}: {e}")
            
    finally:
        driver.quit()
    
    return causas


def extraer_nombre_caratula(caratula):
    """Extrae nombres de personas de una carátula judicial"""
    nombres = []
    
    # Patrones comunes en carátulas
    # "DENUNCIADO: APELLIDO, NOMBRE"
    # "IMPUTADO: APELLIDO NOMBRE"
    # "QUERELLANTE: APELLIDO, NOMBRE"
    
    patrones = [
        r'DENUNCIADO:\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+?)(?:\s+s/|$)',
        r'IMPUTADO:\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+?)(?:\s+s/|$)',
        r'QUERELLANTE:\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+?)(?:\s+s/|$)',
        r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ]+,\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)',
    ]
    
    for patron in patrones:
        matches = re.findall(patron, caratula, re.IGNORECASE)
        for match in matches:
            nombre_limpio = match.strip()
            if len(nombre_limpio) > 3 and nombre_limpio not in nombres:
                nombres.append(nombre_limpio)
    
    return nombres


def normalizar_nombre(nombre):
    """Normaliza un nombre para comparación"""
    # Quitar tildes
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N'
    }
    for old, new in replacements.items():
        nombre = nombre.replace(old, new)
    
    # Convertir a mayúsculas y quitar espacios extra
    return ' '.join(nombre.upper().split())


def fuzzy_match_nombre(nombre1, nombre2, threshold=0.8):
    """Compara dos nombres con fuzzy matching"""
    from difflib import SequenceMatcher
    
    n1 = normalizar_nombre(nombre1)
    n2 = normalizar_nombre(nombre2)
    
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold, ratio


def cargar_legisladores_db():
    """Carga la lista de legisladores desde la base de datos"""
    from sqlalchemy import create_engine, text
    from dotenv import load_dotenv
    
    load_dotenv()
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: No se encontró DATABASE_URL en .env")
        return []
    
    engine = create_engine(DATABASE_URL)
    
    query = """
    SELECT id, nombre_completo, bloque, camara, distrito
    FROM legisladores
    ORDER BY nombre_completo
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query))
        legisladores = [dict(row._mapping) for row in result]
    
    return legisladores


def cruzar_con_legisladores(causas, legisladores):
    """Cruza las causas con la lista de legisladores"""
    matches = []
    
    for causa in causas:
        # Extraer nombres de la carátula
        nombres_causa = extraer_nombre_caratula(causa.get('caratula', ''))
        
        for nombre_causa in nombres_causa:
            for leg in legisladores:
                es_match, score = fuzzy_match_nombre(nombre_causa, leg['nombre_completo'])
                
                if es_match:
                    match = {
                        'legislador_id': leg['id'],
                        'legislador_nombre': leg['nombre_completo'],
                        'bloque': leg['bloque'],
                        'camara': leg['camara'],
                        'nombre_en_causa': nombre_causa,
                        'expediente': causa.get('expediente', ''),
                        'caratula': causa.get('caratula', ''),
                        'delitos': causa.get('delitos', ''),
                        'juzgado': causa.get('juzgado', ''),
                        'estado': causa.get('estado', ''),
                        'match_score': score
                    }
                    matches.append(match)
                    print(f"  ✓ Match: {leg['nombre_completo']} <- {nombre_causa} (score: {score:.2f})")
    
    return matches


def guardar_resultados(causas, matches, timestamp):
    """Guarda los resultados en CSV y JSON"""
    
    # Guardar todas las causas
    if causas:
        df_causas = pd.DataFrame(causas)
        df_causas.to_csv(f"{OUTPUT_DIR}/causas_corrupcion_{timestamp}.csv", index=False)
        print(f"Guardadas {len(causas)} causas en CSV")
    
    # Guardar matches con legisladores
    if matches:
        df_matches = pd.DataFrame(matches)
        df_matches.to_csv(f"{OUTPUT_DIR}/causas_legisladores_{timestamp}.csv", index=False)
        print(f"Guardados {len(matches)} matches con legisladores")
    
    # Guardar JSON completo
    data = {
        'timestamp': timestamp,
        'total_causas': len(causas),
        'total_matches': len(matches),
        'causas': causas,
        'matches': matches
    }
    
    with open(f"{OUTPUT_DIR}/causas_completo_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    """Función principal"""
    print("=" * 60)
    print("SCRAPER DE CAUSAS DE CORRUPCIÓN")
    print("=" * 60)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Cargar legisladores
    print("\n1. Cargando legisladores de la base de datos...")
    legisladores = cargar_legisladores_db()
    print(f"   Cargados {len(legisladores)} legisladores")
    
    if not legisladores:
        print("   ADVERTENCIA: No se pudieron cargar legisladores")
        print("   Continuando solo con scraping...")
    
    # Scrapear archivo CIJ
    print("\n2. Scrapeando archivo CIJ...")
    causas = []
    
    # La URL del archivo CIJ con causas de corrupción
    # Nota: El CIJ fue disuelto, ahora está en archivo de la Corte
    url_archivo = "https://www.csjn.gov.ar/archivo-cij/buscador.html"
    
    driver = setup_driver()
    try:
        driver.get(url_archivo)
        time.sleep(3)
        
        # Buscar "corrupción" en el buscador
        try:
            campo_busqueda = driver.find_element(By.ID, "palabras")
            campo_busqueda.send_keys("corrupción")
            
            btn_buscar = driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')]")
            btn_buscar.click()
            time.sleep(5)
            
            # Parsear resultados
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Buscar tabla de resultados
            tabla = soup.find('table')
            if tabla:
                filas = tabla.find_all('tr')
                for fila in filas:
                    celdas = fila.find_all('td')
                    if len(celdas) >= 2:
                        link = fila.find('a')
                        causa = {
                            'fecha': celdas[0].get_text(strip=True) if celdas[0] else '',
                            'caratula': celdas[1].get_text(strip=True) if celdas[1] else '',
                            'url': link['href'] if link and link.has_attr('href') else '',
                            'fuente': 'archivo_cij'
                        }
                        if causa['caratula']:
                            causas.append(causa)
                            
            print(f"   Encontradas {len(causas)} entradas en archivo CIJ")
            
        except Exception as e:
            print(f"   Error en búsqueda: {e}")
            
    finally:
        driver.quit()
    
    # Si tenemos legisladores, buscar en SCW
    if legisladores:
        print("\n3. Buscando legisladores en SCW (causas civiles/comerciales)...")
        print("   NOTA: Las causas PENALES no están disponibles públicamente")
        
        # Limitar a primeros 10 para prueba
        for i, leg in enumerate(legisladores[:10]):
            nombre = leg['nombre_completo']
            print(f"   [{i+1}/10] Buscando: {nombre}")
            
            # Separar apellido y nombre
            if ',' in nombre:
                partes = nombre.split(',')
                apellido = partes[0].strip()
                nombre_pila = partes[1].strip() if len(partes) > 1 else ''
            else:
                partes = nombre.split()
                apellido = partes[0] if partes else ''
                nombre_pila = ' '.join(partes[1:]) if len(partes) > 1 else ''
            
            # Buscar en SCW
            causas_leg = scrapear_scw_por_nombre(nombre_pila, apellido)
            
            for causa in causas_leg:
                causa['fuente'] = 'scw_pjn'
                causa['legislador_id'] = leg['id']
                causa['legislador_nombre'] = leg['nombre_completo']
                causas.append(causa)
            
            time.sleep(2)  # Pausa entre requests
    
    # Cruzar con legisladores
    print("\n4. Cruzando causas con legisladores...")
    matches = cruzar_con_legisladores(causas, legisladores) if legisladores else []
    
    # Guardar resultados
    print("\n5. Guardando resultados...")
    guardar_resultados(causas, matches, timestamp)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Total causas scrapeadas: {len(causas)}")
    print(f"Matches con legisladores: {len(matches)}")
    print(f"Archivos guardados en: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
