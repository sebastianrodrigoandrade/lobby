#!/usr/bin/env python3
"""
Scraper de Audiencias del Poder Ejecutivo Nacional
===================================================
Fuente: https://audiencias.mininterior.gob.ar/

Este portal contiene ~60,000 audiencias de funcionarios del Poder Ejecutivo.
Los legisladores aparecen como SOLICITANTES (pidiendo reuniones a ministros).

Uso:
    python scrapear_audiencias_ejecutivo.py
    
Salida:
    - data/audiencias_ejecutivo/audiencias.csv
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
import os
from datetime import datetime

OUTPUT_DIR = "data/audiencias_ejecutivo"
BASE_URL = "https://audiencias.mininterior.gob.ar"


def setup_driver():
    """Configura el driver de Chrome."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


def parsear_audiencia(elemento):
    """Extrae datos de un elemento de audiencia."""
    try:
        texto = elemento.text
        
        # Estructura tipica:
        # Sujeto obligado | Solicitante | Otros participantes | Datos audiencia
        
        audiencia = {
            'texto_completo': texto,
            'sujeto_obligado': None,
            'sujeto_cargo': None,
            'sujeto_dependencia': None,
            'solicitante': None,
            'solicitante_cargo': None,
            'fecha': None,
            'hora': None,
            'interes': None,
            'motivo': None,
        }
        
        # Extraer fecha
        fecha_match = re.search(r'Fecha\s*(\d{2}-\d{2}-\d{4})', texto)
        if fecha_match:
            audiencia['fecha'] = fecha_match.group(1)
        
        # Extraer hora
        hora_match = re.search(r'Hora\s*(\d{2}:\d{2})', texto)
        if hora_match:
            audiencia['hora'] = hora_match.group(1)
        
        # Extraer interes
        interes_match = re.search(r'Interés invocado\s*(\w+)', texto)
        if interes_match:
            audiencia['interes'] = interes_match.group(1)
        
        # Extraer motivo (todo despues de "Motivo")
        motivo_match = re.search(r'Motivo\s*(.+?)(?:Fecha|$)', texto, re.DOTALL)
        if motivo_match:
            audiencia['motivo'] = motivo_match.group(1).strip()[:500]
        
        # Intentar extraer sujeto obligado (primera persona mencionada)
        lineas = texto.split('\n')
        for i, linea in enumerate(lineas):
            if 'Sujeto obligado' in linea and i + 1 < len(lineas):
                audiencia['sujeto_obligado'] = lineas[i + 1].strip()
                break
        
        return audiencia
    
    except Exception as e:
        print(f"Error parseando: {e}")
        return None


def obtener_audiencias_pagina(driver):
    """Obtiene las audiencias de la pagina actual."""
    audiencias = []
    
    results = driver.find_elements(By.CLASS_NAME, 'result-el')
    
    for r in results:
        audiencia = parsear_audiencia(r)
        if audiencia:
            audiencias.append(audiencia)
    
    return audiencias


def buscar_audiencias(driver, query="", max_pages=None):
    """Busca audiencias con un query."""
    todas = []
    
    # Ir a busqueda
    url = f"{BASE_URL}/buscar?q={query}"
    driver.get(url)
    time.sleep(3)
    
    page = 1
    
    while True:
        print(f"  Pagina {page}...", end=" ", flush=True)
        
        audiencias = obtener_audiencias_pagina(driver)
        print(f"{len(audiencias)} audiencias")
        
        if not audiencias:
            break
        
        todas.extend(audiencias)
        
        if max_pages and page >= max_pages:
            break
        
        # Buscar boton siguiente
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, '.pagination .next a')
            next_btn.click()
            time.sleep(2)
            page += 1
        except:
            # No hay mas paginas
            break
    
    return todas


def scrapear_por_anio(driver, anio):
    """Scrapea audiencias de un año especifico usando el filtro de fechas."""
    todas = []
    
    driver.get(f"{BASE_URL}/")
    time.sleep(2)
    
    # Activar busqueda avanzada
    try:
        checkbox = driver.find_element(By.ID, 'show-advance-search')
        if not checkbox.is_selected():
            label = driver.find_element(By.CSS_SELECTOR, 'label[for="show-advance-search"]')
            label.click()
            time.sleep(1)
    except:
        pass
    
    # Ingresar fechas
    try:
        date_from = driver.find_element(By.ID, 'date-from')
        date_to = driver.find_element(By.ID, 'date-to')
        
        date_from.clear()
        date_from.send_keys(f"01/01/{anio}")
        
        date_to.clear()
        date_to.send_keys(f"31/12/{anio}")
        
        # Buscar
        btn = driver.find_element(By.ID, 'submit-search')
        btn.click()
        time.sleep(3)
        
        # Obtener todas las paginas
        page = 1
        while True:
            print(f"  {anio} - Pagina {page}...", end=" ", flush=True)
            
            audiencias = obtener_audiencias_pagina(driver)
            print(f"{len(audiencias)} audiencias")
            
            if not audiencias:
                break
            
            for a in audiencias:
                a['anio'] = anio
            
            todas.extend(audiencias)
            
            # Siguiente pagina
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, '.pagination .next a')
                next_btn.click()
                time.sleep(2)
                page += 1
            except:
                break
        
    except Exception as e:
        print(f"Error en {anio}: {e}")
    
    return todas


def main():
    print("=" * 60)
    print("SCRAPER AUDIENCIAS PODER EJECUTIVO NACIONAL")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Fuente: {BASE_URL}")
    print()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    driver = setup_driver()
    
    try:
        todas_las_audiencias = []
        
        # Scrapear por año (2016-2026)
        for anio in range(2026, 2015, -1):
            print(f"\nScrapeando {anio}...")
            audiencias = scrapear_por_anio(driver, anio)
            todas_las_audiencias.extend(audiencias)
            
            # Checkpoint
            if todas_las_audiencias:
                df = pd.DataFrame(todas_las_audiencias)
                df.to_csv(f"{OUTPUT_DIR}/audiencias_checkpoint.csv", index=False)
                print(f"  Checkpoint: {len(todas_las_audiencias)} audiencias total")
        
        # Guardar resultado final
        if todas_las_audiencias:
            df = pd.DataFrame(todas_las_audiencias)
            df.to_csv(f"{OUTPUT_DIR}/audiencias_ejecutivo.csv", index=False)
            
            print()
            print("=" * 60)
            print("RESULTADOS")
            print("=" * 60)
            print(f"Total audiencias: {len(df)}")
            print(f"Guardado en: {OUTPUT_DIR}/audiencias_ejecutivo.csv")
            
            if 'anio' in df.columns:
                print("\nPor año:")
                for anio, count in df.groupby('anio').size().sort_index(ascending=False).items():
                    print(f"  {anio}: {count}")
        
    finally:
        driver.quit()
    
    print("\nCompletado!")


if __name__ == "__main__":
    main()