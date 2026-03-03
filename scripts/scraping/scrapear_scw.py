"""
Scraper de Causas Judiciales - SCW PJN
======================================

Busca causas civiles/comerciales de legisladores en el Sistema de Consulta Web
del Poder Judicial de la Nación.

IMPORTANTE: Las causas PENALES no están disponibles en consulta pública.

Requisitos:
    pip install selenium webdriver-manager pandas beautifulsoup4 python-dotenv

Uso:
    python scrapear_scw.py
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
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Configuración
OUTPUT_DIR = "data/causas_scw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Jurisdicciones disponibles en SCW (las que permiten búsqueda por parte)
JURISDICCIONES = [
    "CIV",  # Civil
    "CAF",  # Contencioso Administrativo Federal
    "CCF",  # Civil y Comercial Federal
    "COM",  # Comercial
    # Las penales (CFP, CCC, CPE, etc.) no permiten búsqueda pública
]


def setup_driver(headless=True):
    """Configura el driver de Selenium"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    return driver


def cargar_legisladores():
    """Carga legisladores de la base de datos"""
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
        return [dict(row._mapping) for row in result]


def buscar_por_parte_scw(driver, apellido, nombre, jurisdiccion="CIV"):
    """
    Busca causas por parte en SCW
    """
    causas = []
    url = "https://scw.pjn.gov.ar/scw/home.seam"
    
    try:
        driver.get(url)
        time.sleep(3)
        
        # Hacer click en el tab "Por parte"
        # Los tabs están en una estructura de lista
        tabs = driver.find_elements(By.CSS_SELECTOR, "ul.rf-tab-hdr-tabs li")
        for tab in tabs:
            if "Por parte" in tab.text:
                tab.click()
                time.sleep(2)
                break
        
        # Esperar a que cargue el formulario de búsqueda por parte
        time.sleep(2)
        
        # Buscar el campo de jurisdicción en el panel de "Por parte"
        # El formulario tiene estructura diferente para cada tab
        try:
            # Seleccionar jurisdicción
            select_juris = Select(driver.find_element(By.ID, "formPublica:camaraPartes"))
            select_juris.select_by_value(jurisdiccion)
            time.sleep(1)
        except Exception as e:
            print(f"      No se pudo seleccionar jurisdicción: {e}")
            # Intentar con otro selector
            try:
                selects = driver.find_elements(By.TAG_NAME, "select")
                for sel in selects:
                    if sel.is_displayed():
                        Select(sel).select_by_value(jurisdiccion)
                        break
            except:
                pass
        
        # Buscar campos de apellido y nombre
        # Pueden tener diferentes IDs según el tab activo
        campos_apellido = driver.find_elements(By.CSS_SELECTOR, "input[id*='apellido'], input[id*='Apellido']")
        campos_nombre = driver.find_elements(By.CSS_SELECTOR, "input[id*='nombre'], input[id*='Nombre']")
        
        campo_apellido = None
        campo_nombre = None
        
        for campo in campos_apellido:
            if campo.is_displayed():
                campo_apellido = campo
                break
        
        for campo in campos_nombre:
            if campo.is_displayed() and campo != campo_apellido:
                campo_nombre = campo
                break
        
        if campo_apellido:
            campo_apellido.clear()
            campo_apellido.send_keys(apellido)
            time.sleep(0.5)
        
        if campo_nombre:
            campo_nombre.clear()
            campo_nombre.send_keys(nombre)
            time.sleep(0.5)
        
        # Buscar botón de consultar
        botones = driver.find_elements(By.CSS_SELECTOR, "input[type='submit'], button[type='submit'], input[value*='Consultar'], button")
        for boton in botones:
            texto = boton.get_attribute("value") or boton.text
            if boton.is_displayed() and ("Consultar" in texto or "Buscar" in texto):
                boton.click()
                break
        
        # Esperar resultados
        time.sleep(5)
        
        # Parsear resultados
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Buscar tabla de resultados
        tablas = soup.find_all('table')
        for tabla in tablas:
            filas = tabla.find_all('tr')
            for fila in filas[1:]:  # Saltar header
                celdas = fila.find_all('td')
                if len(celdas) >= 3:
                    causa = {
                        'expediente': celdas[0].get_text(strip=True),
                        'caratula': celdas[1].get_text(strip=True) if len(celdas) > 1 else '',
                        'juzgado': celdas[2].get_text(strip=True) if len(celdas) > 2 else '',
                        'jurisdiccion': jurisdiccion,
                        'persona_buscada': f"{apellido}, {nombre}",
                        'fuente': 'scw_pjn'
                    }
                    if causa['expediente'] and len(causa['expediente']) > 3:
                        causas.append(causa)
        
        # También buscar en divs con clase de resultado
        resultados_div = soup.find_all('div', class_=re.compile(r'result|data|row', re.I))
        for div in resultados_div:
            texto = div.get_text(strip=True)
            if '/' in texto and len(texto) > 10:  # Parece un expediente
                # Intentar extraer información
                pass
                
    except Exception as e:
        print(f"      Error en búsqueda: {str(e)[:100]}")
    
    return causas


def buscar_legislador_scw(driver, legislador):
    """Busca todas las causas de un legislador en distintas jurisdicciones"""
    nombre_completo = legislador['nombre_completo']
    
    # Separar apellido y nombre
    if ',' in nombre_completo:
        partes = nombre_completo.split(',', 1)
        apellido = partes[0].strip()
        nombre = partes[1].strip() if len(partes) > 1 else ''
    else:
        partes = nombre_completo.split()
        apellido = partes[0] if partes else ''
        nombre = ' '.join(partes[1:]) if len(partes) > 1 else ''
    
    todas_causas = []
    
    # Buscar en jurisdicciones civiles/comerciales
    for juris in JURISDICCIONES:
        print(f"      Buscando en {juris}...")
        causas = buscar_por_parte_scw(driver, apellido, nombre, juris)
        for causa in causas:
            causa['legislador_id'] = legislador['id']
            causa['legislador_nombre'] = nombre_completo
            todas_causas.append(causa)
        time.sleep(2)  # Pausa entre búsquedas
    
    return todas_causas


def guardar_resultados(causas, timestamp):
    """Guarda resultados en CSV y JSON"""
    if not causas:
        print("No hay causas para guardar")
        return
    
    df = pd.DataFrame(causas)
    
    # CSV
    csv_path = f"{OUTPUT_DIR}/causas_scw_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Guardado: {csv_path}")
    
    # JSON
    json_path = f"{OUTPUT_DIR}/causas_scw_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'total': len(causas),
            'causas': causas
        }, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {json_path}")


def main():
    print("=" * 60)
    print("SCRAPER SCW - PODER JUDICIAL DE LA NACIÓN")
    print("=" * 60)
    print("\nNOTA: Solo se pueden buscar causas CIVILES y COMERCIALES")
    print("      Las causas PENALES no están disponibles públicamente\n")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Cargar legisladores
    print("1. Cargando legisladores...")
    legisladores = cargar_legisladores()
    print(f"   Cargados: {len(legisladores)}")
    
    if not legisladores:
        print("   ERROR: No hay legisladores")
        return
    
    # Configurar driver
    print("\n2. Iniciando navegador...")
    driver = setup_driver(headless=True)
    
    todas_causas = []
    
    try:
        # Buscar primeros N legisladores (para prueba)
        MAX_LEGISLADORES = 20  # Cambiar a len(legisladores) para todos
        
        print(f"\n3. Buscando causas de {MAX_LEGISLADORES} legisladores...")
        
        for i, leg in enumerate(legisladores[:MAX_LEGISLADORES]):
            print(f"\n   [{i+1}/{MAX_LEGISLADORES}] {leg['nombre_completo']}")
            
            causas = buscar_legislador_scw(driver, leg)
            
            if causas:
                print(f"      ✓ Encontradas {len(causas)} causas")
                todas_causas.extend(causas)
            else:
                print(f"      - Sin causas encontradas")
            
            # Pausa para no sobrecargar el servidor
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
    finally:
        driver.quit()
    
    # Guardar resultados
    print(f"\n4. Guardando {len(todas_causas)} causas...")
    guardar_resultados(todas_causas, timestamp)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Legisladores procesados: {min(MAX_LEGISLADORES, len(legisladores))}")
    print(f"Causas encontradas: {len(todas_causas)}")
    print(f"Archivos en: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
