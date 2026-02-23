import requests
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import time
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"
def get_acta_con_retry(url, max_intentos=3):
    for intento in range(max_intentos):
        try:
            r = requests.get(url, timeout=20, verify=False)
            return r
        except Exception as e:
            if intento < max_intentos - 1:
                logger.warning(f"  Reintento {intento+1} para {url}")
                time.sleep(2 ** intento)
            else:
                raise e
def parsear_acta(acta_id):
    url = f"{BASE}/votaciones/detalleActa/{acta_id}"
    r = get_acta_con_retry(url)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    texto = soup.get_text(separator='\n', strip=True)

    if 'Senador' not in texto and 'AFIRMATIVO' not in texto:
        return None

    # Parsear metadata del acta
    metadata = {
        'acta_id': acta_id,
        'titulo': '',
        'fecha': None,
        'resultado': '',
        'afirmativos': 0,
        'negativos': 0,
        'abstenciones': 0,
        'ausentes': 0,
    }

    lineas = [l.strip() for l in texto.split('\n') if l.strip()]

    for i, linea in enumerate(lineas):
        if linea.startswith('Acta Nro:'):
            if i + 1 < len(lineas):
                metadata['titulo'] = lineas[i + 1]
        if '/' in linea and len(linea) <= 12:
            try:
                metadata['fecha'] = datetime.strptime(linea[:10], '%d/%m/%Y').date()
            except:
                pass
        if 'AFIRMATIVOS' in linea:
            try:
                metadata['afirmativos'] = int(lineas[i - 1])
            except:
                pass
        if 'NEGATIVOS' in linea:
            try:
                metadata['negativos'] = int(lineas[i - 1])
            except:
                pass
        if 'ABSTENCIONES' in linea:
            try:
                metadata['abstenciones'] = int(lineas[i - 1])
            except:
                pass
        if 'AUSENTES' in linea:
            try:
                metadata['ausentes'] = int(lineas[i - 1])
            except:
                pass

    # Parsear votos individuales desde tabla HTML
    votos = []
    tabla = soup.find('table')
    if tabla:
        filas = tabla.find_all('tr')[1:]  # saltar header
        for fila in filas:
            celdas = fila.find_all('td')
            if len(celdas) >= 4:
                nombre = celdas[1].get_text(strip=True)
                bloque = celdas[2].get_text(strip=True)
                provincia = celdas[3].get_text(strip=True)
                voto = celdas[4].get_text(strip=True) if len(celdas) > 4 else ''
                if nombre and voto:
                    votos.append({
                        'nombre': nombre,
                        'bloque': bloque,
                        'provincia': provincia,
                        'voto': voto,
                    })

    return metadata, votos


def main():
    logger.info("=== INGESTA VOTACIONES SENADO ===")
    session = SessionLocal()

    try:
        # IDs ya procesados
        existentes = {
            row[0] for row in session.execute(
                text("SELECT acta_id FROM actas_cabecera WHERE camara = 'Senado'")
            ).fetchall()
        }
        logger.info(f"Actas ya en DB: {len(existentes)}")

        # Cache de senadores
        cache_senadores = {
            leg.nombre_completo: leg.id
            for leg in session.execute(
                text("SELECT id, nombre_completo FROM legisladores WHERE camara = 'Senadores'")
            ).fetchall()
        }
        logger.info(f"Senadores en cache: {len(cache_senadores)}")

        actas_nuevas = 0
        votos_nuevos = 0
        MAX_ID = 2650  # actualizar periódicamente

        for acta_id in range(1, MAX_ID + 1):
            if acta_id in existentes:
                continue

            try:
                resultado = parsear_acta(acta_id)
                if not resultado:
                    continue

                metadata, votos = resultado
                if not votos:
                    continue

                # Insertar acta en cabecera
                session.execute(text("""
                    INSERT INTO actas_cabecera 
                        (acta_id, titulo, fecha, resultado, 
                         votos_afirmativos, votos_negativos, abstenciones, ausentes, camara)
                    VALUES 
                        (:acta_id, :titulo, :fecha, :resultado,
                         :afirmativos, :negativos, :abstenciones, :ausentes, 'Senado')
                    ON CONFLICT (acta_id) DO NOTHING
                """), metadata)

                # Insertar/actualizar senadores y votos
                for v in votos:
                    nombre = v['nombre']

                    # Crear senador si no existe
                    if nombre not in cache_senadores:
                        res = session.execute(text("""
                            INSERT INTO legisladores 
                                (nombre_completo, camara, bloque, distrito)
                            VALUES 
                                (:nombre, 'Senadores', :bloque, :provincia)
                            ON CONFLICT DO NOTHING
                            RETURNING id
                        """), {
                            'nombre': nombre,
                            'bloque': v['bloque'],
                            'provincia': v['provincia'],
                        })
                        row = res.fetchone()
                        if row:
                            cache_senadores[nombre] = row[0]

                    legislador_id = cache_senadores.get(nombre)
                    if not legislador_id:
                        continue

                    session.execute(text("""
                        INSERT INTO votos (legislador_id, acta_id, voto_individual)
                        VALUES (:leg_id, :acta_id, :voto)
                    """), {
                        'leg_id': legislador_id,
                        'acta_id': acta_id,
                        'voto': v['voto'],
                    })
                    votos_nuevos += 1

                actas_nuevas += 1

                if actas_nuevas % 50 == 0:
                    session.commit()
                    logger.info(f"  Actas: {actas_nuevas} | Votos: {votos_nuevos} | ID actual: {acta_id}")

                time.sleep(0.3)  # respetar el servidor

            except Exception as e:
                logger.warning(f"  Error en acta {acta_id}: {e}")
                continue

        session.commit()
        logger.info(f"Ingesta completa — Actas: {actas_nuevas} | Votos: {votos_nuevos}")

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()