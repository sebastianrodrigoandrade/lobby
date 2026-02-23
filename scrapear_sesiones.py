from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE = "https://www.hcdn.gob.ar"

sesiones_extraordinarias = [
    {'id': 3512, 'reunion': 12, 'periodo': 141, 'fecha': '31/01/2024', 'descripcion': '1° Sesión Extraordinaria'},
    {'id': 3513, 'reunion': 13, 'periodo': 141, 'fecha': '01/02/2024', 'descripcion': 'Continuación'},
    {'id': 3514, 'reunion': 14, 'periodo': 141, 'fecha': '02/02/2024', 'descripcion': 'Continuación'},
    {'id': 3515, 'reunion': 15, 'periodo': 141, 'fecha': '06/02/2024', 'descripcion': 'Continuación'},
    {'id': 3549, 'reunion': 21, 'periodo': 142, 'fecha': '06/02/2025', 'descripcion': '1° Sesión Extraordinaria'},
    {'id': 3550, 'reunion': 22, 'periodo': 142, 'fecha': '12/02/2025', 'descripcion': '2° Sesión Extraordinaria'},
]

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

resultados = []

for sesion in sesiones_extraordinarias:
    url = f"{BASE}/sesiones/sesion.html?id={sesion['id']}&numVid=0&reunion={sesion['reunion']}&periodo={sesion['periodo']}"
    print(f"\nScrapeando: {sesion['fecha']} - {sesion['descripcion']}")
    
    driver.get(url)
    time.sleep(3)  # esperar que cargue el JS
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    tablas = soup.find_all('table')
    print(f"  Tablas encontradas: {len(tablas)}")
    
    temas = soup.find_all(['h2', 'h3', 'h4', 'li', 'td'])
    textos = [t.get_text(strip=True) for t in temas if len(t.get_text(strip=True)) > 30]
    print(f"  Primeros textos:")
    for t in textos[:8]:
        print(f"    - {t[:120]}")

driver.quit()
print("\n✅ Scraping completado")