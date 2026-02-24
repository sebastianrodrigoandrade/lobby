from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import time

BASE = "https://www.hcdn.gob.ar"

COMISIONES = [
    "/comisiones/permanentes/caconstitucionales",
    "/comisiones/permanentes/clgeneral",
    "/comisiones/permanentes/creyculto",
    "/comisiones/permanentes/cpyhacienda",
    "/comisiones/permanentes/ceducacion",
    "/comisiones/permanentes/ccytecnologia",
    "/comisiones/permanentes/ccultura",
    "/comisiones/permanentes/cjusticia",
    "/comisiones/permanentes/cpyssocial",
    "/comisiones/permanentes/casyspublica",
    "/comisiones/permanentes/cfnjuventudes",
    "/comisiones/permanentes/cpmayores",
    "/comisiones/permanentes/clpenal",
    "/comisiones/permanentes/cltrabajo",
    "/comisiones/permanentes/cdnacional",
    "/comisiones/permanentes/copublicas",
    "/comisiones/permanentes/cayganaderia",
    "/comisiones/permanentes/cfinanzas",
    "/comisiones/permanentes/cindustria",
    "/comisiones/permanentes/ccomercio",
    "/comisiones/permanentes/ceycombust",
    "/comisiones/permanentes/cceinformatica",
    "/comisiones/permanentes/ctransportes",
    "/comisiones/permanentes/ceydregional",
    "/comisiones/permanentes/camunicipales",
    "/comisiones/permanentes/cimaritimos",
    "/comisiones/permanentes/cvyourbano",
    "/comisiones/permanentes/cppyreglamento",
    "/comisiones/permanentes/cjpolitico",
    "/comisiones/permanentes/crnaturales",
    "/comisiones/permanentes/cturismo",
    "/comisiones/permanentes/ceconomia",
    "/comisiones/permanentes/cmineria",
    "/comisiones/permanentes/cdrogadiccion",
    "/comisiones/permanentes/cmtyprevisionales",
    "/comisiones/permanentes/cpydhumano",
    "/comisiones/permanentes/cdeportes",
    "/comisiones/permanentes/cdhygarantias",
    "/comisiones/permanentes/cacym",
    "/comisiones/permanentes/cmercosur",
    "/comisiones/permanentes/cpymes",
    "/comisiones/permanentes/cdconsumidor",
    "/comisiones/permanentes/csinterior",
    "/comisiones/permanentes/clexpresion",
    "/comisiones/permanentes/cdiscap",
    "/comisiones/permanentes/cmujeresydiv",
]

def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver

def scrapear_reuniones_selenium(driver, url_base):
    url = f"{BASE}{url_base}/reuniones/"
    driver.get(url)
    time.sleep(3)  # esperar JS

    reuniones = []
    fecha_actual = None

    try:
        elementos = driver.find_elements(By.XPATH, "//*[contains(text(), 'REUNIONES DEL DIA') or contains(@class, 'reunion') or contains(@class, 'citacion')]")
        
        # Si no encontramos nada específico, tomamos todo el texto
        body_text = driver.find_element(By.TAG_NAME, 'body').text
        lineas = [l.strip() for l in body_text.split('\n') if l.strip()]

        for i, linea in enumerate(lineas):
            if 'REUNIONES DEL DIA' in linea:
                fecha_actual = linea.replace('REUNIONES DEL DIA', '').strip()
            elif fecha_actual and any(t in linea.upper() for t in ['INVITADO', 'REUNIÓN CONSTITUTIVA', 'INFORMATIVA', 'EMPLAZAMIENTO', 'CONJUNTA']):
                # Capturar descripción siguiente
                desc = linea
                if i + 1 < len(lineas):
                    desc += ' ' + lineas[i + 1]
                reuniones.append({
                    'fecha': fecha_actual,
                    'tipo': 'INVITADO' if 'INVITADO' in linea.upper() else 'REUNION',
                    'descripcion': desc[:400],
                })

    except Exception as e:
        logger.warning(f"  Error parseando reuniones: {e}")

    return reuniones

def main():
    logger.info("=== SCRAPING REUNIONES COMISIONES (Selenium) ===")
    session = SessionLocal()
    driver = iniciar_driver()

    try:
        total_reuniones = 0

        for url_base in COMISIONES:
            slug = url_base.split('/')[-1]

            # Obtener comision_id
            res = session.execute(text("SELECT id FROM comisiones WHERE slug = :slug"), {'slug': slug})
            row = res.fetchone()
            if not row:
                logger.warning(f"  {slug} no encontrada en DB, salteando")
                continue
            comision_id = row[0]

            logger.info(f"Procesando reuniones: {slug}")

            try:
                session.execute(text("DELETE FROM comision_reuniones WHERE comision_id = :id"), {'id': comision_id})
                reuniones = scrapear_reuniones_selenium(driver, url_base)

                for reu in reuniones:
                    session.execute(text("""
                        INSERT INTO comision_reuniones (comision_id, fecha, tipo, descripcion)
                        VALUES (:cid, :fecha, :tipo, :descripcion)
                    """), {
                        'cid': comision_id,
                        'fecha': reu['fecha'],
                        'tipo': reu['tipo'],
                        'descripcion': reu['descripcion'],
                    })

                session.commit()
                total_reuniones += len(reuniones)
                logger.info(f"  {len(reuniones)} reuniones")

            except Exception as e:
                logger.warning(f"  Error en {slug}: {e}")
                session.rollback()

            time.sleep(1)

        logger.info(f"Total reuniones scrapeadas: {total_reuniones}")

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        session.rollback()
        raise
    finally:
        driver.quit()
        session.close()

if __name__ == "__main__":
    main()