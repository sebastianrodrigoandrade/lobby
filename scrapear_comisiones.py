import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import time
import warnings
warnings.filterwarnings('ignore')

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

def get_nombre_comision(slug):
    return slug.split('/')[-1]

def scrapear_integrantes(url_base):
    r = requests.get(f"{BASE}{url_base}/integrantes.html", timeout=15, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')
    tabla = soup.find('table')
    if not tabla:
        return []
    integrantes = []
    for fila in tabla.find_all('tr')[1:]:
        celdas = fila.find_all('td')
        if len(celdas) >= 4:
            integrantes.append({
                'cargo': celdas[0].get_text(strip=True),
                'nombre': celdas[1].get_text(strip=True),
                'bloque': celdas[2].get_text(strip=True),
                'distrito': celdas[3].get_text(strip=True),
            })
    return integrantes

def scrapear_reuniones(url_base):
    r = requests.get(f"{BASE}{url_base}/reuniones/", timeout=15, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')
    reuniones = []
    fecha_actual = None

    for elem in soup.find_all(['h3', 'div', 'p']):
        texto = elem.get_text(strip=True)

        # Detectar fecha
        if 'REUNIONES DEL DIA' in texto:
            fecha_actual = texto.replace('REUNIONES DEL DIA', '').strip()
            continue

        # Detectar invitados
        if 'INVITADO' in texto.upper() and fecha_actual:
            reuniones.append({
                'fecha': fecha_actual,
                'tipo': 'INVITADO',
                'descripcion': texto,
            })
        elif 'REUNIÓN' in texto.upper() and fecha_actual and len(texto) > 10:
            reuniones.append({
                'fecha': fecha_actual,
                'tipo': 'REUNION',
                'descripcion': texto[:300],
            })

    return reuniones

def main():
    logger.info("=== SCRAPING COMISIONES HCDN ===")
    session = SessionLocal()

    try:
        # Crear tablas si no existen
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS comisiones (
                id SERIAL PRIMARY KEY,
                slug VARCHAR UNIQUE NOT NULL,
                nombre VARCHAR,
                camara VARCHAR DEFAULT 'Diputados'
            )
        """))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS comision_integrantes (
                id SERIAL PRIMARY KEY,
                comision_id INTEGER REFERENCES comisiones(id),
                legislador_id INTEGER REFERENCES legisladores(id),
                nombre_raw VARCHAR,
                cargo VARCHAR,
                bloque VARCHAR,
                distrito VARCHAR
            )
        """))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS comision_reuniones (
                id SERIAL PRIMARY KEY,
                comision_id INTEGER REFERENCES comisiones(id),
                fecha VARCHAR,
                tipo VARCHAR,
                descripcion TEXT
            )
        """))
        session.commit()
        logger.info("Tablas creadas")

        for url_base in COMISIONES:
            slug = get_nombre_comision(url_base)
            logger.info(f"Procesando: {slug}")

            # Insertar o recuperar comisión
            res = session.execute(text("""
                INSERT INTO comisiones (slug, nombre)
                VALUES (:slug, :nombre)
                ON CONFLICT (slug) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id
            """), {'slug': slug, 'nombre': slug})
            comision_id = res.fetchone()[0]

            # Borrar integrantes anteriores para reinsertar frescos
            session.execute(text("DELETE FROM comision_integrantes WHERE comision_id = :id"), {'id': comision_id})

            # Integrantes
            try:
                integrantes = scrapear_integrantes(url_base)
                for ing in integrantes:
                    # Intentar cruzar con legisladores en DB
                    apellido = ing['nombre'].split(',')[0].strip().upper() if ',' in ing['nombre'] else ing['nombre'].split()[0].upper()
                    res_leg = session.execute(text("""
                        SELECT id FROM legisladores
                        WHERE nombre_completo ILIKE :apellido
                        LIMIT 1
                    """), {'apellido': f'%{apellido}%'})
                    row = res_leg.fetchone()
                    legislador_id = row[0] if row else None

                    session.execute(text("""
                        INSERT INTO comision_integrantes 
                            (comision_id, legislador_id, nombre_raw, cargo, bloque, distrito)
                        VALUES (:cid, :lid, :nombre, :cargo, :bloque, :distrito)
                    """), {
                        'cid': comision_id,
                        'lid': legislador_id,
                        'nombre': ing['nombre'],
                        'cargo': ing['cargo'],
                        'bloque': ing['bloque'],
                        'distrito': ing['distrito'],
                    })
                logger.info(f"  {len(integrantes)} integrantes")
            except Exception as e:
                logger.warning(f"  Error integrantes: {e}")

            # Reuniones
            try:
                session.execute(text("DELETE FROM comision_reuniones WHERE comision_id = :id"), {'id': comision_id})
                reuniones = scrapear_reuniones(url_base)
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
                logger.info(f"  {len(reuniones)} reuniones")
            except Exception as e:
                logger.warning(f"  Error reuniones: {e}")

            session.commit()
            time.sleep(0.5)

        logger.info("=== SCRAPING COMPLETO ===")

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()